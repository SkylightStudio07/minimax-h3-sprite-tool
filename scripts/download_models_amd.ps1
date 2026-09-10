$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv-amd\Scripts\python.exe')) { throw 'Run setup_windows_amd.bat first.' }
if (-not (Test-Path -LiteralPath 'MINIMAX_H3_LICENSE_APPROVED.txt')) {
    Write-Host 'Review the MiniMax H3 license and obtain any required separate authorization BEFORE downloading.'
    if ((Read-Host 'Type LICENSE-APPROVED only if you have the required model usage rights') -cne 'LICENSE-APPROVED') { exit 1 }
    # This marker is local only, never a grant of rights.
    'User confirmed model authorization.' | Set-Content -LiteralPath 'MINIMAX_H3_LICENSE_APPROVED.txt'
}
$env:SPRITE_BACKEND='amd'
& '.venv-amd\Scripts\python.exe' 'scripts\download_models.py'
if ($LASTEXITCODE -ne 0) { throw 'Download failed. Resolve access/network errors, then retry.' }
