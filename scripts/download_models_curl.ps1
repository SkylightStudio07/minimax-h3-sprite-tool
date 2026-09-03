$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$comfyModels = Join-Path $root 'ComfyUI\models'
$licenseMarker = Join-Path $root 'MINIMAX_H3_LICENSE_APPROVED.txt'
if (-not (Test-Path -LiteralPath $licenseMarker)) {
    throw 'MiniMax H3 license confirmation is missing.'
}

$downloads = @(
    @{
        Path = 'diffusion_models\minimax_h3_fl2va_pruned_int8_convrot.safetensors'
        Url = 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors'
    },
    @{
        Path = 'text_encoders\qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
        Url = 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
    },
    @{
        Path = 'vae\minimax_h3_video_vae_fp16.safetensors'
        Url = 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors'
    },
    @{
        Path = 'vae\minimax_h3_audio_vae_fp32.safetensors'
        Url = 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors'
    },
    @{
        Path = 'loras\minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors'
        Url = 'https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors'
    }
)

foreach ($download in $downloads) {
    $destination = Join-Path $comfyModels $download.Path
    $partial = "$destination.part"
    $directory = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    if (Test-Path -LiteralPath $destination) {
        Write-Host "Already present: $destination"
        continue
    }
    Write-Host "Downloading: $($download.Path)"
    & curl.exe --location --fail --show-error --progress-bar `
        --retry 100 --retry-all-errors --retry-delay 5 `
        --continue-at - --output $partial $download.Url
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed with curl exit code $LASTEXITCODE"
    }
    Move-Item -LiteralPath $partial -Destination $destination
    Write-Host "Ready: $destination"
}

Write-Host 'All MiniMax H3 model files are ready.'
