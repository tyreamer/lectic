# Opt-in, per-user scheduled updates. No administrator privileges or password storage.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Destination,
    [string]$Python = '',
    [switch]$Disable
)
$ErrorActionPreference = 'Stop'
if (-not $Python) { $Python = (Get-Command python -ErrorAction Stop).Source }
$Python = (Resolve-Path -LiteralPath $Python).Path
$Destination = (Resolve-Path -LiteralPath $Destination).Path
if ((Split-Path -Leaf $Destination) -notin @('lectic', 'expertise-compiler')) {
    throw 'Expected the installed lectic (or legacy expertise-compiler) skill directory.'
}
$lecticUpdater = Join-Path $Destination 'scripts/update_skill.py'
$lecticStatusText = & $Python -B $lecticUpdater status --dest $Destination
if ($LASTEXITCODE -ne 0) { throw 'Could not verify the installed Lectic copy.' }
$lecticStatus = ($lecticStatusText -join "`n") | ConvertFrom-Json
if (($lecticStatus.status -ne 'managed' -and -not $Disable) -or -not $lecticStatus.installed_commit -or $lecticStatus.recovery_pending) {
    throw 'First run update_skill.py update --adopt for a clean, managed installation.'
}
$lecticState = $lecticStatus.state_directory
$lecticRunner = Join-Path $lecticState 'runner.py'
$lecticPythonWindowless = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $lecticPythonWindowless -PathType Leaf)) {
    throw 'pythonw.exe is required so scheduled checks do not open a terminal window.'
}
$lecticHasher = [System.Security.Cryptography.SHA256]::Create()
try {
    $lecticHash = [BitConverter]::ToString($lecticHasher.ComputeHash(
        [System.Text.Encoding]::UTF8.GetBytes($Destination.ToLowerInvariant()))).Replace('-', '').Substring(0, 8)
} finally { $lecticHasher.Dispose() }
$lecticTaskName = "Lectic Skill Update $lecticHash"
$lecticArguments = '-B "' + $lecticRunner + '" run --dest "' + $Destination + '" --state-dir "' + $lecticState + '"'
$lecticService = New-Object -ComObject 'Schedule.Service'
$lecticService.Connect()
$lecticFolder = $lecticService.GetFolder('\')
$lecticExisting = $null
try { $lecticExisting = $lecticFolder.GetTask($lecticTaskName) } catch {
    if ($_.Exception.HResult -notin @(-2147024894, -2147024893)) { throw }
}
if ($lecticExisting) {
    $lecticAction = $lecticExisting.Definition.Actions.Item(1)
    if ($lecticExisting.Definition.Actions.Count -ne 1 -or
        $lecticAction.Path -ne $lecticPythonWindowless -or $lecticAction.Arguments -ne $lecticArguments) {
        throw 'A different task already uses this name. It was left unchanged.'
    }
}
if ($Disable) {
    & $Python -B $lecticRunner pause --dest $Destination --state-dir $lecticState
    if ($LASTEXITCODE -ne 0) { throw 'Could not pause updates.' }
    if ($lecticExisting) { $lecticFolder.DeleteTask($lecticTaskName, 0) }
    Write-Output 'Lectic automatic updates disabled; installation and backups retained.'
    exit 0
}
$lecticUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$lecticTask = $lecticService.NewTask(0)
$lecticTask.RegistrationInfo.Description = 'Update the installed Lectic skill from tyreamer/lectic main. No collection processing or AI calls.'
$lecticTask.Principal.UserId = $lecticUser
$lecticTask.Principal.LogonType = 3 # Interactive token: only while this user is logged in.
$lecticTask.Principal.RunLevel = 0
$lecticTask.Settings.Enabled = $true
$lecticTask.Settings.StartWhenAvailable = $true
$lecticTask.Settings.DisallowStartIfOnBatteries = $false
$lecticTask.Settings.StopIfGoingOnBatteries = $false
$lecticTask.Settings.MultipleInstances = 2 # IgnoreNew; runner also holds an OS file lock.
$lecticTask.Settings.ExecutionTimeLimit = 'PT5M'
$lecticTrigger = $lecticTask.Triggers.Create(2) # Daily trigger, with cheap hourly due checks.
$lecticTrigger.StartBoundary = (Get-Date).Date.AddHours(9).ToString('s')
$lecticTrigger.DaysInterval = 1
$lecticTrigger.Repetition.Interval = 'PT1H'
$lecticTrigger.Repetition.Duration = 'P1D'
$lecticLogon = $lecticTask.Triggers.Create(9)
$lecticLogon.UserId = $lecticUser
$lecticLogon.Delay = 'PT2M'
$lecticAction = $lecticTask.Actions.Create(0)
$lecticAction.Path = $lecticPythonWindowless
$lecticAction.Arguments = $lecticArguments
$lecticAction.WorkingDirectory = $lecticState
$null = $lecticFolder.RegisterTaskDefinition($lecticTaskName, $lecticTask, 6, $lecticUser, $null, 3)
& $Python -B $lecticRunner enable --dest $Destination --state-dir $lecticState --interval-hours 24 --task-name $lecticTaskName
if ($LASTEXITCODE -ne 0) {
    $lecticFolder.GetTask($lecticTaskName).Enabled = $false
    throw 'Could not enable the update receipt; the scheduled task was disabled.'
}
$lecticRegistered = $lecticFolder.GetTask($lecticTaskName)
[PSCustomObject]@{
    TaskName = $lecticTaskName
    Enabled = $lecticRegistered.Enabled
    NextRunTime = $lecticRegistered.NextRunTime
    NetworkCheck = 'At most once every 24 hours while logged in; hourly wake-up and at logon'
} | ConvertTo-Json
