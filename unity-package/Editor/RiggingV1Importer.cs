using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using SpriteLab.RiggingV1;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace SpriteLab.RiggingV1.Editor
{
    public static class RiggingV1Importer
    {
        private static float PixelsPerUnit = 100f;

        [Serializable] private sealed class Manifest
        {
            public CanvasInfo canvas;
            public Part[] parts;
            public Expression[] expressions;
            public string[] layerOrder;
            public Anchors anchors;
            public float unityPixelsPerUnit;
        }

        [Serializable] private sealed class CanvasInfo { public int width; public int height; }
        [Serializable] private sealed class FaceAnchor { public float cx; public float cy; }
        [Serializable] private sealed class Anchors { public FaceAnchor face; public FaceAnchor neckPivot; public FaceAnchor bodyPivot; public float hairRootY; }

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
            public string variantOf;
            public string sourceLayerName;
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
            var manifest = ReadManifest(diskRoot);

            var prefabPath = BuildFromFolder(assetRoot, manifest);
            Debug.Log("Rigging V1 prefab 생성: " + prefabPath);
            return prefabPath;
        }

        // Writing to the same prefab path keeps its GUID, so scenes that use it stay linked.
        [MenuItem("Tools/Sprite Lab/Reimport Selected Rigging V1 Folder")]
        public static void ReimportSelectedFolder()
        {
            var assetRoot = SelectedImportFolder();
            if (assetRoot == null) return;
            Debug.Log("Rigging V1 prefab 다시 생성: " + ReimportFolder(assetRoot));
        }

        [MenuItem("Tools/Sprite Lab/Update Selected Rigging V1 Folder From ZIP")]
        public static void UpdateSelectedFolderFromZip()
        {
            var assetRoot = SelectedImportFolder();
            if (assetRoot == null) return;
            var zipPath = EditorUtility.OpenFilePanel("새 Rigging V1 ZIP 선택", "", "zip");
            if (string.IsNullOrEmpty(zipPath)) return;
            Debug.Log("Rigging V1 prefab 갱신: " + UpdateFolderFromZip(assetRoot, zipPath));
        }

        public static string ReimportFolder(string assetRoot) => BuildFromFolder(assetRoot, ReadManifest(Path.GetFullPath(assetRoot)));

        public static string UpdateFolderFromZip(string assetRoot, string zipPath)
        {
            ExtractAllowedFiles(zipPath, Path.GetFullPath(assetRoot));
            return ReimportFolder(assetRoot);
        }

        private static string SelectedImportFolder()
        {
            var assetRoot = AssetDatabase.GetAssetPath(Selection.activeObject);
            if (!string.IsNullOrEmpty(assetRoot) && AssetDatabase.IsValidFolder(assetRoot) && File.Exists(Path.Combine(Path.GetFullPath(assetRoot), "manifest.json")))
                return assetRoot;
            EditorUtility.DisplayDialog("Rigging V1", "manifest.json이 있는 가져오기 폴더를 Project 창에서 선택하세요.", "확인");
            return null;
        }

        private static Manifest ReadManifest(string diskRoot)
        {
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(diskRoot, "manifest.json")));
            if (manifest == null || manifest.canvas == null || manifest.parts == null)
                throw new InvalidDataException("manifest.json 형식이 올바르지 않습니다.");
            return manifest;
        }

        private static string BuildFromFolder(string assetRoot, Manifest manifest)
        {
            PixelsPerUnit = manifest.unityPixelsPerUnit > 0f ? manifest.unityPixelsPerUnit : 100f;
            ConfigureTextures(assetRoot, manifest);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            return BuildPrefab(assetRoot, manifest);
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
                ConfigureTexture(assetRoot + "/" + part.file, PartPivot(assetRoot, part, manifest));
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
            importer.maxTextureSize = 8192;
            var settings = new TextureImporterSettings();
            importer.ReadTextureSettings(settings);
            settings.spriteAlignment = (int)SpriteAlignment.Custom;
            settings.spritePivot = pivot;
            importer.SetTextureSettings(settings);
            importer.SaveAndReimport();
        }

        private static Vector2 PartPivot(string assetRoot, Part part, Manifest manifest)
        {
            if (string.IsNullOrEmpty(part.id)) return new Vector2(0.5f, 0.5f);
            if (IsCloth(part.id)) return new Vector2(0.5f, 1f);          // hangs from the waist
            if (IsEquipment(part.id)) return GripPivot(assetRoot, part, manifest);
            return HairPivot(part, manifest);
        }

        private static bool IsCloth(string id) => id.Contains("bottom") || id.Contains("skirt");
        private static bool IsEquipment(string id) => id.Contains("object");

        // A held object turns around the hand that overlaps it, else around its point nearest the body.
        private static Vector2 GripPivot(string assetRoot, Part part, Manifest manifest)
        {
            var center = new Vector2(0.5f, 0.5f);
            var item = LoadAlpha(assetRoot, part);
            if (item == null) return center;
            var hits = Vector2.zero;
            var count = 0;
            foreach (var hand in manifest.parts.Where(other => other.id != null && other.id.Contains("handwear")))
            {
                var alpha = LoadAlpha(assetRoot, hand);
                if (alpha == null) continue;
                for (var y = Mathf.Max(part.top, hand.top); y < Mathf.Min(part.top + part.height, hand.top + hand.height); y++)
                    for (var x = Mathf.Max(part.left, hand.left); x < Mathf.Min(part.left + part.width, hand.left + hand.width); x++)
                        if (item[(y - part.top) * part.width + x - part.left] > 64 && alpha[(y - hand.top) * hand.width + x - hand.left] > 64)
                        {
                            hits += new Vector2(x, y);
                            count++;
                        }
            }
            Vector2 point;
            if (count >= 8) point = hits / count;
            else
            {
                var neck = manifest.anchors?.neckPivot;
                if (neck == null || neck.cy <= 0f) return center;
                var target = new Vector2(neck.cx, neck.cy);
                var best = float.MaxValue;
                point = new Vector2(part.left + part.width * 0.5f, part.top + part.height * 0.5f);
                for (var y = 0; y < part.height; y++)
                    for (var x = 0; x < part.width; x++)
                    {
                        if (item[y * part.width + x] <= 64) continue;
                        var candidate = new Vector2(part.left + x, part.top + y);
                        var distance = (candidate - target).sqrMagnitude;
                        if (distance < best) { best = distance; point = candidate; }
                    }
            }
            return new Vector2(Mathf.Clamp01((point.x - part.left) / Mathf.Max(1f, part.width)), Mathf.Clamp01(1f - (point.y - part.top) / Mathf.Max(1f, part.height)));
        }

        // Alpha in top-to-bottom rows matching the manifest's pixel box, or null if the PNG does not match it.
        private static byte[] LoadAlpha(string assetRoot, LayerRecord record)
        {
            var path = Path.GetFullPath(assetRoot + "/" + record.file);
            if (!File.Exists(path)) return null;
            var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            try
            {
                if (!texture.LoadImage(File.ReadAllBytes(path)) || texture.width != record.width || texture.height != record.height) return null;
                var pixels = texture.GetPixels32();
                var alpha = new byte[pixels.Length];
                for (var y = 0; y < record.height; y++)
                    for (var x = 0; x < record.width; x++)
                        alpha[y * record.width + x] = pixels[(record.height - 1 - y) * record.width + x].a;
                return alpha;
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(texture);
            }
        }

        private static Vector2 HairPivot(Part part, Manifest manifest)
        {
            if (!part.id.Contains("hair") || manifest.anchors == null || manifest.anchors.face == null)
                return new Vector2(0.5f, 0.5f);
            var x = Mathf.Clamp01((manifest.anchors.face.cx - part.left) / Mathf.Max(1f, part.width));
            var y = Mathf.Clamp01(1f - (manifest.anchors.hairRootY - part.top) / Mathf.Max(1f, part.height));
            return new Vector2(x, y);
        }

        private static bool IsHeadLayer(string id)
        {
            if (id.StartsWith("neck")) return false;
            return id.Contains("hair") || id.Contains("headwear") || new[] { "face", "nose", "ear", "eye", "iris", "irides", "mouth" }.Any(id.StartsWith);
        }

        private static Transform Group(Transform parent, string name, FaceAnchor anchor)
        {
            var group = new GameObject(name).transform;
            group.position = new Vector3(anchor.cx / PixelsPerUnit, anchor.cy / PixelsPerUnit, 0f);
            group.SetParent(parent, true);
            return group;
        }

        private static string BuildPrefab(string assetRoot, Manifest manifest)
        {
            var root = new GameObject("RiggingV1Avatar");
            root.AddComponent<SortingGroup>();
            var controller = root.AddComponent<RiggingV1Avatar>();
            var eyesOpen = new List<SpriteRenderer>();
            var eyesClosed = new List<SpriteRenderer>();
            var hair = new List<Transform>();
            var equipment = new List<Transform>();
            var cloth = new List<Transform>();
            var slots = new Dictionary<string, SpriteRenderer>();
            SpriteRenderer mouthOpen = null, mouthClosed = null;
            var layerOrder = (manifest.layerOrder ?? Array.Empty<string>())
                .Select((key, index) => new { key, index }).ToDictionary(item => item.key, item => item.index);

            // Older manifests have no neck anchor; their layers stay flat and simply do not get head motion.
            var anchors = manifest.anchors;
            var hasBody = anchors != null && anchors.neckPivot != null && anchors.bodyPivot != null && anchors.neckPivot.cy > 0f;
            var canvas = manifest.canvas;
            FaceAnchor Local(FaceAnchor a) => new FaceAnchor { cx = a.cx - canvas.width * 0.5f, cy = canvas.height * 0.5f - a.cy };
            var bodyGroup = hasBody ? Group(root.transform, "Body", Local(anchors.bodyPivot)) : root.transform;
            var headGroup = hasBody ? Group(bodyGroup, "Head", Local(anchors.neckPivot)) : root.transform;

            for (var i = 0; i < manifest.parts.Length; i++)
            {
                var part = manifest.parts[i];
                var order = layerOrder.TryGetValue("part:" + part.id, out var savedOrder) ? savedOrder : i;
                var renderer = CreateLayer(IsHeadLayer(part.id) ? headGroup : bodyGroup, assetRoot, part, order, PartPivot(assetRoot, part, manifest), canvas);
                slots["part:" + part.id] = renderer;
                if (part.id.StartsWith("eyewhite") || part.id.StartsWith("irides") || part.id.StartsWith("eyelash")) eyesOpen.Add(renderer);
                if (part.id == "mouth_open") mouthOpen = renderer;
                if (part.id.Contains("hair")) hair.Add(renderer.transform);
                if (IsEquipment(part.id)) equipment.Add(renderer.transform);
                if (IsCloth(part.id)) cloth.Add(renderer.transform);
            }

            var expressions = manifest.expressions ?? Array.Empty<Expression>();
            var center = new Vector2(0.5f, 0.5f);
            for (var i = 0; i < expressions.Length; i++)
            {
                var expression = expressions[i];
                if (!string.IsNullOrEmpty(expression.variantOf)) continue;
                var order = layerOrder.TryGetValue("expression:" + expression.id, out var savedOrder) ? savedOrder : 1000 + i;
                var renderer = CreateLayer(headGroup, assetRoot, expression, order, center, canvas);
                slots["expression:" + expression.id] = renderer;
                if (expression.id == "eye_open_original") eyesOpen.Add(renderer);
                if (expression.id.StartsWith("eye_close")) eyesClosed.Add(renderer);
                if (expression.id == "mouth_open") mouthOpen = renderer;
                if (expression.id == "mouth_close") mouthClosed = renderer;
            }

            var variants = new List<ExpressionVariant>();
            foreach (var expression in expressions.Where(item => !string.IsNullOrEmpty(item.variantOf)))
            {
                if (!slots.TryGetValue(expression.variantOf, out var slot)) continue;
                var renderer = CreateLayer(slot.transform.parent, assetRoot, expression, slot.sortingOrder, center, canvas);
                renderer.enabled = false;
                variants.Add(new ExpressionVariant { name = VariantName(expression), slot = expression.variantOf, renderer = renderer, slotRenderer = slot });
            }

            controller.Configure(eyesOpen.ToArray(), eyesClosed.ToArray(), mouthOpen, mouthClosed, hair.ToArray(), equipment.ToArray(), cloth.ToArray(),
                hasBody ? headGroup : null, hasBody ? bodyGroup : null, variants.ToArray());
            var prefabPath = assetRoot + "/RiggingV1Avatar.prefab";
            PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            UnityEngine.Object.DestroyImmediate(root);
            AssetDatabase.SaveAssets();
            return prefabPath;
        }

        private static string VariantName(Expression expression)
        {
            const string prefix = "차분 · ";
            var name = expression.sourceLayerName ?? "";
            return name.StartsWith(prefix) ? name.Substring(prefix.Length) : (string.IsNullOrEmpty(name) ? expression.id : name);
        }

        private static SpriteRenderer CreateLayer(
            Transform parent, string assetRoot, LayerRecord record, int order, Vector2 pivot, CanvasInfo canvas)
        {
            var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(assetRoot + "/" + record.file);
            if (!sprite) throw new InvalidDataException("Sprite가 없습니다: " + record.file);
            var child = new GameObject(record.id);
            // Placed in canvas space while the prefab root is at the origin, then parented, so groups do not move layers.
            child.transform.position = new Vector3(
                (record.left + pivot.x * record.width - canvas.width * 0.5f) / PixelsPerUnit,
                (canvas.height * 0.5f - record.top - (1f - pivot.y) * record.height) / PixelsPerUnit,
                0f);
            child.transform.SetParent(parent, true);
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
