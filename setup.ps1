# setup.ps1 -- one-time setup on a new Windows laptop.
# Run from this folder:  powershell -ExecutionPolicy Bypass -File setup.ps1
#
# It creates the Python environment, installs dependencies, and registers the
# two windowless scheduled tasks (JobMonitor 8am/6pm, JobKitBuilder 9am/7pm).

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Write-Host "Setting up job-system in: $root`n"

# 1) Find Python (needs 3.10+). Install from python.org first if this fails.
$python = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = "python" }
if (-not $python) {
    Write-Host "ERROR: Python not found. Install it from https://python.org (tick 'Add Python to PATH'), then re-run." -ForegroundColor Red
    exit 1
}
Write-Host "Using Python: $python"

# 2) Create the virtual environment (fresh).
$venv = Join-Path $root ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment (.venv)..."
    & $python -m venv $venv
} else {
    Write-Host ".venv already exists - reusing it."
}
$py = Join-Path $venv "Scripts\python.exe"

# 3) Install dependencies.
Write-Host "Installing dependencies..."
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $root "requirements.txt") --quiet
Write-Host "Dependencies installed."

# 4) Register the two windowless scheduled tasks.
$pw = Join-Path $venv "Scripts\pythonw.exe"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

$mAction = New-ScheduledTaskAction -Execute $pw -Argument "fetch_jobs.py" -WorkingDirectory $root
$mTriggers = @((New-ScheduledTaskTrigger -Daily -At 8:00am), (New-ScheduledTaskTrigger -Daily -At 6:00pm))
Register-ScheduledTask -TaskName "JobMonitor" -Action $mAction -Trigger $mTriggers -Settings $settings -Principal $principal -Description "Find new India SWE roles 2x/day and alert (windowless)." -Force | Out-Null

$kAction = New-ScheduledTaskAction -Execute $pw -Argument "approvals.py" -WorkingDirectory $root
$kTriggers = @((New-ScheduledTaskTrigger -Daily -At 9:00am), (New-ScheduledTaskTrigger -Daily -At 7:00pm))
Register-ScheduledTask -TaskName "JobKitBuilder" -Action $kAction -Trigger $kTriggers -Settings $settings -Principal $principal -Description "Build kits for tapped roles 2x/day (windowless)." -Force | Out-Null

Write-Host "`nDone! Tasks registered:" -ForegroundColor Green
Get-ScheduledTask -TaskName "JobMonitor","JobKitBuilder" | Select-Object TaskName, State | Format-Table -AutoSize

Write-Host "Quick test (optional):  .\.venv\Scripts\python.exe fetch_jobs.py"
Write-Host "Check config.local.json has your gemini_api_key, ntfy_topic, and resume_link."
