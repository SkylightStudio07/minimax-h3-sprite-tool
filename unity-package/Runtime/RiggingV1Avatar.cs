using System;
using System.Collections;
using System.Linq;
using UnityEngine;

namespace SpriteLab.RiggingV1
{
    [Serializable]
    public sealed class ExpressionVariant
    {
        public string name;
        public string slot;
        public SpriteRenderer renderer;
        public SpriteRenderer slotRenderer;
    }

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

        [Header("Equipment and cloth idle")]
        [SerializeField] private Transform[] equipmentParts = new Transform[0];
        [SerializeField] private Transform[] clothParts = new Transform[0];
        [SerializeField, Range(0f, 2f)] private float equipmentAngle = 0.75f;
        [SerializeField, Range(0f, 2f)] private float clothAngle = 0.55f;

        [Header("Head and body idle")]
        [SerializeField] private Transform headRoot;
        [SerializeField] private Transform bodyRoot;
        [SerializeField, Range(0f, 4f)] private float headAngle = 0.7f;
        [SerializeField, Range(0f, 0.05f)] private float headShift = 0.008f;
        [SerializeField, Range(0f, 2f)] private float bodyAngle = 0.2f;
        [SerializeField, Range(0f, 0.02f)] private float breathScale = 0.004f;
        [SerializeField] private float breathSeconds = 3.4f;

        [Header("Look and depth")]
        [Tooltip("Follow this object with the eyes and head. Leave empty to use SetLook or idle only.")]
        [SerializeField] private Transform lookTarget;
        [Tooltip("World distance from the head at which the look reaches its limit.")]
        [SerializeField] private float lookRange = 3f;
        [SerializeField] private float lookSpeed = 6f;
        [SerializeField, Range(0f, 1f)] private float idleLook = 0.18f;
        [SerializeField, Range(0f, 2f)] private float parallax = 1f;
        [SerializeField] private Transform[] depthParts = new Transform[0];
        [SerializeField] private float[] depthAmounts = new float[0];

        [Header("Crowds")]
        [Tooltip("Start each character's idle at a different point so a group does not sway in unison.")]
        [SerializeField] private bool randomizePhase = true;

        [Header("Expressions")]
        [SerializeField] private ExpressionVariant[] variants = new ExpressionVariant[0];

        private bool restCached;
        private float phase;
        private float eyeOpenAmount = 1f;
        private Quaternion headRestRotation = Quaternion.identity;
        private Quaternion bodyRestRotation = Quaternion.identity;
        private Vector3 headRestPosition;
        private Vector3 bodyRestScale = Vector3.one;
        private Quaternion[] hairRest = new Quaternion[0];
        private Quaternion[] equipmentRest = new Quaternion[0];
        private Quaternion[] clothRest = new Quaternion[0];
        private Vector3[] depthRest = new Vector3[0];
        private Vector2 look;
        private Vector2 manualLook;
        private bool hasManualLook;
        private Coroutine blinkRoutine;

        public void Configure(
            SpriteRenderer[] eyesOpen,
            SpriteRenderer[] eyesClosed,
            SpriteRenderer openMouth,
            SpriteRenderer closedMouth,
            Transform[] hair,
            Transform[] equipment = null,
            Transform[] cloth = null,
            Transform head = null,
            Transform body = null,
            ExpressionVariant[] expressionVariants = null,
            Transform[] depthLayers = null,
            float[] depthShifts = null)
        {
            depthParts = depthLayers ?? new Transform[0];
            depthAmounts = depthShifts ?? new float[0];
            openEyes = eyesOpen ?? new SpriteRenderer[0];
            closedEyes = eyesClosed ?? new SpriteRenderer[0];
            mouthOpen = openMouth;
            mouthClosed = closedMouth;
            hairParts = hair ?? new Transform[0];
            equipmentParts = equipment ?? new Transform[0];
            clothParts = cloth ?? new Transform[0];
            headRoot = head;
            bodyRoot = body;
            variants = expressionVariants ?? new ExpressionVariant[0];
            CacheRestPose();
            SetEyeOpen(1f);
            SetMouthOpen(0f);
        }

        public void ApplyPreviewSettings(
            bool blink,
            Vector2 interval,
            float duration,
            bool lipSync,
            float mouthAmount,
            float hairSwayAngle,
            float hairSwaySpeed,
            float equipmentSwayAngle,
            float clothSwayAngle)
        {
            automaticBlink = blink;
            blinkInterval = new Vector2(Mathf.Max(0.1f, interval.x), Mathf.Max(Mathf.Max(0.1f, interval.x), interval.y));
            blinkDuration = Mathf.Max(0.02f, duration);
            automaticLipSync = lipSync;
            mouthOpenAmount = Mathf.Clamp01(mouthAmount);
            hairAngle = Mathf.Max(0f, hairSwayAngle);
            hairSpeed = Mathf.Max(0f, hairSwaySpeed);
            equipmentAngle = Mathf.Max(0f, equipmentSwayAngle);
            clothAngle = Mathf.Max(0f, clothSwayAngle);
            if (!automaticLipSync) SetMouthOpen(mouthOpenAmount);
            UpdateBlinkRoutine();
        }

        private void Awake()
        {
            CacheRestPose();
            phase = randomizePhase ? UnityEngine.Random.value * 100f : 0f;
            SetEyeOpen(1f);
            SetMouthOpen(mouthOpenAmount);
        }

        private void OnEnable()
        {
            UpdateBlinkRoutine();
        }

        private void OnDisable()
        {
            if (blinkRoutine != null) StopCoroutine(blinkRoutine);
            blinkRoutine = null;
        }

        private void Update()
        {
            var time = Time.time + phase;
            if (automaticLipSync)
                SetMouthOpen(Mathf.SmoothStep(0f, 1f, (Mathf.Sin(time * 7f) + 1f) * 0.5f));
            if (!PartMotionEnabled) return;
            ApplyIdle(time);
            var wander = idleLook * new Vector2(0.7f * Mathf.Sin(time * 0.37f + 0.9f) + 0.3f * Mathf.Sin(time * 0.83f), 0.5f * Mathf.Sin(time * 0.29f + 2f));
            var wanted = Vector2.ClampMagnitude((lookTarget ? LookDirection(lookTarget.position) : hasManualLook ? manualLook : Vector2.zero) + wander, 1f);
            ApplyLook(Vector2.Lerp(look, wanted, 1f - Mathf.Exp(-lookSpeed * Time.deltaTime)));
        }

        /// <summary>Look in a direction, -1 to 1 on each axis: +x is the screen right, +y is up. Eases there.</summary>
        public void SetLook(Vector2 direction)
        {
            manualLook = Vector2.ClampMagnitude(direction, 1f);
            hasManualLook = true;
        }

        /// <summary>Look once toward a world position. Assign lookTarget instead to keep following something.</summary>
        public void LookAt(Vector3 worldPoint) => SetLook(LookDirection(worldPoint));

        /// <summary>Return to facing forward.</summary>
        public void ClearLook() => hasManualLook = false;

        /// <summary>Pose the head layers for a look direction at once. Update calls this; it is public for previews and tests.</summary>
        public void ApplyLook(Vector2 direction)
        {
            if (!restCached) CacheRestPose();
            look = direction;
            var shift = new Vector3(direction.x, direction.y * 0.6f, 0f) * parallax;
            for (var i = 0; i < depthParts.Length && i < depthRest.Length && i < depthAmounts.Length; i++)
                if (depthParts[i]) depthParts[i].localPosition = depthRest[i] + shift * depthAmounts[i];
        }

        private Vector2 LookDirection(Vector3 worldPoint)
        {
            var offset = worldPoint - (headRoot ? headRoot.position : transform.position);
            // A sprite flipped with a negative scale mirrors its layers, so the look has to mirror back.
            return Vector2.ClampMagnitude(new Vector2(offset.x * Mathf.Sign(transform.lossyScale.x), offset.y) / Mathf.Max(0.01f, lookRange), 1f);
        }

        /// <summary>Pose the idle at a given time. Update calls this; it is public for previews and tests.</summary>
        public void ApplyIdle(float time)
        {
            if (!restCached) CacheRestPose();
            for (var i = 0; i < hairParts.Length && i < hairRest.Length; i++)
            {
                if (!hairParts[i]) continue;
                var sway = Mathf.Sin(time * hairSpeed + i * 0.73f) * hairAngle / (1f + i * 0.12f);
                hairParts[i].localRotation = hairRest[i] * Quaternion.Euler(0f, 0f, sway);
            }
            for (var i = 0; i < equipmentParts.Length && i < equipmentRest.Length; i++)
                if (equipmentParts[i]) equipmentParts[i].localRotation = equipmentRest[i] * Quaternion.Euler(0f, 0f, Mathf.Sin(time * 1.15f + 0.35f + i * 0.2f) * equipmentAngle);
            for (var i = 0; i < clothParts.Length && i < clothRest.Length; i++)
                if (clothParts[i]) clothParts[i].localRotation = clothRest[i] * Quaternion.Euler(0f, 0f, Mathf.Sin(time * 0.92f + 1.1f + i * 0.31f) * clothAngle);

            var breath = 0.5f + 0.5f * Mathf.Sin(time * 2f * Mathf.PI / Mathf.Max(0.1f, breathSeconds));
            if (bodyRoot)
            {
                bodyRoot.localRotation = bodyRestRotation * Quaternion.Euler(0f, 0f, Mathf.Sin(time * 0.19f + 2.1f) * bodyAngle);
                var scale = bodyRestScale;
                scale.y *= 1f + breath * breathScale;
                bodyRoot.localScale = scale;
            }
            if (headRoot)
            {
                var tilt = 0.6f * Mathf.Sin(time * 0.23f + 0.5f) + 0.4f * Mathf.Sin(time * 0.71f + 1.3f);
                headRoot.localRotation = headRestRotation * Quaternion.Euler(0f, 0f, tilt * headAngle);
                headRoot.localPosition = headRestPosition + new Vector3(
                    (0.7f * Mathf.Sin(time * 0.42f) + 0.3f * Mathf.Sin(time * 1.13f)) * headShift,
                    (0.5f * Mathf.Sin(time * 0.31f + 1.7f) + 0.5f * (breath - 0.5f)) * headShift, 0f);
            }
        }

        /// <summary>Saved expression names that SetExpression accepts.</summary>
        public string[] ExpressionNames => variants.Select(item => item.name).ToArray();

        /// <summary>Show a saved expression in place of its slot. Returns false if the name is unknown.</summary>
        public bool SetExpression(string expressionName)
        {
            var chosen = variants.FirstOrDefault(item => item.name == expressionName);
            if (chosen == null || !chosen.renderer) return false;
            foreach (var other in variants.Where(item => item.slot == chosen.slot && item != chosen))
            {
                Replace(other.renderer, chosen.slotRenderer);
                if (other.renderer) other.renderer.enabled = false;
            }
            Replace(chosen.slotRenderer, chosen.renderer);
            Refresh(chosen.slotRenderer, chosen.renderer);
            return true;
        }

        /// <summary>Return to the default look, for one slot or, with no argument, for every slot.</summary>
        public void ClearExpression(string slot = null)
        {
            foreach (var item in variants.Where(item => slot == null || item.slot == slot))
            {
                if (!item.renderer || !item.slotRenderer) continue;
                var wasShown = item.renderer.enabled;
                Replace(item.renderer, item.slotRenderer);
                if (wasShown) Refresh(item.renderer, item.slotRenderer);
            }
        }

        private void Replace(SpriteRenderer from, SpriteRenderer to)
        {
            for (var i = 0; i < openEyes.Length; i++) if (openEyes[i] == from) openEyes[i] = to;
            for (var i = 0; i < closedEyes.Length; i++) if (closedEyes[i] == from) closedEyes[i] = to;
            if (mouthOpen == from) mouthOpen = to;
            if (mouthClosed == from) mouthClosed = to;
        }

        private void Refresh(SpriteRenderer hidden, SpriteRenderer shown)
        {
            hidden.enabled = false;
            shown.enabled = true;
            SetEyeOpen(eyeOpenAmount);
            SetMouthOpen(mouthOpenAmount);
        }

        public void SetEyeOpen(float amount)
        {
            amount = Mathf.Clamp01(amount);
            eyeOpenAmount = amount;
            SetAlpha(openEyes, amount);
            SetAlpha(closedEyes, 1f - amount);
        }

        // A recorded body clip can own bone motion while blink/lip sync continue.
        public bool PartMotionEnabled { get; set; } = true;

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
            while (isActiveAndEnabled && automaticBlink)
            {
                yield return new WaitForSeconds(UnityEngine.Random.Range(blinkInterval.x, blinkInterval.y));
                SetEyeOpen(0f);
                yield return new WaitForSeconds(blinkDuration);
                SetEyeOpen(1f);
            }
            blinkRoutine = null;
            SetEyeOpen(1f);
        }

        private void UpdateBlinkRoutine()
        {
            if (blinkRoutine != null)
            {
                StopCoroutine(blinkRoutine);
                blinkRoutine = null;
            }
            if (isActiveAndEnabled && automaticBlink) blinkRoutine = StartCoroutine(BlinkLoop());
            else SetEyeOpen(1f);
        }

        private void CacheRestPose()
        {
            hairRest = new Quaternion[hairParts.Length];
            for (var i = 0; i < hairParts.Length; i++)
                hairRest[i] = hairParts[i] ? hairParts[i].localRotation : Quaternion.identity;
            equipmentRest = CacheRotations(equipmentParts);
            clothRest = CacheRotations(clothParts);
            depthRest = depthParts.Select(part => part ? part.localPosition : Vector3.zero).ToArray();
            if (headRoot) { headRestRotation = headRoot.localRotation; headRestPosition = headRoot.localPosition; }
            if (bodyRoot) { bodyRestRotation = bodyRoot.localRotation; bodyRestScale = bodyRoot.localScale; }
            restCached = true;
        }

        private static Quaternion[] CacheRotations(Transform[] parts)
        {
            var result = new Quaternion[parts.Length];
            for (var i = 0; i < parts.Length; i++) result[i] = parts[i] ? parts[i].localRotation : Quaternion.identity;
            return result;
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
