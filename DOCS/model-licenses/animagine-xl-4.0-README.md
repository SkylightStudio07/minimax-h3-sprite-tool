---
language:
- en
tags:
- text-to-image
- stable-diffusion
- safetensors
- stable-diffusion-xl
widget:
- text: >-
    1girl, green hair, sweater, looking at viewer, upper body, beanie, outdoors,
    night, turtleneck, masterpiece, high score, great score, absurdres
  parameter:
    negative_prompt: >-
      lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit,
      fewer digits, cropped, worst quality, low quality, low score, bad score,
      average score, signature, watermark, username, blurry
  example_title: 1girl
- text: >-
    1boy, male focus, green hair, sweater, looking at viewer, upper body,
    beanie, outdoors, night, turtleneck, masterpiece, high score, great score,
    absurdres
  parameter:
    negative_prompt: >-
      lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit,
      fewer digits, cropped, worst quality, low quality, low score, bad score,
      average score, signature, watermark, username, blurry
  example_title: 1boy
license: openrail++
base_model:
- stabilityai/stable-diffusion-xl-base-1.0
---

# Animagine XL 4.0

![image/png](https://cdn-uploads.huggingface.co/production/uploads/6365c8dbf31ef76df4042821/_tsxjwf3VPu94xh9wJSbo.png)

## Overview

**Animagine XL 4.0**, also stylized as **Anim4gine**, is the ultimate anime-themed finetuned SDXL model and the latest installment of [Animagine XL series](https://huggingface.co/collections/Linaqruf/animagine-xl-669888c0add5adaf09754aca). Despite being a continuation, the model was retrained from [Stable Diffusion XL 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) with a massive dataset of 8.4M diverse anime-style images from various sources with the knowledge cut-off of January 7th 2025 and finetuned for approximately 2650 GPU hours. Similar to the previous version, this model was trained using tag ordering method for the identity and style training.
With the release of **Animagine XL 4.0 Opt (Optimized)**, the model has been further refined with an additional dataset, improving **stability**, **anatomy accuracy**, **noise reduction**, **color saturation**, and **overall color accuracy**. These enhancements make **Animagine XL 4.0 Opt** more consistent and visually appealing while maintaining the signature quality of the series.


## Changelog
- 2025-02-13 – Added Animagine XL 4.0 Opt
  - Better stability for more consistent outputs
  - Enhanced anatomy with more accurate proportions
  - Reduced noise and artifacts in generations
  - Fixed low saturation issues, resulting in richer colors
  - Improved color accuracy for more visually appealing results
- 2025-01-24 – Initial release


## Model Details

- **Developed by**: [Cagliostro Research Lab](https://github.com/cagliostrolab)
- **Model type**: Diffusion-based text-to-image generative model
- **License**: [CreativeML Open RAIL++-M](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md)
- **Model Description**: This is a model that can be used to generate and modify specifically anime-themed images based on text prompt
- **Fine-tuned from**: [Stable Diffusion XL 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)

## Downstream Use

1. Use this model in our [`Hugging Face Spaces`](https://huggingface.co/spaces/cagliostrolab/animagine-xl-4.0)
2. Use it in [`ComfyUI`](https://github.com/comfyanonymous/ComfyUI) or [`Stable Diffusion Webui`](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
3. Use it with 🧨 `diffusers`

## 🧨 Diffusers Installation

### 1. Install Required Libraries

```bash
pip install diffusers transformers accelerate safetensors --upgrade
```

### 2. Example Code
The example below uses `lpw_stable_diffusion_xl` pipeline which enables better handling of long, weighted and detailed prompts. The model is already uploaded in FP16 format, so there's no need to specify `variant="fp16"` in the `from_pretrained` call.

```python
import torch
from diffusers import StableDiffusionXLPipeline

pipe = StableDiffusionXLPipeline.from_pretrained(
    "cagliostrolab/animagine-xl-4.0",
    torch_dtype=torch.float16,
    use_safetensors=True,
    custom_pipeline="lpw_stable_diffusion_xl",
    add_watermarker=False
)
pipe.to('cuda')

prompt = "1girl, arima kana, oshi no ko, hoshimachi suisei, hoshimachi suisei \(1st costume\), cosplay, looking at viewer, smile, outdoors, night, v, masterpiece, high score, great score, absurdres"
negative_prompt = "lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry"

image = pipe(
    prompt,
    negative_prompt=negative_prompt,
    width=832,
    height=1216,
    guidance_scale=5,
    num_inference_steps=28
).images[0]

image.save("./arima_kana.png")
```

## Usage Guidelines

The summary can be seen in the image for the prompt guideline.

![image/png](https://cdn-uploads.huggingface.co/production/uploads/64c088660a4d02f37a965f6c/YPe3MCnQAHM7nCZ1vQ7vI.png)

### 1. Prompt Structure
The model was trained with tag-based captions and the tag-ordering method. Use this structured template:

```
1girl/1boy/1other, character name, from which series, rating, everything else in any order and end with quality enhancement
```

### 2. Quality Enhancement Tags
Add these tags at the end of your prompt:

```
masterpiece, high score, great score, absurdres
```

### 3. Recommended Negative Prompt
```
lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry
```

### 4. Optimal Settings
- **CFG Scale**: 4-7 (5 Recommended)
- **Sampling Steps**: 25-28 (28 Recommended)
- **Preferred Sampler**: Euler Ancestral (Euler a)

### 5. Recommended Resolutions

| Orientation | Dimensions | Aspect Ratio |
|------------|------------|--------------|
| Square     | 1024 x 1024| 1:1          |
| Landscape  | 1152 x 896 | 9:7          |
|            | 1216 x 832 | 3:2          |
|            | 1344 x 768 | 7:4          |
|            | 1536 x 640 | 12:5         |
| Portrait   | 896 x 1152 | 7:9          |
|            | 832 x 1216 | 2:3          |
|            | 768 x 1344 | 4:7          |
|            | 640 x 1536 | 5:12         |

### 6. Final Prompt Structure Example
```
1girl, firefly \(honkai: star rail\), honkai \(series\), honkai: star rail, safe, casual, solo, looking at viewer, outdoors, smile, reaching towards viewer, night, masterpiece, high score, great score, absurdres
```

## Special Tags

The model supports various special tags that can be used to control different aspects of the image generation process. These tags are carefully weighted and tested to provide consistent results across different prompts.

### Quality Tags
Quality tags are fundamental controls that directly influence the overall image quality and detail level. Available quality tags:
- `masterpiece`
- `best quality`
- `low quality`
- `worst quality`

| <img src="https://cdn-uploads.huggingface.co/production/uploads/6365c8dbf31ef76df4042821/bDdKraYxjiReKknlYJepR.png" width="100%" style="max-height: 400px; object-fit: contain;"> | <img src="https://cdn-uploads.huggingface.co/production/uploads/6365c8dbf31ef76df4042821/mAgMMKL2tBj8oBuWHTYUz.png" width="100%" style="max-height: 400px; object-fit: contain;"> |
|---|---|
| Sample image using `"masterpiece, best quality"` quality tags with negative prompt left empty. | Sample image using `"low quality, worst quality"` quality tags with negative prompt left empty. |

### Score Tags
Score tags provide a more nuanced control over image quality compared to basic quality tags. They have a stronger impact on steering output quality in this model. Available score tags:
- `high score`
- `great score`
- `good score`
- `average score`
- `bad score`
- `low score`

| <img src="https://cdn-uploads.huggingface.co/production/uploads/6365c8dbf31ef76df4042821/PXK6D1yhD8SND-VHFQOXD.png" width="100%" style="max-height: 400px; object-fit: contain;"> | <img src="https://cdn-uploads.huggingface.co/production/uploads/6365c8dbf31ef76df4042821/0uUw7DQ9IMiSNE_MZ9Uyf.png" width="100%" style="max-height: 400px; object-fit: contain;"> |
|---|---|
| Sample image using `"high score, great score"` score tags with negative prompt left empty. | Sample image using `"bad score, low score"` score tags with negative prompt left empty. |

### Temporal Tags
Temporal tags allow you to influence the artistic style based on specific time periods or years. This can be useful for generating images with era-specific artistic characteristics. Supported year tags:
- `year 2005`
- `year {n}`
- `year 2025`

| <img src="https://cdn-uploads.huggingface.co/production/uploads/6365c8dbf31ef76df4042821/weRv0BmfkZrBhcW5NxXAI.png" width="100%" style="max-height: 400px; object-fit: contain;"> | <img src="https://cdn-uploads.huggingface.co/production/uploads/6365c8dbf31ef76df4042821/WwFoeLrbN2MkXuGHh91Ky.png" width="100%" style="max-height: 400px; object-fit: contain;"> |
|---|---|
| Sample image of Hatsune Miku with `"year 2007"` temporal tag. | Sample image of Hatsune Miku with `"year 2023"` temporal tag. |

### Rating Tags
Rating tags help control the content safety level of generated images. These tags should be used responsibly and in accordance with applicable laws and platform policies. Supported ratings:
- `safe`
- `sensitive`
- `nsfw`
- `explicit`

## Training Information

The model was trained using state-of-the-art hardware and optimized hyperparameters to ensure the highest quality output. Below are the detailed technical specifications and parameters used during the training process:

| Parameter | Value |
|-----------|--------|
| Hardware | 7 x H100 80GB SXM5 |
| Num Images | 8,401,464 |
| UNet Learning Rate | 2.5e-6 |
| Text Encoder Learning Rate | 1.25e-6 |
| Scheduler | Constant With Warmup |
| Warmup Steps | 5% |
| Batch Size | 32 |
| Gradient Accumulation Steps | 2 |
| Training Resolution | 1024x1024 |
| Optimizer | Adafactor |
| Input Perturbation Noise | 0.1 |
| Debiased Estimation Loss | Enabled |
| Mixed Precision | fp16 |

## Acknowledgement

This long-term project would not have been possible without the groundbreaking work, innovative contributions, and comprehensive documentation provided by **Stability AI**, **Novel AI**, and **Waifu Diffusion Team**. We are especially grateful for the kickstarter grant from **Main** that enabled us to progress beyond V2. For this iteration, we would like to express our sincere gratitude to everyone in the community for their continuous support, particularly:

1. [**Moescape AI**](https://moescape.ai/): Our invaluable collaboration partner in model distribution and testing
2. **Lesser Rabbit**: For providing essential computing and research grants
3. [**Kohya SS**](https://github.com/kohya-ss): For developing the comprehensive open-source training framework
4. [**discus0434**](https://github.com/discus0434): For creating the industry-leading open-source Aesthetic Predictor 2.5
5. **Early testers**: For their dedication in providing critical feedback and thorough quality assurance

## Contributors

We extend our heartfelt appreciation to our dedicated team members who have contributed significantly to this project, including but not limited to:

### Model
- [**KayfaHaarukku**](https://huggingface.co/kayfahaarukku)
- [**Raelina**](https://huggingface.co/Raelina)
- [**Linaqruf**](https://huggingface.co/Linaqruf)

### Gradio 
- [**Damar Jati**](https://huggingface.co/DamarJati)

### Relations, finance, and quality assurance
- [**Scipius**](https://huggingface.co/Scipius2121)
- [**Asahina**](https://huggingface.co/Asahina2K)
- [**Bell**](https://huggingface.co/ItsMeBell)
- [**BoboiAzumi**](https://huggingface.co/Boboiazumi)

### Data
- [**Pomegranata**](https://huggingface.co/paripi)
- [**Kr1SsSzz**](https://huggingface.co/Kr1SsSzz)
- [**Fiqi**](https://huggingface.co/saikanov)
- [**William Adams Soeherman**](https://huggingface.co/williamsoeherman)

## Fundraising Has New Methods!

We're excited to introduce new fundraising methods through GitHub Sponsors to support training, research, and model development. Your support helps us push the boundaries of what's possible with AI.

**You can help us with:**

* **Donate**: Contribute via ETH, USDT, or USDC to the address below, or sponsor us on GitHub.

* **Share**: Spread the word about our models and share your creations!

* **Feedback**: Let us know how we can improve.

**Donation Address**: 

ETH/USDT/USDC(e): ```0xd8A1dA94BA7E6feCe8CfEacc1327f498fCcBFC0C```

**Github Sponsor**: [https://github.com/sponsors/cagliostrolab/](https://github.com/sponsors/cagliostrolab/)


<details>
<summary>Why do we use Cryptocurrency?</summary>
When we initially opened fundraising through Ko-fi and using PayPal as withdrawal methods, our PayPal account was flagged and eventually banned, despite our efforts to explain the purpose of our project. Unfortunately, this forced us to refund all donations and left us without a reliable way to receive support. To avoid such issues and ensure transparency, we have now switched to cryptocurrency as the way to raise the fund.
</details>

<details>
<summary>Want to Donate in Non-Crypto Currency?</summary>
Although we had a bad experience with Paypal, and you’d like to support us but prefer not to use cryptocurrency, feel free to contact us via [Discord Server](https://discord.gg/cqh9tZgbGc) for alternative donation methods.
</details>

## Join Our Discord Server
Feel free to join our discord server
<div style="text-align: center;">
  <a href="https://discord.gg/cqh9tZgbGc">
  <img src="https://discord.com/api/guilds/1115542847395987519/widget.png?style=banner2" alt="Discord Banner 2"/>
  </a>
</div>

## Limitations

- **Prompt Format**: Limited to tag-based text prompts; natural language input may not be effective
- **Anatomy**: May struggle with complex anatomical details, particularly hand poses and finger counting
- **Text Generation**: Text rendering in images is currently not supported and not recommended
- **New Characters**: Recent characters may have lower accuracy due to limited training data availability
- **Multiple Characters**: Scenes with multiple characters may require careful prompt engineering
- **Resolution**: Higher resolutions (e.g., 1536x1536) may show degradation as training used original SDXL resolution
- **Style Consistency**: May require specific style tags as training focused more on identity preservation than style consistency

## License

This model adopts the original [CreativeML Open RAIL++-M License](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md) from Stability AI without any modifications or additional restrictions. The license terms remain exactly as specified in the original SDXL license, which includes:

- ✅ **Permitted**: Commercial use, modifications, distributions, private use
- ❌ **Prohibited**: Illegal activities, harmful content generation, discrimination, exploitation
- ⚠️ **Requirements**: Include license copy, state changes, preserve notices
- 📝 **Warranty**: Provided "AS IS" without warranties

Please refer to the [original SDXL license](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md) for the complete and authoritative terms and conditions.