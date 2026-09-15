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
        [SerializeField] private Transform skirtCenter;
        [SerializeField] private Transform skirtLeft;
        [SerializeField] private Transform skirtRight;
        [SerializeField] private Transform legLeft;
        [SerializeField] private Transform legRight;

        private Quaternion spineRest;
        private Quaternion chestRest;
        private Quaternion neckRest;
        private Quaternion headRest;
        private Vector3 chestScale;
        private Quaternion skirtCenterRest;
        private Quaternion skirtLeftRest;
        private Quaternion skirtRightRest;
        private Quaternion legLeftRest;
        private Quaternion legRightRest;

        public void Configure(Transform hipsBone, Transform spineBone, Transform chestBone, Transform neckBone, Transform headBone,
            Transform skirtCenterBone = null, Transform skirtLeftBone = null, Transform skirtRightBone = null,
            Transform legLeftBone = null, Transform legRightBone = null)
        {
            hips = hipsBone;
            spine = spineBone;
            chest = chestBone;
            neck = neckBone;
            head = headBone;
            skirtCenter = skirtCenterBone;
            skirtLeft = skirtLeftBone;
            skirtRight = skirtRightBone;
            legLeft = legLeftBone;
            legRight = legRightBone;
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
            skirtCenterRest = skirtCenter ? skirtCenter.localRotation : Quaternion.identity;
            skirtLeftRest = skirtLeft ? skirtLeft.localRotation : Quaternion.identity;
            skirtRightRest = skirtRight ? skirtRight.localRotation : Quaternion.identity;
            legLeftRest = legLeft ? legLeft.localRotation : Quaternion.identity;
            legRightRest = legRight ? legRight.localRotation : Quaternion.identity;
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
            var skirtSway = Mathf.Sin(phase * 0.92f + 1.1f);
            if (skirtCenter) skirtCenter.localRotation = skirtCenterRest * Quaternion.Euler(0f, 0f, skirtSway * 0.55f);
            if (skirtLeft) skirtLeft.localRotation = skirtLeftRest * Quaternion.Euler(0f, 0f, skirtSway * 0.85f);
            if (skirtRight) skirtRight.localRotation = skirtRightRest * Quaternion.Euler(0f, 0f, -skirtSway * 0.85f);
            var step = Mathf.Sin(phase * 0.72f + 0.2f) * 0.8f;
            if (legLeft) legLeft.localRotation = legLeftRest * Quaternion.Euler(0f, 0f, step);
            if (legRight) legRight.localRotation = legRightRest * Quaternion.Euler(0f, 0f, -step);
        }
    }
}
