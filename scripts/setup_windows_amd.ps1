# Experimental, version-pinned Windows ROCm path; never modifies NVIDIA venv.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
function Run-Python {
    & $script:amdPython @args
    if ($LASTEXITCODE -ne 0) { throw 'Python/pip failed. Setup stopped; inspect the error above.' }
}
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows first.' }
if (-not (Get-Command py.exe -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12 with the py launcher first.' }
$ramGiB = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB
Write-Host ("Physical RAM: {0:N1} GiB. 32 GB installed RAM is the recommended starting point, not a guarantee." -f $ramGiB)
if ($ramGiB -lt 30) { throw 'Less than approximately 32 GB RAM detected. This installer does not support this configuration.' }
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion | Format-Table
Write-Host 'Experimental RX 9070 XT / Windows 11 path. Read AMD_INSTALL.md first.'
Write-Host 'Requires an AMD driver compatible with ROCm 7.2.1 (official guide specifies Adrenalin 26.2.2).'
if ((Read-Host 'Confirm compatible Windows/driver and installation into .venv-amd / ComfyUI-amd. Type INSTALL') -cne 'INSTALL') { exit 1 }
if (-not (Test-Path -LiteralPath '.venv-amd\Scripts\python.exe')) {
    & py.exe -3.12 -m venv .venv-amd
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 venv creation failed.' }
}
$script:amdPython = Join-Path (Get-Location) '.venv-amd\Scripts\python.exe'
Run-Python -c "import sys,struct; assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8, 'Python 3.12 x64 required'"
Run-Python -m pip install --upgrade pip
$base = 'https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1/'
Run-Python -m pip install ($base+'rocm_sdk_core-7.2.1-py3-none-win_amd64.whl') ($base+'rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl') ($base+'rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl') ($base+'rocm-7.2.1.tar.gz')
Run-Python -m pip install ($base+'torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl') ($base+'torchvision-0.24.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl') ($base+'torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl')
if (-not (Test-Path -LiteralPath 'ComfyUI-amd')) {
    & git.exe clone --depth 1 --branch v0.34.0 https://github.com/Comfy-Org/ComfyUI.git ComfyUI-amd
    if ($LASTEXITCODE -ne 0) { throw 'Pinned ComfyUI clone failed.' }
} elseif (-not (Test-Path -LiteralPath 'ComfyUI-amd\main.py')) {
    throw 'ComfyUI-amd exists but is incomplete. Inspect it manually before retrying.'
}
Run-Python -m pip install -c scripts/amd-constraints.txt -r ComfyUI-amd/requirements.txt -r requirements-tool.txt
Run-Python -m pip check
Run-Python -c "import torch; assert torch.version.hip, 'Not a ROCm build'; assert torch.cuda.is_available(), 'GPU unavailable'; print(torch.__version__, torch.version.hip, torch.cuda.get_device_name(0)); x=torch.ones((16,16),device='cuda'); print((x@x).sum().item()); torch.cuda.synchronize()"
Write-Host 'Runtime checks passed; H3 generation is NOT yet verified. Read AMD_INSTALL.md.'
Write-Host 'Next: download_h3_models_amd.bat (only with model authorization), then start_team_tool_amd.bat.'
