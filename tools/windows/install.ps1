# One-time setup for the GTA card uploader. Run it by double-clicking install.bat.
#
# It creates D:\gta-media, saves your GitHub token encrypted for this Windows
# account only, and adds a task that checks the folder every 5 minutes.
# Plain ASCII on purpose (Windows PowerShell 5.1).

param([string]$Root = 'D:\gta-media')
$ErrorActionPreference = 'Stop'
$From = Split-Path -Parent $MyInvocation.MyCommand.Path
$Here = Join-Path $Root '.uploader'

Write-Host ''
Write-Host 'GTA card uploader setup' -ForegroundColor Green
Write-Host "Drop folder: $Root"
Write-Host ''

foreach ($d in @($Root, $Here, (Join-Path $Root 'uploaded'))) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}
(Get-Item -Force $Here).Attributes = 'Hidden, Directory'
foreach ($f in @('upload.ps1', 'run-hidden.vbs')) {
    Copy-Item -Path (Join-Path $From $f) -Destination (Join-Path $Here $f) -Force
    Unblock-File -Path (Join-Path $Here $f)
}

# The token: typed here, encrypted with Windows DPAPI, readable only by this
# Windows account on this PC. It never goes anywhere but GitHub.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
while ($true) {
    $secure = Read-Host 'Paste your GitHub token (it will not show) and press Enter' -AsSecureString
    $bstr  = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    try {
        $h = @{ Authorization = "Bearer $token"; 'User-Agent' = 'gta-card-uploader'; Accept = 'application/vnd.github+json' }
        Invoke-RestMethod -Uri 'https://api.github.com/repos/chanhofai/gta-media/git/ref/heads/main' -Headers $h -UseBasicParsing | Out-Null
        break
    } catch {
        Write-Host 'That token cannot see chanhofai/gta-media. Check it and try again.' -ForegroundColor Yellow
    }
}
$secure | ConvertFrom-SecureString | Set-Content -Path (Join-Path $Here 'token.txt')
Write-Host 'Token saved.' -ForegroundColor Green

# Every 5 minutes, and at log-on. Runs as you, only while you are logged in,
# which is what lets it read the encrypted token.
$action   = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + (Join-Path $Here 'run-hidden.vbs') + '"')
$every    = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$logon    = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName 'GTA card uploader' -Action $action -Trigger @($every, $logon) -Settings $settings -Description 'Sends images dropped into D:\gta-media to github.com/chanhofai/gta-media' -Force | Out-Null
Start-ScheduledTask -TaskName 'GTA card uploader'

Write-Host ''
Write-Host 'Done.' -ForegroundColor Green
Write-Host "Drop PNGs named like gta-2026-11-07.png into $Root."
Write-Host 'Within 5 minutes they go to GitHub and move into the uploaded folder.'
Write-Host "Check $Root\upload-log.txt to see what happened."
Write-Host ''
Read-Host 'Press Enter to close'
