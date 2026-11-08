using System;
using System.IO;
using System.Linq;
using System.Text;
using Microsoft.Win32;
using SpriteLab.RiggingV2.Editor;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

namespace SpriteLab.UnityLink.Editor
{
    [InitializeOnLoad]
    public static class SpriteLabUnityLink
    {
        private const string Scheme = "spritelab-unity";
        private const string AllowedHostsKey = "SpriteLab.UnityLink.AllowedHosts";
        private static readonly string StateRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SpriteLabUnityLink");
        private static readonly string QueueRoot = Path.Combine(StateRoot, "queue");
        private static readonly string HeartbeatPath = Path.Combine(StateRoot, "heartbeat.txt");
        private static readonly string ConfigPath = Path.Combine(StateRoot, "config.txt");
        private static double nextHeartbeat;
        private static UnityWebRequest download;
        private static string downloadPath;

        static SpriteLabUnityLink()
        {
            Initialize();
        }

        [InitializeOnLoadMethod]
        private static void Initialize()
        {
            EditorApplication.update -= Tick;
            EditorApplication.update += Tick;
            EditorApplication.delayCall -= EnsureBridgeInstalled;
            EditorApplication.delayCall += EnsureBridgeInstalled;
            WriteHeartbeat();
            Debug.Log("Sprite Lab One-click Link receiver ready: " + StateRoot);
        }

        [MenuItem("Tools/Sprite Lab/One-click Link/Enable for this project")]
        public static void Enable()
        {
#if !UNITY_EDITOR_WIN
            EditorUtility.DisplayDialog("Sprite Lab", "현재 원클릭 링크 설치는 Windows Unity Editor를 지원합니다.", "확인");
#else
            InstallBridge();
            EditorUtility.DisplayDialog("Sprite Lab", "이 프로젝트를 원클릭 가져오기 대상으로 등록했습니다.\n이제 사이트의 ‘Unity에서 열기’를 사용할 수 있습니다.", "확인");
#endif
        }

#if UNITY_EDITOR_WIN
        private static void InstallBridge()
        {
            Directory.CreateDirectory(StateRoot);
            Directory.CreateDirectory(QueueRoot);
            var handler = Path.Combine(StateRoot, "SpriteLabUnityLinkHandler.js");
            File.WriteAllText(handler, ReadHandlerTemplate());
            var project = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            File.WriteAllLines(ConfigPath, new[]
            {
                EditorApplication.applicationPath,
                project,
                Path.GetFileName(project)
            }, Encoding.Unicode);
            using (var protocol = Registry.CurrentUser.CreateSubKey(@"Software\Classes\" + Scheme))
            {
                protocol.SetValue("", "URL:Sprite Lab Unity Link");
                protocol.SetValue("URL Protocol", "");
                using var command = protocol.CreateSubKey(@"shell\open\command");
                command.SetValue("", Quote(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "wscript.exe"))
                    + " " + Quote(handler) + " \"%1\"");
            }
            File.WriteAllText(HeartbeatPath, DateTime.UtcNow.ToString("O"));
        }
#endif

        private static void EnsureBridgeInstalled()
        {
#if UNITY_EDITOR_WIN
            try
            {
                InstallBridge();
                Debug.Log("Sprite Lab One-click Link bridge installed for this project (v2).");
            }
            catch (Exception error)
            {
                Debug.LogWarning("Sprite Lab One-click Link bridge installation failed: " + error.Message);
            }
#endif
        }

        [MenuItem("Tools/Sprite Lab/One-click Link/Disable")]
        public static void Disable()
        {
#if UNITY_EDITOR_WIN
            Registry.CurrentUser.DeleteSubKeyTree(@"Software\Classes\" + Scheme, false);
#endif
            EditorUtility.DisplayDialog("Sprite Lab", "Sprite Lab 원클릭 링크 연결을 해제했습니다.", "확인");
        }

        private static void Tick()
        {
            // The handler launches the configured project. An already-open editor with
            // this package can immediately drain the queue without another menu step.
            if (EditorApplication.timeSinceStartup >= nextHeartbeat)
            {
                nextHeartbeat = EditorApplication.timeSinceStartup + 2d;
                WriteHeartbeat();
            }
            if (download != null)
            {
                if (!download.isDone) return;
                FinishDownload();
                return;
            }
            if (!Directory.Exists(QueueRoot)) return;
            var request = Directory.GetFiles(QueueRoot, "*.link").OrderBy(path => path).FirstOrDefault();
            if (request == null) return;
            try
            {
                var link = File.ReadAllText(request).Trim();
                File.Delete(request);
                BeginImport(link);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                TryDelete(request);
            }
        }

        private static void BeginImport(string deepLink)
        {
            if (!Uri.TryCreate(deepLink, UriKind.Absolute, out var link) || link.Scheme != Scheme || link.Host != "import")
                throw new InvalidDataException("올바른 Sprite Lab Unity 링크가 아닙니다.");
            var query = ParseQuery(link.Query);
            if (!query.TryGetValue("url", out var encodedUrl))
                throw new InvalidDataException("다운로드 주소가 없습니다.");
            var packageUrl = Uri.UnescapeDataString(encodedUrl);
            if (!Uri.TryCreate(packageUrl, UriKind.Absolute, out var remote) ||
                !(remote.Scheme == Uri.UriSchemeHttps || (remote.Scheme == Uri.UriSchemeHttp && remote.IsLoopback)))
                throw new InvalidDataException("HTTPS 또는 로컬 Sprite Lab 주소만 가져올 수 있습니다.");
            if (!IsAllowed(remote.Host))
            {
                if (!EditorUtility.DisplayDialog("Sprite Lab 캐릭터 가져오기",
                        remote.Host + "에서 V2 스켈레톤 ZIP을 받아 현재 프로젝트로 가져올까요?", "가져오기", "취소"))
                    return;
                RememberHost(remote.Host);
            }
            var name = query.TryGetValue("name", out var encodedName) ? Uri.UnescapeDataString(encodedName) : "character";
            name = Sanitize(name);
            downloadPath = Path.Combine(Path.GetTempPath(), "sprite-lab-" + name + "-" + Guid.NewGuid().ToString("N") + ".zip");
            download = UnityWebRequest.Get(remote);
            download.SendWebRequest();
            Debug.Log("Sprite Lab V2 패키지 다운로드 시작: " + remote.Host);
        }

        private static void FinishDownload()
        {
            var request = download;
            download = null;
            try
            {
                if (request.result != UnityWebRequest.Result.Success)
                    throw new IOException("Sprite Lab 패키지 다운로드 실패: " + request.error);
                File.WriteAllBytes(downloadPath, request.downloadHandler.data);
                var prefabPath = RiggingV2Importer.ImportZipAtPath(downloadPath);
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                Selection.activeObject = prefab;
                EditorGUIUtility.PingObject(prefab);
                Debug.Log("Sprite Lab V2 prefab 생성: " + prefabPath);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                EditorUtility.DisplayDialog("Sprite Lab 가져오기 실패", error.Message, "확인");
            }
            finally
            {
                request.Dispose();
                TryDelete(downloadPath);
                downloadPath = null;
            }
        }

        private static System.Collections.Generic.Dictionary<string, string> ParseQuery(string query)
        {
            return query.TrimStart('?').Split('&')
                .Where(part => !string.IsNullOrWhiteSpace(part))
                .Select(part => part.Split(new[] { '=' }, 2))
                .ToDictionary(parts => Uri.UnescapeDataString(parts[0]), parts => parts.Length > 1 ? parts[1] : "");
        }

        private static bool IsAllowed(string host) =>
            EditorPrefs.GetString(AllowedHostsKey, "").Split('|').Any(value => string.Equals(value, host, StringComparison.OrdinalIgnoreCase));

        private static bool IsEnabledProject()
        {
#if !UNITY_EDITOR_WIN
            return false;
#else
            try
            {
                if (!File.Exists(ConfigPath)) return false;
                var config = File.ReadAllLines(ConfigPath);
                if (config.Length < 2) return false;
                var current = Path.GetFullPath(Path.Combine(Application.dataPath, ".."))
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                var enabled = Path.GetFullPath(config[1])
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                return string.Equals(current, enabled, StringComparison.OrdinalIgnoreCase);
            }
            catch { return false; }
#endif
        }

        private static void RememberHost(string host)
        {
            var values = EditorPrefs.GetString(AllowedHostsKey, "").Split('|')
                .Where(value => !string.IsNullOrWhiteSpace(value)).ToList();
            if (!values.Any(value => string.Equals(value, host, StringComparison.OrdinalIgnoreCase))) values.Add(host);
            EditorPrefs.SetString(AllowedHostsKey, string.Join("|", values));
        }

        private static string ReadHandlerTemplate()
        {
            var guid = AssetDatabase.FindAssets("SpriteLabUnityLinkHandler t:TextAsset").FirstOrDefault();
            if (string.IsNullOrEmpty(guid)) throw new FileNotFoundException("SpriteLabUnityLinkHandler.txt를 찾을 수 없습니다.");
            return File.ReadAllText(Path.GetFullPath(AssetDatabase.GUIDToAssetPath(guid)));
        }

        private static string Quote(string value) => "\"" + value.Replace("\"", "\\\"") + "\"";
        private static void WriteHeartbeat()
        {
            try
            {
                Directory.CreateDirectory(StateRoot);
                File.WriteAllText(HeartbeatPath, DateTime.UtcNow.ToString("O"));
            }
            catch (Exception error)
            {
                Debug.LogWarning("Sprite Lab heartbeat write failed: " + error.Message);
            }
        }

        private static string Sanitize(string value)
        {
            var invalid = Path.GetInvalidFileNameChars();
            var cleaned = new string((value ?? "character").Where(character => !invalid.Contains(character)).ToArray());
            return string.IsNullOrWhiteSpace(cleaned) ? "character" : cleaned.Substring(0, Math.Min(60, cleaned.Length));
        }
        private static void TryDelete(string path)
        {
            try { if (!string.IsNullOrEmpty(path) && File.Exists(path)) File.Delete(path); } catch { }
        }
    }
}
