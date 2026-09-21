param([switch]$DownloadModels)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath 'vendor\YuE\pyproject.toml')) {
    git.exe clone --depth 1 https://github.com/multimodal-art-projection/YuE.git vendor/YuE
    if ($LASTEXITCODE -ne 0) { throw 'YuE2 clone failed.' }
}

if (-not (Test-Path -LiteralPath '.venv-yue2\Scripts\python.exe')) {
    py.exe -3.12 -m venv .venv-yue2
    if ($LASTEXITCODE -ne 0) { throw 'YuE2 virtual environment creation failed.' }
}

$python = Join-Path $projectRoot '.venv-yue2\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install '.\vendor\YuE'
if ($LASTEXITCODE -ne 0) { throw 'YuE2 dependency installation failed.' }
$torchVersion = & $python -c "import torch; print(torch.__version__)"
if ($torchVersion.Trim() -ne '2.10.0+cu130') {
    & $python -m pip install --upgrade --force-reinstall 'torch==2.10.0+cu130' --index-url 'https://download.pytorch.org/whl/cu130'
    if ($LASTEXITCODE -ne 0) { throw 'YuE2 CUDA PyTorch installation failed.' }
}

if ($DownloadModels) {
    & $python '.\tools\download_yue2_models.py'
    if ($LASTEXITCODE -ne 0) { throw 'YuE2 model download failed.' }
}

Write-Host 'YuE2 runtime setup complete.' -ForegroundColor Green
if (-not $DownloadModels) {
    Write-Host 'Review the YuE2 model license, then run setup_yue2.bat -DownloadModels.'
}
