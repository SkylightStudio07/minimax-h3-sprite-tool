$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    throw 'Git is required. Install Git for Windows, then run this script again.'
}

$pythonCommand = $null
if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $pythonCommand = @('py.exe', '-3.12')
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    $pythonCommand = @('python.exe')
} else {
    throw 'Python 3.12 is required. Install it from python.org, then run this script again.'
}

if (-not (Test-Path -LiteralPath 'ComfyUI\main.py')) {
    Write-Host 'Cloning ComfyUI...'
    & git.exe clone --depth 1 https://github.com/Comfy-Org/ComfyUI.git ComfyUI
    if ($LASTEXITCODE -ne 0) { throw 'ComfyUI clone failed.' }
}

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    Write-Host 'Creating Python virtual environment...'
    if ($pythonCommand.Count -eq 2) {
        & $pythonCommand[0] $pythonCommand[1] -m venv .venv
    } else {
        & $pythonCommand[0] -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
Write-Host 'Installing PyTorch CUDA 13.0 build...'
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }

Write-Host 'Installing ComfyUI and sprite-tool dependencies...'
& $venvPython -m pip install -r 'ComfyUI\requirements.txt' -r 'requirements-tool.txt'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

Write-Host ''
Write-Host 'Setup complete.' -ForegroundColor Green
Write-Host 'Next: run download_h3_models.bat only after confirming MiniMax authorization.'
