using System.Linq;
using SpriteLab.RiggingV1;
using UnityEngine;
using UnityEngine.UI;

namespace SpriteLab.RiggingV2
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(RawImage))]
    public sealed class RiggingV2Portrait : MonoBehaviour
    {
        private const int PreviewLayer = 31;
        private static int nextStageSlot;

        [SerializeField] private GameObject avatarPrefab;
        [SerializeField, Range(1f, 1.5f)] private float framingPadding = 1.08f;
        [SerializeField, Range(256, 2048)] private int maximumTextureSize = 1024;

        [Header("Eyes and mouth")]
        [SerializeField] private bool automaticBlink = true;
        [SerializeField] private Vector2 blinkIntervalSeconds = new Vector2(2.5f, 5.5f);
        [SerializeField, Range(0.02f, 0.5f)] private float blinkDurationSeconds = 0.12f;
        [SerializeField] private bool automaticLipSync;
        [SerializeField, Range(0f, 1f)] private float mouthOpenAmount;

        [Header("Hair, equipment, and cloth")]
        [SerializeField, Range(0f, 12f)] private float hairSwayDegrees = 2.5f;
        [SerializeField, Range(0f, 5f)] private float hairSwaySpeed = 1.4f;
        [SerializeField, Range(0f, 8f)] private float equipmentSwayDegrees = 0.75f;
        [SerializeField, Range(0f, 8f)] private float clothSwayDegrees = 0.55f;

        [Header("Body idle")]
        [SerializeField] private bool automaticIdle = true;
        [SerializeField, Range(0f, 6f)] private float bodySwayDegrees = 0.65f;
        [SerializeField, Range(0f, 6f)] private float headFollowDegrees = 0.45f;
        [SerializeField, Range(0f, 0.05f)] private float breathingScale = 0.008f;
        [SerializeField, Range(0.1f, 3f)] private float idleSpeed = 0.8f;
        [SerializeField, Range(0f, 0.2f)] private float bodyBob;

        private RawImage targetImage;
        private GameObject stage;
        private Camera portraitCamera;
        private RenderTexture targetTexture;
        private Vector2Int textureSize;

        public GameObject AvatarInstance { get; private set; }

        public void Configure(GameObject prefab)
        {
            avatarPrefab = prefab;
        }

        public void RefreshAnimationSettings()
        {
            if (!AvatarInstance) return;
            var expression = AvatarInstance.GetComponent<RiggingV1Avatar>();
            if (expression)
                expression.ApplyPreviewSettings(automaticBlink, blinkIntervalSeconds, blinkDurationSeconds,
                    automaticLipSync, mouthOpenAmount, hairSwayDegrees, hairSwaySpeed,
                    equipmentSwayDegrees, clothSwayDegrees);
            var idle = AvatarInstance.GetComponent<RiggingV2Avatar>();
            if (idle)
                idle.ApplyIdleSettings(automaticIdle, bodySwayDegrees, headFollowDegrees, breathingScale, idleSpeed, bodyBob);
        }

        private void OnValidate()
        {
            blinkIntervalSeconds.x = Mathf.Max(0.1f, blinkIntervalSeconds.x);
            blinkIntervalSeconds.y = Mathf.Max(blinkIntervalSeconds.x, blinkIntervalSeconds.y);
            if (Application.isPlaying) RefreshAnimationSettings();
        }

        private void OnEnable()
        {
            if (Application.isPlaying) BuildStage();
        }

        private void OnDisable()
        {
            ReleaseStage();
        }

        private void OnRectTransformDimensionsChange()
        {
            if (!Application.isPlaying || !isActiveAndEnabled || !avatarPrefab) return;
            var wanted = CalculateTextureSize();
            if (wanted != textureSize) BuildStage();
        }

        private void BuildStage()
        {
            ReleaseStage();
            if (!avatarPrefab) return;

            targetImage = GetComponent<RawImage>();
            targetImage.raycastTarget = false;
            textureSize = CalculateTextureSize();
            targetTexture = new RenderTexture(textureSize.x, textureSize.y, 16, RenderTextureFormat.ARGB32)
            {
                name = name + " Portrait",
                antiAliasing = 1,
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
            };
            targetTexture.Create();
            targetImage.texture = targetTexture;

            var slot = nextStageSlot++;
            stage = new GameObject("[Sprite Lab Portrait Stage]");
            stage.hideFlags = HideFlags.HideAndDontSave;
            stage.transform.position = new Vector3(slot * 1000f, 10000f, 0f);

            AvatarInstance = Instantiate(avatarPrefab, stage.transform, false);
            AvatarInstance.name = avatarPrefab.name;
            SetLayerRecursively(AvatarInstance.transform, PreviewLayer);
            RefreshAnimationSettings();

            var cameraObject = new GameObject("Portrait Camera");
            cameraObject.hideFlags = HideFlags.HideAndDontSave;
            cameraObject.transform.SetParent(stage.transform, false);
            portraitCamera = cameraObject.AddComponent<Camera>();
            portraitCamera.clearFlags = CameraClearFlags.SolidColor;
            portraitCamera.backgroundColor = Color.clear;
            portraitCamera.orthographic = true;
            portraitCamera.cullingMask = 1 << PreviewLayer;
            portraitCamera.targetTexture = targetTexture;
            portraitCamera.allowHDR = false;
            portraitCamera.allowMSAA = false;

            FrameAvatar(AvatarInstance);
        }

        private void FrameAvatar(GameObject avatar)
        {
            var renderers = avatar.GetComponentsInChildren<SpriteRenderer>(true);
            if (renderers.Length == 0) return;
            var bounds = renderers[0].bounds;
            foreach (var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);
            var aspect = textureSize.x / (float)textureSize.y;
            portraitCamera.orthographicSize = Mathf.Max(bounds.extents.y, bounds.extents.x / aspect) * framingPadding;
            portraitCamera.orthographicSize = Mathf.Max(0.01f, portraitCamera.orthographicSize);
            portraitCamera.transform.position = new Vector3(bounds.center.x, bounds.center.y, bounds.min.z - 10f);
            portraitCamera.nearClipPlane = 0.01f;
            portraitCamera.farClipPlane = 100f;
        }

        private Vector2Int CalculateTextureSize()
        {
            var rect = ((RectTransform)transform).rect;
            var width = Mathf.Max(1f, Mathf.Abs(rect.width));
            var height = Mathf.Max(1f, Mathf.Abs(rect.height));
            var scale = Mathf.Min(1f, maximumTextureSize / Mathf.Max(width, height));
            return new Vector2Int(
                Mathf.Clamp(Mathf.CeilToInt(width * scale), 64, maximumTextureSize),
                Mathf.Clamp(Mathf.CeilToInt(height * scale), 64, maximumTextureSize));
        }

        private static void SetLayerRecursively(Transform root, int layer)
        {
            root.gameObject.layer = layer;
            foreach (Transform child in root) SetLayerRecursively(child, layer);
        }

        private void ReleaseStage()
        {
            if (targetImage && targetImage.texture == targetTexture) targetImage.texture = null;
            if (portraitCamera) portraitCamera.enabled = false;
            if (stage) stage.SetActive(false);
            if (targetTexture)
            {
                targetTexture.Release();
                Destroy(targetTexture);
            }
            if (stage) Destroy(stage);
            targetTexture = null;
            stage = null;
            portraitCamera = null;
            AvatarInstance = null;
        }
    }
}
