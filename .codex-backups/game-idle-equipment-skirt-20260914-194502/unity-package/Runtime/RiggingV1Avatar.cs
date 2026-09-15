using System.Collections;
using UnityEngine;

namespace SpriteLab.RiggingV1
{
    public sealed class RiggingV1Avatar : MonoBehaviour
    {
        [Header("Expression layers")]
        [SerializeField] private SpriteRenderer[] openEyes = new SpriteRenderer[0];
        [SerializeField] private SpriteRenderer[] closedEyes = new SpriteRenderer[0];
        [SerializeField] private SpriteRenderer mouthOpen;
        [SerializeField] private SpriteRenderer mouthClosed;

        [Header("Automatic preview")]
        [SerializeField] private bool automaticBlink = true;
        [SerializeField] private Vector2 blinkInterval = new Vector2(2.5f, 5.5f);
        [SerializeField] private float blinkDuration = 0.12f;
        [SerializeField] private bool automaticLipSync;
        [SerializeField, Range(0f, 1f)] private float mouthOpenAmount;

        [Header("Hair sway")]
        [SerializeField] private Transform[] hairParts = new Transform[0];
        [SerializeField] private float hairAngle = 2.5f;
        [SerializeField] private float hairSpeed = 1.4f;

        private Quaternion[] hairRest = new Quaternion[0];

        public void Configure(
            SpriteRenderer[] eyesOpen,
            SpriteRenderer[] eyesClosed,
            SpriteRenderer openMouth,
            SpriteRenderer closedMouth,
            Transform[] hair)
        {
            openEyes = eyesOpen ?? new SpriteRenderer[0];
            closedEyes = eyesClosed ?? new SpriteRenderer[0];
            mouthOpen = openMouth;
            mouthClosed = closedMouth;
            hairParts = hair ?? new Transform[0];
            CacheHairRestPose();
            SetEyeOpen(1f);
            SetMouthOpen(0f);
        }

        private void Awake()
        {
            CacheHairRestPose();
            SetEyeOpen(1f);
            SetMouthOpen(mouthOpenAmount);
        }

        private void OnEnable()
        {
            if (automaticBlink)
                StartCoroutine(BlinkLoop());
        }

        private void Update()
        {
            if (automaticLipSync)
                SetMouthOpen(Mathf.SmoothStep(0f, 1f, (Mathf.Sin(Time.time * 7f) + 1f) * 0.5f));

            for (var i = 0; i < hairParts.Length && i < hairRest.Length; i++)
            {
                if (!hairParts[i]) continue;
                var sway = Mathf.Sin(Time.time * hairSpeed + i * 0.73f) * hairAngle / (1f + i * 0.12f);
                hairParts[i].localRotation = hairRest[i] * Quaternion.Euler(0f, 0f, sway);
            }
        }

        public void SetEyeOpen(float amount)
        {
            amount = Mathf.Clamp01(amount);
            SetAlpha(openEyes, amount);
            SetAlpha(closedEyes, 1f - amount);
        }

        public void SetMouthOpen(float amount)
        {
            mouthOpenAmount = Mathf.Clamp01(amount);
            SetAlpha(mouthOpen, mouthOpenAmount);
            SetAlpha(mouthClosed, 1f - mouthOpenAmount);
            if (mouthOpen)
            {
                var scale = mouthOpen.transform.localScale;
                scale.y = Mathf.Lerp(0.35f, 1f, mouthOpenAmount);
                mouthOpen.transform.localScale = scale;
            }
        }

        private IEnumerator BlinkLoop()
        {
            while (enabled)
            {
                yield return new WaitForSeconds(Random.Range(blinkInterval.x, blinkInterval.y));
                SetEyeOpen(0f);
                yield return new WaitForSeconds(blinkDuration);
                SetEyeOpen(1f);
            }
        }

        private void CacheHairRestPose()
        {
            hairRest = new Quaternion[hairParts.Length];
            for (var i = 0; i < hairParts.Length; i++)
                hairRest[i] = hairParts[i] ? hairParts[i].localRotation : Quaternion.identity;
        }

        private static void SetAlpha(SpriteRenderer[] renderers, float alpha)
        {
            foreach (var renderer in renderers)
                SetAlpha(renderer, alpha);
        }

        private static void SetAlpha(SpriteRenderer renderer, float alpha)
        {
            if (!renderer) return;
            var color = renderer.color;
            color.a = alpha;
            renderer.color = color;
            renderer.enabled = alpha > 0.001f;
        }
    }
}
