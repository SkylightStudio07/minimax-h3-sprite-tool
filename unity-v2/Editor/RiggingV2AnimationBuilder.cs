using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using SpriteLab.RiggingV2;
using UnityEditor;
using UnityEngine;

namespace SpriteLab.RiggingV2.Editor
{
    public static class RiggingV2AnimationBuilder
    {
        [Serializable] public sealed class ClipRecord { public string id, name, easing; public int fps, frames; public bool loop; public Track[] tracks; }
        [Serializable] public sealed class Track { public string bone; public PoseKey[] keys; }
        [Serializable] public sealed class PoseKey { public int frame; public float dx, dy, angle; }

        public static void Build(string assetRoot, GameObject root, Transform[] bones, ClipRecord[] clips, float pixelsPerUnit, MonoBehaviour[] idleControllers)
        {
            if (clips == null || clips.Length == 0) return;
            var player = root.AddComponent<Animation>(); player.playAutomatically = false;
            var folder = assetRoot + "/Animations"; Directory.CreateDirectory(Path.GetFullPath(folder)); AssetDatabase.Refresh();
            var lookup = bones.ToDictionary(bone => bone.name);
            foreach (var record in clips)
            {
                if (record == null || !Regex.IsMatch(record.id ?? "", "^clip_[a-z0-9_]{1,60}$") || record.fps < 1 || record.fps > 60 || record.frames < 2 || record.frames > 3600)
                    throw new InvalidDataException("애니메이션 클립 ID·FPS·길이를 확인하세요.");
                if (record.tracks == null || record.tracks.Length == 0) continue;
                var path = folder + "/" + record.id + ".anim";
                var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
                var isNew = !clip; if (isNew) clip = new AnimationClip(); else clip.ClearCurves();
                clip.name = record.name; clip.legacy = true; clip.frameRate = record.fps; clip.wrapMode = record.loop ? WrapMode.Loop : WrapMode.Once;
                foreach (var track in record.tracks)
                {
                    if (!lookup.TryGetValue(track.bone, out var bone) || track.keys == null || track.keys.Length == 0) continue;
                    var xs = new List<Keyframe>(); var ys = new List<Keyframe>(); var angles = new List<Keyframe>();
                    var previousAngle = 0f;
                    for (var frame = 0; frame <= record.frames; frame++)
                    {
                        var pose = Evaluate(record, track, frame);
                        var unwrapped = frame == 0 ? pose.angle : previousAngle + ShortAngle(pose.angle - previousAngle); previousAngle = unwrapped;
                        var time = frame / (float)record.fps;
                        xs.Add(new Keyframe(time, bone.localPosition.x + pose.dx / pixelsPerUnit));
                        ys.Add(new Keyframe(time, bone.localPosition.y - pose.dy / pixelsPerUnit));
                        angles.Add(new Keyframe(time, -unwrapped));
                    }
                    var bonePath = AnimationUtility.CalculateTransformPath(bone, root.transform);
                    clip.SetCurve(bonePath, typeof(Transform), "localPosition.x", LinearCurve(xs));
                    clip.SetCurve(bonePath, typeof(Transform), "localPosition.y", LinearCurve(ys));
                    clip.SetCurve(bonePath, typeof(Transform), "localEulerAnglesRaw.z", LinearCurve(angles));
                }
                if (isNew) AssetDatabase.CreateAsset(clip, path); else EditorUtility.SetDirty(clip);
                player.AddClip(clip, record.id);
            }
            root.AddComponent<RiggingV2ClipPlayer>().Configure(player, idleControllers, bones);
        }

        private static AnimationCurve LinearCurve(List<Keyframe> keys)
        {
            var curve = new AnimationCurve(keys.ToArray());
            for (var i = 0; i < curve.length; i++)
            { AnimationUtility.SetKeyLeftTangentMode(curve, i, AnimationUtility.TangentMode.Linear); AnimationUtility.SetKeyRightTangentMode(curve, i, AnimationUtility.TangentMode.Linear); }
            return curve;
        }
        private static float ShortAngle(float delta) => ((delta + 180f) % 360f + 360f) % 360f - 180f;

        public static PoseKey Evaluate(ClipRecord clip, Track track, float frame)
        {
            var keys = track.keys;
            frame = clip.loop ? (frame % clip.frames + clip.frames) % clip.frames : Mathf.Clamp(frame, 0, clip.frames - 1);
            var a = keys[0]; var b = a; float fa = a.frame, fb = fa;
            if (frame < keys[0].frame)
            { if (clip.loop) { a = keys[keys.Length - 1]; b = keys[0]; fa = a.frame - clip.frames; fb = b.frame; } }
            else if (frame >= keys[keys.Length - 1].frame)
            { a = b = keys[keys.Length - 1]; fa = fb = a.frame; if (clip.loop) { b = keys[0]; fb = b.frame + clip.frames; } }
            else for (var i = 0; i < keys.Length - 1; i++)
            { if (keys[i].frame <= frame && frame < keys[i + 1].frame) { a = keys[i]; b = keys[i + 1]; fa = a.frame; fb = b.frame; break; } }
            var t = fa == fb ? 0f : (frame - fa) / (fb - fa);
            t = clip.easing == "hold" ? 0f : clip.easing == "smooth" ? t * t * (3f - 2f * t) : t;
            return new PoseKey { dx = Mathf.Lerp(a.dx, b.dx, t), dy = Mathf.Lerp(a.dy, b.dy, t), angle = a.angle + ShortAngle(b.angle - a.angle) * t };
        }
    }
}
