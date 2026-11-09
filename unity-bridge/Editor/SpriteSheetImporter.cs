using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.U2D.Sprites;
using UnityEngine;

namespace SpriteLab.SpriteSheets.Editor
{
    /// <summary>Turns Sprite Lab game sheets (PNG + TexturePacker JSON hash) into sliced sprites, clips, a controller and a prefab.</summary>
    public static class SpriteSheetImporter
    {
        private const string Root = "Assets/SpriteLab/Sheets";
        private const float PixelsPerUnit = 100f;

        private sealed class Frame
        {
            public string name;
            public int x, y, w, h;
            public float pivotX, pivotY, durationMs;
        }

        private sealed class Sheet
        {
            public string action, jsonPath, imagePath;
            public List<Frame> frames = new List<Frame>();
            public bool loop;
            public float fps;
            public int width, height;
        }

        [MenuItem("Tools/Sprite Lab/Import Sprite Sheet JSON")]
        public static void ImportFileMenu()
        {
            var path = EditorUtility.OpenFilePanel("스프라이트 시트 JSON 선택", "", "json");
            if (!string.IsNullOrEmpty(path)) Run(() => ImportFile(path));
        }

        [MenuItem("Tools/Sprite Lab/Import Sprite Sheet Folder (One Character)")]
        public static void ImportFolderMenu()
        {
            var path = EditorUtility.OpenFolderPanel("한 캐릭터의 시트가 든 폴더 선택", "", "");
            if (!string.IsNullOrEmpty(path)) Run(() => ImportFolder(path));
        }

        private static void Run(Func<string> import)
        {
            try
            {
                var prefab = import();
                Selection.activeObject = AssetDatabase.LoadAssetAtPath<GameObject>(prefab);
                EditorGUIUtility.PingObject(Selection.activeObject);
                Debug.Log("Sprite sheet prefab: " + prefab);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                EditorUtility.DisplayDialog("스프라이트 시트 가져오기 실패", error.Message, "확인");
            }
            finally
            {
                EditorUtility.ClearProgressBar();
            }
        }

        public static string ImportFile(string jsonPath) =>
            Import(Path.GetFileNameWithoutExtension(jsonPath), new List<Sheet> { ReadSheet(jsonPath) });

        /// <summary>Every sheet in the folder becomes one action of one character. pack.json and other JSON files are ignored.</summary>
        public static string ImportFolder(string folder)
        {
            var sheets = new List<Sheet>();
            foreach (var path in Directory.GetFiles(folder, "*.json").OrderBy(item => item, StringComparer.Ordinal))
            {
                if (!(Json.Parse(File.ReadAllText(path)) is Dictionary<string, object> data) || !data.ContainsKey("frames")) continue;
                var sheet = ReadSheet(path);
                if (sheets.Any(item => item.action == sheet.action))
                {
                    Debug.LogWarning($"같은 동작이 여러 개라 앞의 것만 씁니다: {sheet.action} ({Path.GetFileName(path)} 제외)");
                    continue;
                }
                sheets.Add(sheet);
            }
            if (sheets.Count == 0) throw new InvalidDataException("폴더에 스프라이트 시트 JSON이 없습니다.");
            var full = new DirectoryInfo(folder);
            // pack_cli always writes to a folder called pack, so the character's name is one level up.
            var unit = full.Name.Equals("pack", StringComparison.OrdinalIgnoreCase) && full.Parent != null ? full.Parent.Name : full.Name;
            return Import(unit, sheets);
        }

        private static string Import(string unitName, List<Sheet> sheets)
        {
            var unit = Sanitize(unitName);
            var folder = Root + "/" + unit;
            Directory.CreateDirectory(Path.GetFullPath(folder));
            var images = new Dictionary<Sheet, string>();
            foreach (var sheet in sheets)
            {
                var name = Sanitize(sheet.action);
                images[sheet] = folder + "/" + name + ".png";
                File.Copy(sheet.imagePath, Path.GetFullPath(images[sheet]), true);
                File.Copy(sheet.jsonPath, Path.GetFullPath(folder + "/" + name + ".sheet.json"), true);
            }
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);

            var clips = new Dictionary<Sheet, AnimationClip>();
            var firstSprites = new Dictionary<Sheet, Sprite>();
            for (var i = 0; i < sheets.Count; i++)
            {
                var sheet = sheets[i];
                EditorUtility.DisplayProgressBar("Sprite Lab", sheet.action, i / (float)sheets.Count);
                Slice(images[sheet], sheet);
                var sprites = AssetDatabase.LoadAllAssetsAtPath(images[sheet]).OfType<Sprite>().ToDictionary(item => item.name);
                var missing = sheet.frames.FirstOrDefault(frame => !sprites.ContainsKey(frame.name));
                if (missing != null) throw new InvalidDataException("스프라이트가 만들어지지 않았습니다: " + missing.name);
                clips[sheet] = WriteClip(folder + "/" + Sanitize(sheet.action) + ".anim", sheet, sprites);
                firstSprites[sheet] = sprites[sheet.frames[0].name];
            }

            var standing = sheets.FirstOrDefault(item => item.action == "idle") ?? sheets.FirstOrDefault(item => item.loop) ?? sheets[0];
            var controller = WriteController(folder + "/" + unit + ".controller", sheets, clips, standing);
            var prefab = folder + "/" + unit + ".prefab";
            // A prefab that already exists may carry the game's own components, and the controller it points at keeps its GUID.
            if (AssetDatabase.LoadAssetAtPath<GameObject>(prefab) == null)
            {
                var root = new GameObject(unit);
                root.AddComponent<SpriteRenderer>().sprite = firstSprites[standing];
                root.AddComponent<Animator>().runtimeAnimatorController = controller;
                PrefabUtility.SaveAsPrefabAsset(root, prefab);
                UnityEngine.Object.DestroyImmediate(root);
            }
            AssetDatabase.SaveAssets();
            return prefab;
        }

        private static Sheet ReadSheet(string jsonPath)
        {
            if (!(Json.Parse(File.ReadAllText(jsonPath)) is Dictionary<string, object> data)
                || !(data.TryGetValue("frames", out var framesValue) && framesValue is Dictionary<string, object> frames)
                || !(data.TryGetValue("meta", out var metaValue) && metaValue is Dictionary<string, object> meta))
                throw new InvalidDataException("TexturePacker JSON Hash 형식이 아닙니다: " + Path.GetFileName(jsonPath));

            var imageName = Path.GetFileName(Text(meta, "image"));
            var sheet = new Sheet
            {
                jsonPath = jsonPath,
                imagePath = Path.Combine(Path.GetDirectoryName(jsonPath), imageName),
                loop = !meta.TryGetValue("loop", out var loopValue) || !(loopValue is bool loopFlag) || loopFlag,
                fps = Number(meta, "fps", 0f),
                action = Path.GetFileNameWithoutExtension(jsonPath),
            };
            if (!File.Exists(sheet.imagePath)) throw new FileNotFoundException("JSON 옆에 시트 PNG가 없습니다: " + imageName, sheet.imagePath);
            (sheet.width, sheet.height) = PngSize(sheet.imagePath);

            var names = frames.Keys.ToList();
            if (data.TryGetValue("animations", out var animationsValue) && animationsValue is Dictionary<string, object> animations && animations.Count > 0)
            {
                var first = animations.First();
                sheet.action = first.Key;
                names = ((List<object>)first.Value).Select(item => (string)item).ToList();
            }

            foreach (var name in names)
            {
                if (!frames.TryGetValue(name, out var value) || !(value is Dictionary<string, object> item))
                    throw new InvalidDataException("animations에 있는 프레임이 frames에 없습니다: " + name);
                if (Flag(item, "rotated") || Flag(item, "trimmed"))
                    throw new InvalidDataException("회전되거나 잘린 프레임은 지원하지 않습니다: " + name);
                var box = (Dictionary<string, object>)item["frame"];
                var pivot = item.TryGetValue("pivot", out var pivotValue) ? pivotValue as Dictionary<string, object> : null;
                var frame = new Frame
                {
                    name = name,
                    x = (int)Number(box, "x"), y = (int)Number(box, "y"), w = (int)Number(box, "w"), h = (int)Number(box, "h"),
                    pivotX = pivot != null ? Number(pivot, "x") : 0.5f,
                    pivotY = pivot != null ? Number(pivot, "y") : 0.5f,
                    durationMs = Mathf.Max(1f, Number(item, "duration", 100f)),
                };
                if (frame.x < 0 || frame.y < 0 || frame.x + frame.w > sheet.width || frame.y + frame.h > sheet.height)
                    throw new InvalidDataException("프레임이 PNG 밖으로 나갑니다: " + name);
                sheet.frames.Add(frame);
            }
            if (sheet.frames.Count == 0) throw new InvalidDataException("프레임이 없습니다: " + Path.GetFileName(jsonPath));
            return sheet;
        }

        // Sprite ids are kept by name, so clips and scenes that reference a frame survive a reimport.
        private static void Slice(string assetPath, Sheet sheet)
        {
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);
            var importer = (TextureImporter)AssetImporter.GetAtPath(assetPath);
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Multiple;
            importer.spritePixelsPerUnit = PixelsPerUnit;
            importer.alphaIsTransparency = true;
            importer.mipmapEnabled = false;
            importer.maxTextureSize = 8192;
            importer.SaveAndReimport();

            var factory = new SpriteDataProviderFactories();
            factory.Init();
            var provider = factory.GetSpriteEditorDataProviderFromObject(importer);
            provider.InitSpriteEditorDataProvider();
            var capability = provider.GetDataProvider<ISpriteFrameEditCapability>()?.GetEditCapability();
            if (capability == null
                || !capability.Value.HasCapability(EEditCapability.CreateAndDeleteSprite)
                || !capability.Value.HasCapability(EEditCapability.EditPivot))
                throw new InvalidOperationException("이 텍스처는 스프라이트 슬라이스를 지원하지 않습니다: " + assetPath);

            var known = provider.GetSpriteRects().GroupBy(item => item.name).ToDictionary(group => group.Key, group => group.First().spriteID);
            var rects = sheet.frames.Select(frame => new SpriteRect
            {
                name = frame.name,
                // JSON counts from the top-left, Unity from the bottom-left.
                rect = new Rect(frame.x, sheet.height - frame.y - frame.h, frame.w, frame.h),
                alignment = SpriteAlignment.Custom,
                pivot = new Vector2(frame.pivotX, 1f - frame.pivotY),
                spriteID = known.TryGetValue(frame.name, out var id) ? id : GUID.Generate(),
            }).ToArray();
            provider.SetSpriteRects(rects);
            provider.GetDataProvider<ISpriteNameFileIdDataProvider>()
                ?.SetNameFileIdPairs(rects.Select(item => new SpriteNameFileIdPair(item.name, item.spriteID)).ToList());
            provider.Apply();
            importer.SaveAndReimport();
        }

        private static AnimationClip WriteClip(string path, Sheet sheet, Dictionary<string, Sprite> sprites)
        {
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
            var isNew = clip == null;
            if (isNew) clip = new AnimationClip { name = Path.GetFileNameWithoutExtension(path) };

            // Whole milliseconds cannot land on a 36 fps grid, so a sheet with a set rate is timed by frame number.
            var times = new float[sheet.frames.Count + 1];
            for (var i = 0; i < sheet.frames.Count; i++)
                times[i + 1] = sheet.fps > 0f ? (i + 1) / sheet.fps : times[i] + sheet.frames[i].durationMs / 1000f;
            clip.frameRate = sheet.fps > 0f ? sheet.fps : Mathf.Max(12f, Mathf.Round(1000f / sheet.frames.Min(frame => frame.durationMs)));

            // Unity lengthens a sprite clip by one frame past its last key, so a last frame longer than that needs a key to hold it.
            var keys = sheet.frames.Select((frame, i) => new ObjectReferenceKeyframe { time = times[i], value = sprites[frame.name] }).ToList();
            var holdUntil = times[sheet.frames.Count] - 1f / clip.frameRate;
            if (holdUntil > times[sheet.frames.Count - 1] + 0.0005f)
                keys.Add(new ObjectReferenceKeyframe { time = holdUntil, value = keys[keys.Count - 1].value });
            var binding = EditorCurveBinding.PPtrCurve("", typeof(SpriteRenderer), "m_Sprite");
            AnimationUtility.SetObjectReferenceCurve(clip, binding, keys.ToArray());
            var settings = AnimationUtility.GetAnimationClipSettings(clip);
            settings.loopTime = sheet.loop;
            AnimationUtility.SetAnimationClipSettings(clip, settings);

            if (isNew) AssetDatabase.CreateAsset(clip, path);
            else EditorUtility.SetDirty(clip);
            return clip;
        }

        private static AnimatorController WriteController(string path, List<Sheet> sheets, Dictionary<Sheet, AnimationClip> clips, Sheet standing)
        {
            var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(path) ?? AnimatorController.CreateAnimatorControllerAtPath(path);
            var machine = controller.layers[0].stateMachine;
            foreach (var transition in machine.anyStateTransitions.ToArray()) machine.RemoveAnyStateTransition(transition);
            foreach (var child in machine.states.ToArray()) machine.RemoveState(child.state);
            foreach (var parameter in controller.parameters.ToArray()) controller.RemoveParameter(parameter);

            var states = new Dictionary<Sheet, AnimatorState>();
            foreach (var sheet in sheets)
            {
                var state = machine.AddState(sheet.action);
                state.motion = clips[sheet];
                states[sheet] = state;
                controller.AddParameter(sheet.action, AnimatorControllerParameterType.Trigger);
                var enter = machine.AddAnyStateTransition(state);
                enter.AddCondition(AnimatorConditionMode.If, 0f, sheet.action);
                enter.hasExitTime = false;
                enter.duration = 0f;
                enter.canTransitionToSelf = !sheet.loop;  // firing attack again restarts it, firing idle during idle does not
            }
            machine.defaultState = states[standing];
            foreach (var sheet in sheets.Where(item => !item.loop && item != standing))
            {
                var back = states[sheet].AddTransition(states[standing]);
                back.hasExitTime = true;
                back.exitTime = 1f;
                back.duration = 0f;
            }
            EditorUtility.SetDirty(controller);
            return controller;
        }

        private static (int, int) PngSize(string path)
        {
            var head = new byte[24];
            using (var stream = File.OpenRead(path))
                if (stream.Read(head, 0, 24) != 24 || head[1] != 'P' || head[2] != 'N' || head[3] != 'G')
                    throw new InvalidDataException("PNG 파일이 아닙니다: " + Path.GetFileName(path));
            return (head[16] << 24 | head[17] << 16 | head[18] << 8 | head[19], head[20] << 24 | head[21] << 16 | head[22] << 8 | head[23]);
        }

        private static string Sanitize(string name)
        {
            var invalid = Path.GetInvalidFileNameChars();
            var clean = new string(name.Select(character => invalid.Contains(character) ? '_' : character).ToArray()).Trim(' ', '.');
            if (clean.Length == 0) throw new InvalidDataException("사용할 수 없는 이름입니다: " + name);
            return clean;
        }

        private static string Text(Dictionary<string, object> data, string key) =>
            data.TryGetValue(key, out var value) && value is string text ? text : throw new InvalidDataException("JSON에 값이 없습니다: " + key);

        private static float Number(Dictionary<string, object> data, string key) =>
            data.TryGetValue(key, out var value) && value is double number ? (float)number : throw new InvalidDataException("JSON에 값이 없습니다: " + key);

        private static float Number(Dictionary<string, object> data, string key, float fallback) =>
            data.TryGetValue(key, out var value) && value is double number ? (float)number : fallback;

        private static bool Flag(Dictionary<string, object> data, string key) => data.TryGetValue(key, out var value) && value is bool flag && flag;

        // JsonUtility cannot read a hash keyed by frame name, and Newtonsoft is not always installed.
        private sealed class Json
        {
            private readonly string text;
            private int at;

            private Json(string source) { text = source; }

            public static object Parse(string source)
            {
                var reader = new Json(source.TrimStart('﻿'));
                var value = reader.Value();
                reader.Space();
                if (reader.at != reader.text.Length) throw reader.Bad();
                return value;
            }

            private InvalidDataException Bad() => new InvalidDataException("JSON을 읽을 수 없습니다 (위치 " + at + ").");

            private void Space() { while (at < text.Length && char.IsWhiteSpace(text[at])) at++; }

            private bool Take(char character)
            {
                Space();
                if (at >= text.Length || text[at] != character) return false;
                at++;
                return true;
            }

            private void Need(char character) { if (!Take(character)) throw Bad(); }

            private object Value()
            {
                Space();
                if (at >= text.Length) throw Bad();
                switch (text[at])
                {
                    case '{': return Dictionary();
                    case '[': return Array();
                    case '"': return String();
                    case 't': return Word("true", true);
                    case 'f': return Word("false", false);
                    case 'n': return Word("null", null);
                    default: return Number();
                }
            }

            private object Word(string word, object value)
            {
                if (string.CompareOrdinal(text, at, word, 0, word.Length) != 0) throw Bad();
                at += word.Length;
                return value;
            }

            private Dictionary<string, object> Dictionary()
            {
                var result = new Dictionary<string, object>();
                Need('{');
                if (Take('}')) return result;
                do
                {
                    Space();
                    var key = String();
                    Need(':');
                    result[key] = Value();
                } while (Take(','));
                Need('}');
                return result;
            }

            private List<object> Array()
            {
                var result = new List<object>();
                Need('[');
                if (Take(']')) return result;
                do result.Add(Value()); while (Take(','));
                Need(']');
                return result;
            }

            private string String()
            {
                if (at >= text.Length || text[at] != '"') throw Bad();
                var result = new StringBuilder();
                for (at++; at < text.Length; at++)
                {
                    var character = text[at];
                    if (character == '"') { at++; return result.ToString(); }
                    if (character != '\\') { result.Append(character); continue; }
                    if (++at >= text.Length) throw Bad();
                    switch (text[at])
                    {
                        case 'n': result.Append('\n'); break;
                        case 't': result.Append('\t'); break;
                        case 'r': result.Append('\r'); break;
                        case 'b': result.Append('\b'); break;
                        case 'f': result.Append('\f'); break;
                        case 'u':
                            if (at + 4 >= text.Length) throw Bad();
                            result.Append((char)int.Parse(text.Substring(at + 1, 4), NumberStyles.HexNumber, CultureInfo.InvariantCulture));
                            at += 4;
                            break;
                        default: result.Append(text[at]); break;
                    }
                }
                throw Bad();
            }

            private object Number()
            {
                var start = at;
                while (at < text.Length && "+-.0123456789eE".IndexOf(text[at]) >= 0) at++;
                if (!double.TryParse(text.Substring(start, at - start), NumberStyles.Float, CultureInfo.InvariantCulture, out var number)) throw Bad();
                return number;
            }
        }
    }
}
