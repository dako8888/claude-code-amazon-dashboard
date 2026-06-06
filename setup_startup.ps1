$startupDir = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupDir "AmazonDashboard-Watchdog.lnk"
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = "E:\WorkBuddy\amazon-dashboard\start_watchdog.vbs"
$sc.WorkingDirectory = "E:\WorkBuddy\amazon-dashboard"
$sc.WindowStyle = 7
$sc.Save()
Write-Host "Startup shortcut created: $shortcutPath"
