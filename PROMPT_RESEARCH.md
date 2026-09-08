# Sprite prompt revision: sprite-flat-v2 (2026-09-08)

## Follow-up: sprite-flat-v3-cfg-experiment

User requested removal of spotlight-related wording. Automatic positive and default negative prompts no longer name spotlight, stage lighting, cast shadows or vignettes. Historical per-job prompt records are unchanged.

Optional negative guidance is off by default. Enabling it switches BasicGuider to CFGGuider, encodes a separate negative using identical image order, first/last keyframes and audio/video geometry, and accepts CFG 1.1–2.0 (initial 1.5). Default negative is `scenery, textured background, changing background`. This is experimental with the existing four-step Turbo LoRA: extra computation/memory and visual degradation are possible. Model weights and step count are unchanged. Prompt audit records include both branches and CFG.

Structural tests verify both loop/non-loop branch layouts, default pass-through, removed terms and validation. They do not establish successful GPU sampling or better visual quality. Compare the new positive-only path against the same positive plus negative at the same input, seed, resolution and duration; comparison against v2 would also change positive wording.

## Evidence

- MiniMax's base prompt guide: https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md
- Official Chinese README: https://github.com/MiniMax-AI/MiniMax-H3/blob/main/README.zh-CN.md
- ComfyUI I2V documentation: https://docs.comfy.org/tutorials/video/minimax/minimax-h3
- Chinese-language discussion on the official model repository: https://huggingface.co/MiniMaxAI/MiniMax-H3/discussions/32

The base guide describes keyframe alignment followed by three named visual/audio fields. Our installed ComfyUI node sends the provided prompt to the encoder without adding those sections. The loop workflow supplies two images, but the old prompt mentioned only the first as a character reference. Revision v2 adds explicit opening/closing roles and a single-shot body. Duration labels follow the actual 17k+5 frame count at 24 fps. Chinese searches did not establish that Chinese is superior to English for this task; third-party H3-branded sites were not used as authoritative evidence.

## Task-specific hypotheses (not guaranteed model behavior)

- Describe exposed matte as a flat two-dimensional color field instead of leaving scene context unspecified. Explicitly retain input character scale, painted shading and illumination. This aims to discourage invented floors and stage lighting.
- Only alpha-bearing inputs receive the gray-matte instruction, matching existing preprocessing. Opaque inputs retain their own background. No background segmentation, keying or post-generation removal was added.
- Replace default repeated blinking with fixed opening eye shape; optional maximum-one-blink mode is a language instruction, not an exact counter.
- Default idle asks for a shallow slow torso motion, not a general performance. Keep action-specific movement and facing instructions intact.
- Existing sampler, model, steps and first/last-frame wiring are unchanged. This isolates the prompt change.

## Validation and limits

Run `.venv\Scripts\python.exe -m unittest test_sprite_prompts test_team_server -v`.
Each new real job stores `generation_prompt.json` beside its outputs with revision, actual prompt, seed, canvas and length. This file is not served by either public or authenticated result routes.

Use the same input, seed, resolution, duration, action, sampler and normalization setting for A/B comparisons. Judge the H3 raw video, not just stabilized playback. Inspect background color/geometry drift, head/eye changes, first-versus-last size and motion readability. Test multiple seeds before claiming reliability. A successful single clip does not establish a guarantee.

Prompt control does not create a transparent alpha channel. This revision aims to preserve a uniform matte; it cannot guarantee either background invariance or blink counts.
