---
license: creativeml-openrail-m
tags:
  - text-to-image
  - stable-diffusion
  - lora
  - diffusers
base_model: stabilityai/stable-diffusion-xl-base-1.0
instance_prompt: pixel art
widget:
  - text: pixel art, a cute corgi, simple, flat colors
---
# Pixel Art XL
## Consider supporting further research on [Patreon](https://www.patreon.com/user?u=29466374) or [Twitter](https://twitter.com/nerijs)

![F1hS8XHXwAQrMEW.jpeg](https://cdn-uploads.huggingface.co/production/uploads/6303f37c3926de1f7ec42d3e/SSOQ9lfB1PVhXVWJiL7Mx.jpeg)
![F1hS489X0AE-PK5.jpeg](https://cdn-uploads.huggingface.co/production/uploads/6303f37c3926de1f7ec42d3e/tY19J3xWDlSY2hhTTHySc.jpeg)


Downscale 8 times to get pixel perfect images (use Nearest Neighbors)
Use a fixed VAE to avoid artifacts (0.9 or fp16 fix)

### Need more performance?
Use it with a LCM Lora!

Use 8 steps and guidance scale of 1.5
1.2 Lora strength for the Pixel Art XL works better

```python
from diffusers import DiffusionPipeline, LCMScheduler
import torch

model_id = "stabilityai/stable-diffusion-xl-base-1.0"
lcm_lora_id = "latent-consistency/lcm-lora-sdxl"
pipe = DiffusionPipeline.from_pretrained(model_id, variant="fp16")
pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)

pipe.load_lora_weights(lcm_lora_id, adapter_name="lora")
pipe.load_lora_weights("./pixel-art-xl.safetensors", adapter_name="pixel")

pipe.set_adapters(["lora", "pixel"], adapter_weights=[1.0, 1.2])
pipe.to(device="cuda", dtype=torch.float16)

prompt = "pixel, a cute corgi"
negative_prompt = "3d render, realistic"

num_images = 9

for i in range(num_images):
    img = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=8,
        guidance_scale=1.5,
    ).images[0]
    
    img.save(f"lcm_lora_{i}.png")
```

### Tips:
Don't use refiner

Works great with only 1 text encoder

No style prompt required

No trigger keyword require

Works great with isometric and non-isometric

Works with 0.9 and 1.0

#### Changelog
v1: Initial release