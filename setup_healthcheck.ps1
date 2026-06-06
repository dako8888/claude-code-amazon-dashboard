$tr = @'
powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File "E:\WorkBuddy\amazon-dashboard\healthcheck.ps1"
'@

& schtasks.exe /create /tn "AmazonDashboard-HealthCheck" /tr $tr /sc MINUTE /mo 5 /ru Administrator /f
Write-Host "Done"
