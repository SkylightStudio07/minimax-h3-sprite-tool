using UnityEngine;

namespace SpriteLab.RiggingV2
{
    public sealed class RiggingV2Avatar : MonoBehaviour
    {
        [Header("Automatic idle preview")]
        [SerializeField] private bool automaticIdle = true;
        [SerializeField, Range(0f, 3f)] private float bodySwayDegrees = 0.65f;
        [SerializeField, Range(0f, 3f)] private float headFollowDegrees = 0.45f;
        [SerializeField, Range(0f, 0.03f)] private float breathingScale = 0.008f;
        [SerializeField, Range(0.1f, 3f)] private float idleSpeed = 0.8f;

        [SerializeField] private Transform hips;
        [SerializeField] private Transform spine;
        [SerializeField] private Transform chest;
        [SerializeField] private Transform neck;
        [SerializeField] private Transform head;

        private Quaternion spineRest;
        private Quaternion chestRest;
        private Quaternion neckRest;
        private Quaternion headRest;
        private Vector3 chestScale;

        public void Configure(Transform hipsBone, Transform spineBone, Transform chestBone, Transform neckBone, Transform headBone)
        {
            hips = hipsBone;
            spine = spineBone;
            chest = chestBone;
            neck = neckBone;
            head = headBone;
            CachePose();
        }

        private void Awake() => CachePose();

        private void CachePose()
        {
            spineRest = spine ? spine.localRotation : Quaternion.identity;
            chestRest = chest ? chest.localRotation : Quaternion.identity;
            neckRest = neck ? neck.localRotation : Quaternion.identity;
            headRest = head ? head.localRotation : Quaternion.identity;
            chestScale = chest ? chest.localScale : Vector3.one;
        }

        private void Update()
        {
            if (!automaticIdle) return;
            var phase = Time.time * idleSpeed;
            var sway = Mathf.Sin(phase) * bodySwayDegrees;
            var breath = (Mathf.Sin(phase * 1.7f - 0.8f) + 1f) * 0.5f;
            if (spine) spine.localRotation = spineRest * Quaternion.Euler(0f, 0f, sway * 0.45f);
            if (chest)
            {
                chest.localRotation = chestRest * Quaternion.Euler(0f, 0f, sway);
                chest.localScale = chestScale + new Vector3(breathingScale * breath * 0.35f, breathingScale * breath, 0f);
            }
            if (neck) neck.localRotation = neckRest * Quaternion.Euler(0f, 0f, -sway * 0.55f);
            if (head) head.localRotation = headRest * Quaternion.Euler(0f, 0f, -Mathf.Sin(phase + 0.35f) * headFollowDegrees);
        }
    }
}
