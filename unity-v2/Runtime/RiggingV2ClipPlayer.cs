using UnityEngine;
using SpriteLab.RiggingV1;

namespace SpriteLab.RiggingV2
{
    public sealed class RiggingV2ClipPlayer : MonoBehaviour
    {
        [SerializeField] private Animation player;
        [SerializeField] private MonoBehaviour[] idleControllers;
        [SerializeField] private Transform[] bones;
        private Vector3[] positions, scales;
        private Quaternion[] rotations;
        private bool[] enabledBefore;
        private bool[] partMotionBefore;
        private bool holding;

        public void Configure(Animation animation, MonoBehaviour[] controllers, Transform[] skeleton)
        { player = animation; idleControllers = controllers; bones = skeleton; }

        private void Awake() => CaptureRest();
        private void CaptureRest()
        {
            if (positions != null || bones == null) return;
            positions = new Vector3[bones.Length]; scales = new Vector3[bones.Length]; rotations = new Quaternion[bones.Length];
            for (var i = 0; i < bones.Length; i++)
            { positions[i] = bones[i].localPosition; scales[i] = bones[i].localScale; rotations[i] = bones[i].localRotation; }
        }

        // Accepts the editor clip name or its stable clip_* ID.
        public bool Play(string clipNameOrId)
        {
            if (!player) return false;
            var state = player[clipNameOrId];
            if (state == null)
                foreach (AnimationState candidate in player)
                    if (candidate.clip.name == clipNameOrId) { state = candidate; break; }
            if (state == null) return false;
            CaptureRest();
            if (!holding)
            {
                enabledBefore = new bool[idleControllers.Length];
                partMotionBefore = new bool[idleControllers.Length];
                for (var i = 0; i < idleControllers.Length; i++)
                {
                    enabledBefore[i] = idleControllers[i] && idleControllers[i].enabled;
                    if (idleControllers[i] is RiggingV1Avatar face)
                    { partMotionBefore[i] = face.PartMotionEnabled; face.PartMotionEnabled = false; }
                    else if (idleControllers[i]) idleControllers[i].enabled = false;
                }
                holding = true;
            }
            RestoreBones();
            state.time = 0f;
            return player.Play(state.name);
        }

        public void Stop()
        {
            if (!holding) return;
            player.Stop(); RestoreBones();
            for (var i = 0; i < idleControllers.Length; i++) if (idleControllers[i])
            { if (idleControllers[i] is RiggingV1Avatar face) face.PartMotionEnabled = partMotionBefore[i]; idleControllers[i].enabled = enabledBefore[i]; }
            holding = false;
        }

        private void RestoreBones()
        {
            if (positions == null) return;
            for (var i = 0; i < bones.Length; i++) if (bones[i])
            { bones[i].localPosition = positions[i]; bones[i].localRotation = rotations[i]; bones[i].localScale = scales[i]; }
        }
        private void Update() { if (holding && !player.isPlaying) Stop(); }
        private void OnDisable() => Stop();
    }
}
