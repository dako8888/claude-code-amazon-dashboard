Unregister-ScheduledTask -TaskName "AmazonDashboard-HealthCheck" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "AmazonDashboard-Startup" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Both tasks removed"
