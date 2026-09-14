using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using SpriteLab.RiggingV1;
using UnityEditor;
using UnityEngine;

namespace SpriteLab.RiggingV1.Editor
{
    public static class RiggingV1Importer
    {
        private const float PixelsPerUnit = 100f;

        [Serializable] private sealed class Manifest
        {
            public CanvasInfo canvas;
            public Part[] parts;
            public Expression[] expressions;
            public Anchors anchors;
        }

        [Serializable] private sealed class CanvasInfo { public int width; public int height; }
        [Serializable] private sealed class FaceAnchor { public float cx; public float cy; }
        [Serializable] private sealed class Anchors { public FaceAnchor face; public float hairRootY; }

        [Serializable] private class LayerRecord
        {
            public string id;
            public string file;
            public int left;
            public int top;
            public int width;
            public int height;
        }

        [Serializable] private sealed class Part : LayerRecord
        {
            public string runtimeName;
            public float depthMedian;
        }

        [Serializable] private sealed class Expression : LayerRecord
        {
            public string side;
            public string fade;
        }

        [MenuItem("Tools/Sprite Lab/Import Rigging V1 ZIP")]
        public static void ImportZip()
        {
            var zipPath = EditorUtility.OpenFilePanel("Rigging V1 ZIP 선택", "", "zip");
            if (string.IsNullOrEmpty(zipPath)) return;
            try
            {
                var prefabPath = ImportZipAtPath(zipPath);
                Selection.activeObject = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                EditorGUIUtility.PingObject(Selection.activeObject);
                Debug.Log("Rigging V1 prefab 생성: " + prefabPath);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                EditorUtility.DisplayDialog("Rigging V1 가져오기 실패", error.Message, "확인");
            }
        }

        public static string ImportZipAtPath(string zipPath)
        {
            if (string.IsNullOrWhiteSpace(zipPath) || !File.Exists(zipPath))
                throw new FileNotFoundException("Rigging V1 ZIP을 찾을 수 없습니다.", zipPath);
            var folderName = Sanitize(Path.GetFileNameWithoutExtension(zipPath)) + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss");
            var assetRoot = "Assets/RiggingV1/Imported/" + folderName;
            var diskRoot = Path.GetFullPath(assetRoot);
            Directory.CreateDirectory(diskRoot);
            ExtractAllowedFiles(zipPath, diskRoot);
            var manifestPath = Path.Combine(diskRoot, "manifest.json");
            if (!File.Exists(manifestPath)) throw new InvalidDataException("manifest.json이 없습니다.");
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(manifestPath));
            if (manifest == null || manifest.canvas == null || manifest.parts == null)
                throw new InvalidDataException("manifest.json 형식이 올바르지 않습니다.");

            ConfigureTextures(assetRoot, manifest);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var prefabPath = BuildPrefab(assetRoot, manifest);
            Debug.Log("Rigging V1 prefab 생성: " + prefabPath);
            return prefabPath;
        }

        private static void ExtractAllowedFiles(string zipPath, string diskRoot)
        {
            var rootWithSeparator = diskRoot.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            using var archive = ZipFile.OpenRead(zipPath);
            foreach (var entry in archive.Entries)
            {
                var normalized = entry.FullName.Replace('\\', '/');
                if (!(normalized == "manifest.json" || normalized.StartsWith("layers/") || normalized.StartsWith("expressions/")))
                    continue;
                var target = Path.GetFullPath(Path.Combine(diskRoot, normalized.Replace('/', Path.DirectorySeparatorChar)));
                if (!target.StartsWith(rootWithSeparator, StringComparison.OrdinalIgnoreCase) && target != diskRoot)
                    throw new InvalidDataException("ZIP 경로가 출력 폴더를 벗어납니다.");
                if (string.IsNullOrEmpty(entry.Name)) { Directory.CreateDirectory(target); continue; }
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                entry.ExtractToFile(target, true);
            }
        }

        private static void ConfigureTextures(string assetRoot, Manifest manifest)
        {
            foreach (var part in manifest.parts)
                ConfigureTexture(assetRoot + "/" + part.file, HairPivot(part, manifest));
            foreach (var expression in manifest.expressions ?? Array.Empty<Expression>())
                ConfigureTexture(assetRoot + "/" + expression.file, new Vector2(0.5f, 0.5f));
        }

        private static void ConfigureTexture(string assetPath, Vector2 pivot)
        {
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);
            var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
            if (!importer) throw new InvalidDataException("Sprite를 가져올 수 없습니다: " + assetPath);
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.spritePixelsPerUnit = PixelsPerUnit;
            importer.alphaIsTransparency = true;
            importer.mipmapEnabled = false;
            var settings = new TextureImporterSettings();
            importer.ReadTextureSettings(settings);
            settings.spriteAlignment = (int)SpriteAlignment.Custom;
            settings.spritePivot = pivot;
            importer.SetTextureSettings(settings);
            importer.SaveAndReimport();
        }

        private static Vector2 HairPivot(Part part, Manifest manifest)
        {
            if (string.IsNullOrEmpty(part.id) || !part.id.Contains("hair") || manifest.anchors == null || manifest.anchors.face == null)
                return new Vector2(0.5f, 0.5f);
            var x = Mathf.Clamp01((manifest.anchors.face.cx - part.left) / Mathf.Max(1f, part.width));
            var y = Mathf.Clamp01(1f - (manifest.anchors.hairRootY - part.top) / Mathf.Max(1f, part.height));
            return new Vector2(x, y);
        }

        private static string BuildPrefab(string assetRoot, Manifest manifest)
        {
            var root = new GameObject("RiggingV1Avatar");
            var controller = root.AddComponent<RiggingV1Avatar>();
            var eyesOpen = new List<SpriteRenderer>();
            var eyesClosed = new List<SpriteRenderer>();
            var hair = new List<Transform>();
            SpriteRenderer mouthOpen = null, mouthClosed = null;

            for (var i = 0; i < manifest.parts.Length; i++)
            {
                var part = manifest.parts[i];
                var renderer = CreateLayer(root.transform, assetRoot, part, i, HairPivot(part, manifest), manifest.canvas);
                if (part.id.StartsWith("eyewhite") || part.id.StartsWith("irides") || part.id == "eyelash") eyesOpen.Add(renderer);
                if (part.id == "mouth_open") mouthOpen = renderer;
                if (part.id.Contains("hair")) hair.Add(renderer.transform);
            }

            var expressions = manifest.expressions ?? Array.Empty<Expression>();
            for (var i = 0; i < expressions.Length; i++)
            {
                var expression = expressions[i];
                var renderer = CreateLayer(root.transform, assetRoot, expression, 1000 + i, new Vector2(0.5f, 0.5f), manifest.canvas);
                if (expression.id.StartsWith("eye_close")) eyesClosed.Add(renderer);
                if (expression.id == "mouth_close") mouthClosed = renderer;
            }

            controller.Configure(eyesOpen.ToArray(), eyesClosed.ToArray(), mouthOpen, mouthClosed, hair.ToArray());
            var prefabPath = assetRoot + "/RiggingV1Avatar.prefab";
            PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            UnityEngine.Object.DestroyImmediate(root);
            AssetDatabase.SaveAssets();
            return prefabPath;
        }

        private static SpriteRenderer CreateLayer(
            Transform parent, string assetRoot, LayerRecord record, int order, Vector2 pivot, CanvasInfo canvas)
        {
            var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(assetRoot + "/" + record.file);
            if (!sprite) throw new InvalidDataException("Sprite가 없습니다: " + record.file);
            var child = new GameObject(record.id);
            child.transform.SetParent(parent, false);
            child.transform.localPosition = new Vector3(
                (record.left + pivot.x * record.width - canvas.width * 0.5f) / PixelsPerUnit,
                (canvas.height * 0.5f - record.top - (1f - pivot.y) * record.height) / PixelsPerUnit,
                0f);
            var renderer = child.AddComponent<SpriteRenderer>();
            renderer.sprite = sprite;
            renderer.sortingOrder = order;
            return renderer;
        }

        private static string Sanitize(string name)
        {
            var invalid = Path.GetInvalidFileNameChars();
            return new string(name.Select(character => invalid.Contains(character) ? '_' : character).ToArray());
        }
    }
}
