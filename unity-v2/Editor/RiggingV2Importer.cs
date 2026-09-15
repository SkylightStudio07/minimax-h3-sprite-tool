using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using SpriteLab.RiggingV1;
using SpriteLab.RiggingV2;
using UnityEditor;
using UnityEditor.U2D.Sprites;
using UnityEngine;
using UnityEngine.U2D;
using UnityEngine.U2D.Animation;

namespace SpriteLab.RiggingV2.Editor
{
    public static class RiggingV2Importer
    {
        private const float PixelsPerUnit = 100f;

        [Serializable] private sealed class Manifest { public CanvasInfo canvas; public Part[] parts; public Expression[] expressions; public string[] layerOrder; }
        [Serializable] private sealed class CanvasInfo { public int width; public int height; }
        [Serializable] private class LayerRecord { public string id; public string file; public int left; public int top; public int width; public int height; }
        [Serializable] private sealed class Part : LayerRecord { public string runtimeName; }
        [Serializable] private sealed class Expression : LayerRecord { public string side; public string fade; }
        [Serializable] private sealed class RigData { public int sourceRevision; public BoneRecord[] bones; public MeshSettings mesh; public string[] warnings; }
        [Serializable] private sealed class BoneRecord { public string name; public string parent; public float x; public float y; public float length; }
        [Serializable] private sealed class MeshSettings { public int columns = 5; public int rows = 5; public int maxInfluences = 2; }

        [MenuItem("Tools/Sprite Lab/Import Rigging V2 ZIP")]
        public static void ImportZip()
        {
            var zipPath = EditorUtility.OpenFilePanel("Rigging V2 ZIP 선택", "", "zip");
            if (string.IsNullOrEmpty(zipPath)) return;
            try
            {
                var prefabPath = ImportZipAtPath(zipPath);
                Selection.activeObject = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                EditorGUIUtility.PingObject(Selection.activeObject);
                Debug.Log("Rigging V2 prefab 생성: " + prefabPath);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                EditorUtility.DisplayDialog("Rigging V2 가져오기 실패", error.Message, "확인");
            }
        }

        public static string ImportZipAtPath(string zipPath)
        {
            if (string.IsNullOrWhiteSpace(zipPath) || !File.Exists(zipPath))
                throw new FileNotFoundException("Rigging V2 ZIP을 찾을 수 없습니다.", zipPath);
            var folderName = Sanitize(Path.GetFileNameWithoutExtension(zipPath)) + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss");
            var assetRoot = "Assets/RiggingV2/Imported/" + folderName;
            var diskRoot = Path.GetFullPath(assetRoot);
            Directory.CreateDirectory(diskRoot);
            ExtractAllowedFiles(zipPath, diskRoot);
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(diskRoot, "manifest.json")));
            var rig = JsonUtility.FromJson<RigData>(File.ReadAllText(Path.Combine(diskRoot, "rig-v2.json")));
            if (manifest == null || manifest.canvas == null || manifest.parts == null || rig == null || rig.bones == null || rig.bones.Length < 5)
                throw new InvalidDataException("V2 manifest 형식이 올바르지 않습니다.");

            foreach (var part in manifest.parts)
                ConfigureTexture(assetRoot + "/" + part.file, part, rig);
            foreach (var expression in manifest.expressions ?? Array.Empty<Expression>())
                ConfigurePlainTexture(assetRoot + "/" + expression.file);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            return BuildPrefab(assetRoot, manifest, rig);
        }

        private static void ExtractAllowedFiles(string zipPath, string diskRoot)
        {
            var rootWithSeparator = diskRoot.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            using var archive = ZipFile.OpenRead(zipPath);
            foreach (var entry in archive.Entries)
            {
                var normalized = entry.FullName.Replace('\\', '/');
                if (!(normalized == "manifest.json" || normalized == "rig-v2.json" || normalized.StartsWith("layers/") || normalized.StartsWith("expressions/")))
                    continue;
                var target = Path.GetFullPath(Path.Combine(diskRoot, normalized.Replace('/', Path.DirectorySeparatorChar)));
                if (!target.StartsWith(rootWithSeparator, StringComparison.OrdinalIgnoreCase) && target != diskRoot)
                    throw new InvalidDataException("ZIP 경로가 출력 폴더를 벗어납니다.");
                if (string.IsNullOrEmpty(entry.Name)) { Directory.CreateDirectory(target); continue; }
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                entry.ExtractToFile(target, true);
            }
        }

        private static void ConfigurePlainTexture(string assetPath)
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
            settings.spriteAlignment = (int)SpriteAlignment.Center;
            settings.spritePivot = new Vector2(0.5f, 0.5f);
            settings.spriteMeshType = SpriteMeshType.FullRect;
            importer.SetTextureSettings(settings);
            importer.SaveAndReimport();
        }

        private static void ConfigureTexture(string assetPath, Part part, RigData rig)
        {
            ConfigurePlainTexture(assetPath);
            var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
            var factory = new SpriteDataProviderFactories();
            factory.Init();
            var provider = factory.GetSpriteEditorDataProviderFromObject(importer);
            provider.InitSpriteEditorDataProvider();
            var spriteRect = provider.GetSpriteRects().Single();
            var boneProvider = provider.GetDataProvider<ISpriteBoneDataProvider>();
            var meshProvider = provider.GetDataProvider<ISpriteMeshDataProvider>();
            if (boneProvider == null || meshProvider == null)
                throw new InvalidOperationException("Unity 2D Animation Sprite 데이터 공급자를 찾을 수 없습니다.");
            boneProvider.SetBones(spriteRect.spriteID, BuildSpriteBones(part, rig));
            BuildMesh(part, rig, out var vertices, out var indices, out var edges);
            meshProvider.SetVertices(spriteRect.spriteID, vertices);
            meshProvider.SetIndices(spriteRect.spriteID, indices);
            meshProvider.SetEdges(spriteRect.spriteID, edges);
            provider.Apply();
            importer.SaveAndReimport();
        }

        private static List<SpriteBone> BuildSpriteBones(Part part, RigData rig)
        {
            var indices = rig.bones.Select((bone, index) => new { bone.name, index }).ToDictionary(item => item.name, item => item.index);
            var output = new List<SpriteBone>();
            foreach (var bone in rig.bones)
            {
                var parentId = string.IsNullOrEmpty(bone.parent) ? -1 : indices[bone.parent];
                Vector3 position;
                if (parentId < 0)
                    position = new Vector3(bone.x - part.left, part.top + part.height - bone.y, 0f);
                else
                {
                    var parent = rig.bones[parentId];
                    position = new Vector3(bone.x - parent.x, parent.y - bone.y, 0f);
                }
                output.Add(new SpriteBone
                {
                    name = bone.name,
                    guid = GUID.Generate().ToString(),
                    position = position,
                    rotation = Quaternion.identity,
                    length = Mathf.Max(1f, bone.length),
                    parentId = parentId,
                    color = new Color32(151, 226, 255, 255),
                });
            }
            return output;
        }

        private static void BuildMesh(Part part, RigData rig, out Vertex2DMetaData[] vertices, out int[] indices, out Vector2Int[] edges)
        {
            var columns = Mathf.Clamp(rig.mesh != null ? rig.mesh.columns : 5, 2, 12);
            var rows = Mathf.Clamp(rig.mesh != null ? rig.mesh.rows : 5, 2, 12);
            vertices = new Vertex2DMetaData[columns * rows];
            for (var row = 0; row < rows; row++)
            for (var column = 0; column < columns; column++)
            {
                var x = (part.width - 1f) * column / (columns - 1f);
                var y = (part.height - 1f) * row / (rows - 1f);
                var canvasX = part.left + x;
                var canvasY = part.top + part.height - y;
                vertices[row * columns + column] = new Vertex2DMetaData { position = new Vector2(x, y), boneWeight = WeightFor(part, rig, canvasX, canvasY) };
            }
            var triangles = new List<int>();
            var edgeSet = new HashSet<string>();
            var edgeList = new List<Vector2Int>();
            Action<int, int> addEdge = (a, b) =>
            {
                if (a > b) { var swap = a; a = b; b = swap; }
                if (edgeSet.Add(a + ":" + b)) edgeList.Add(new Vector2Int(a, b));
            };
            for (var row = 0; row < rows - 1; row++)
            for (var column = 0; column < columns - 1; column++)
            {
                var a = row * columns + column;
                var b = a + 1;
                var c = a + columns;
                var d = c + 1;
                triangles.AddRange(new[] { a, c, b, b, c, d });
                addEdge(a, b); addEdge(a, c); addEdge(b, c); addEdge(b, d); addEdge(c, d);
            }
            indices = triangles.ToArray();
            edges = edgeList.ToArray();
        }

        private static BoneWeight WeightFor(Part part, RigData rig, float x, float y)
        {
            var names = InfluenceNames(part, rig);
            var candidates = rig.bones.Select((bone, index) => new { bone, index })
                .Where(item => names.Contains(item.bone.name))
                .Select(item => new { item.index, distance = Mathf.Sqrt(Mathf.Pow(x - item.bone.x, 2f) + Mathf.Pow(y - item.bone.y, 2f)) })
                .OrderBy(item => item.distance).Take(2).ToArray();
            if (candidates.Length == 0) candidates = new[] { new { index = 0, distance = 0f } };
            var first = 1f / Mathf.Max(4f, candidates[0].distance);
            var second = candidates.Length > 1 ? 1f / Mathf.Max(4f, candidates[1].distance) : 0f;
            var total = first + second;
            return new BoneWeight
            {
                boneIndex0 = candidates[0].index,
                weight0 = first / total,
                boneIndex1 = candidates.Length > 1 ? candidates[1].index : candidates[0].index,
                weight1 = second / total,
            };
        }

        private static HashSet<string> InfluenceNames(Part part, RigData rig)
        {
            var id = (part.id ?? string.Empty).ToLowerInvariant();
            if (id.Contains("eye") || id.Contains("iride") || id.Contains("lash") || id.Contains("brow") || id.Contains("nose") || id.Contains("mouth") || id == "face")
                return Names("head");
            if (id.Contains("hair") || id.Contains("headwear") || id == "ears")
                return Names("head", "neck", "chest");
            if (id.Contains("neck")) return Names("neck", "chest");
            if (id.Contains("hand") || id.Contains("arm"))
            {
                var side = part.left + part.width * 0.5f < rig.bones[0].x ? "l" : "r";
                return Names("shoulder_" + side, "arm_" + side, "hand_" + side, "chest");
            }
            if (id.Contains("leg") || id.Contains("foot") || id.Contains("shoe"))
                return Names("hips", "leg_l", "knee_l", "foot_l", "leg_r", "knee_r", "foot_r");
            if (id.Contains("bottom") || id.Contains("skirt")) return Names("hips", "leg_l", "leg_r", "spine", "skirt_c", "skirt_l", "skirt_r");
            if (id.Contains("top") || id.Contains("object"))
                return Names("hips", "spine", "chest", "neck", "shoulder_l", "shoulder_r", "hand_l", "hand_r");
            return Names("hips", "spine", "chest", "neck", "head", "leg_l", "leg_r");
        }

        private static HashSet<string> Names(params string[] values) => new HashSet<string>(values);

        private static string BuildPrefab(string assetRoot, Manifest manifest, RigData rig)
        {
            var root = new GameObject("RiggingV2Avatar");
            var boneRoot = new GameObject("Skeleton").transform;
            boneRoot.SetParent(root.transform, false);
            var bones = CreateBoneHierarchy(boneRoot, manifest.canvas, rig);
            var controller = root.AddComponent<RiggingV1Avatar>();
            var v2Controller = root.AddComponent<RiggingV2Avatar>();
            var eyesOpen = new List<SpriteRenderer>();
            var eyesClosed = new List<SpriteRenderer>();
            var hair = new List<Transform>();
            var equipment = new List<Transform>();
            var cloth = new List<Transform>();
            SpriteRenderer mouthOpen = null, mouthClosed = null;
            var layerOrder = (manifest.layerOrder ?? Array.Empty<string>())
                .Select((key, index) => new { key, index }).ToDictionary(item => item.key, item => item.index);

            for (var i = 0; i < manifest.parts.Length; i++)
            {
                var part = manifest.parts[i];
                var order = layerOrder.TryGetValue("part:" + part.id, out var savedOrder) ? savedOrder : i;
                var renderer = CreateLayer(root.transform, assetRoot, part, order, manifest.canvas);
                BindSkin(renderer.gameObject, bones);
                if (part.id.StartsWith("eyewhite") || part.id.StartsWith("irides") || part.id.StartsWith("eyelash")) eyesOpen.Add(renderer);
                if (part.id == "mouth_open") mouthOpen = renderer;
                if (part.id.Contains("hair")) hair.Add(renderer.transform);
                if (part.id.Contains("object")) equipment.Add(renderer.transform);
                if (part.id.Contains("bottom") || part.id.Contains("skirt")) cloth.Add(renderer.transform);
            }
            var head = bones[Array.FindIndex(rig.bones, bone => bone.name == "head")];
            var expressions = manifest.expressions ?? Array.Empty<Expression>();
            for (var i = 0; i < expressions.Length; i++)
            {
                var expression = expressions[i];
                var order = layerOrder.TryGetValue("expression:" + expression.id, out var savedOrder) ? savedOrder : 1000 + i;
                var renderer = CreateLayer(root.transform, assetRoot, expression, order, manifest.canvas);
                renderer.transform.SetParent(head, true);
                if (expression.id == "eye_open_original") eyesOpen.Add(renderer);
                if (expression.id.StartsWith("eye_close")) eyesClosed.Add(renderer);
                if (expression.id == "mouth_open") mouthOpen = renderer;
                if (expression.id == "mouth_close") mouthClosed = renderer;
            }
            controller.Configure(eyesOpen.ToArray(), eyesClosed.ToArray(), mouthOpen, mouthClosed, hair.ToArray(), equipment.ToArray(), cloth.ToArray());
            v2Controller.Configure(FindBone(rig, bones, "hips"), FindBone(rig, bones, "spine"), FindBone(rig, bones, "chest"), FindBone(rig, bones, "neck"), head,
                FindBoneOrNull(rig, bones, "skirt_c"), FindBoneOrNull(rig, bones, "skirt_l"), FindBoneOrNull(rig, bones, "skirt_r"),
                FindBoneOrNull(rig, bones, "leg_l"), FindBoneOrNull(rig, bones, "leg_r"));
            var prefabPath = assetRoot + "/RiggingV2Avatar.prefab";
            PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            UnityEngine.Object.DestroyImmediate(root);
            AssetDatabase.SaveAssets();
            return prefabPath;
        }

        private static Transform[] CreateBoneHierarchy(Transform parent, CanvasInfo canvas, RigData rig)
        {
            var output = new Transform[rig.bones.Length];
            var indexByName = rig.bones.Select((bone, index) => new { bone.name, index }).ToDictionary(item => item.name, item => item.index);
            for (var i = 0; i < rig.bones.Length; i++)
            {
                var record = rig.bones[i];
                var bone = new GameObject(record.name).transform;
                var parentIndex = string.IsNullOrEmpty(record.parent) ? -1 : indexByName[record.parent];
                bone.SetParent(parentIndex < 0 ? parent : output[parentIndex], false);
                if (parentIndex < 0)
                    bone.localPosition = CanvasToWorld(record.x, record.y, canvas);
                else
                {
                    var owner = rig.bones[parentIndex];
                    bone.localPosition = new Vector3((record.x - owner.x) / PixelsPerUnit, (owner.y - record.y) / PixelsPerUnit, 0f);
                }
                output[i] = bone;
            }
            return output;
        }

        private static Vector3 CanvasToWorld(float x, float y, CanvasInfo canvas) =>
            new Vector3((x - canvas.width * 0.5f) / PixelsPerUnit, (canvas.height * 0.5f - y) / PixelsPerUnit, 0f);

        private static SpriteRenderer CreateLayer(Transform parent, string assetRoot, LayerRecord record, int order, CanvasInfo canvas)
        {
            var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(assetRoot + "/" + record.file);
            if (!sprite) throw new InvalidDataException("Sprite가 없습니다: " + record.file);
            var child = new GameObject(record.id);
            child.transform.SetParent(parent, false);
            child.transform.localPosition = new Vector3(
                (record.left + record.width * 0.5f - canvas.width * 0.5f) / PixelsPerUnit,
                (canvas.height * 0.5f - record.top - record.height * 0.5f) / PixelsPerUnit, 0f);
            var renderer = child.AddComponent<SpriteRenderer>();
            renderer.sprite = sprite;
            renderer.sortingOrder = order;
            return renderer;
        }

        private static void BindSkin(GameObject target, Transform[] bones)
        {
            var skin = target.AddComponent<SpriteSkin>();
            var serialized = new SerializedObject(skin);
            serialized.FindProperty("m_RootBone").objectReferenceValue = bones[0];
            var boneArray = serialized.FindProperty("m_BoneTransforms");
            boneArray.arraySize = bones.Length;
            for (var i = 0; i < bones.Length; i++) boneArray.GetArrayElementAtIndex(i).objectReferenceValue = bones[i];
            serialized.ApplyModifiedPropertiesWithoutUndo();
            skin.alwaysUpdate = true;
        }

        private static Transform FindBone(RigData rig, Transform[] bones, string name) => bones[Array.FindIndex(rig.bones, bone => bone.name == name)];
        private static Transform FindBoneOrNull(RigData rig, Transform[] bones, string name)
        {
            var index = Array.FindIndex(rig.bones, bone => bone.name == name);
            return index >= 0 ? bones[index] : null;
        }
        private static string Sanitize(string name)
        {
            var invalid = Path.GetInvalidFileNameChars();
            return new string(name.Select(character => invalid.Contains(character) ? '_' : character).ToArray());
        }
    }
}
