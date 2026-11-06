@echo off
rem Double-click this to stop the GTA card uploader. Your images are left alone.
powershell.exe -NoProfile -Command "Unregister-ScheduledTask -TaskName 'GTA card uploader' -Confirm:$false; Remove-Item -Recurse -Force 'D:\gta-media\.uploader' -ErrorAction SilentlyContinue; Write-Host 'Uploader removed.'; Read-Host 'Press Enter to close'"
