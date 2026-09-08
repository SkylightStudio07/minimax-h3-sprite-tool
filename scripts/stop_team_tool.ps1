$ErrorActionPreference = 'Stop'
try {
    $listeners = @(Get-NetTCPConnection -LocalPort 7866 -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) {
        Write-Host 'Team server is not running on port 7866.'
        exit 0
    }
    $targets = @()
    foreach ($serverId in @($listeners.OwningProcess | Select-Object -Unique)) {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $serverId"
        if (!$processInfo -or $processInfo.Name -notmatch '^python(w)?\.exe$' -or
            $processInfo.CommandLine -notmatch '(?i)(?:^|[\s"\\/])team_server\.py(?=["\s]|$)') {
            throw "Port 7866 belongs to an unrecognized process ($serverId). Nothing was stopped."
        }
        $targets += $processInfo
    }
    Write-Host 'This stops the team web server only. ComfyUI will keep running.'
    Write-Host 'WARNING: Active jobs may be interrupted. Stop only after generation finishes.'
    $answer = Read-Host 'Stop the team server? Type YES to confirm'
    if ($answer -cne 'YES') {
        Write-Host 'Cancelled.'
        exit 0
    }
    foreach ($target in $targets) {
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($target.ProcessId)"
        if (!$current) { continue }
        if ($current.CreationDate -ne $target.CreationDate -or $current.CommandLine -ne $target.CommandLine) {
            throw 'Process changed during confirmation. Refusing to stop it.'
        }
        Stop-Process -Id $target.ProcessId -ErrorAction Stop
        Write-Host "Team server stopped (PID $($target.ProcessId))."
    }
} catch {
    Write-Host "Could not stop server: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
