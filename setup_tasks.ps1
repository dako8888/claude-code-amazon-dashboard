# 创建 AmazonDashboard 计划任务
$ErrorActionPreference = "Stop"

$taskDir = "E:\WorkBuddy\amazon-dashboard"

# ── 任务1: 开机自启 ──
$action1 = New-ScheduledTaskAction -Execute "$taskDir\start_streamlit.bat"
$trigger1 = New-ScheduledTaskTrigger -AtStartup -RandomDelay (New-TimeSpan -Seconds 30)
$principal = New-ScheduledTaskPrincipal -UserId "Administrator" -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

Register-ScheduledTask `
    -TaskName "AmazonDashboard-Startup" `
    -Action $action1 `
    -Trigger $trigger1 `
    -Principal $principal `
    -Settings $settings `
    -Description "Streamlit Dashboard 开机自启 · Amazon Workflow" `
    -Force

# ── 任务2: 每5分钟健康检查 ──
$action2 = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$taskDir\healthcheck.ps1`""

$now = Get-Date
$startAt = $now.AddMinutes(1)
$startAtStr = $startAt.ToString("yyyy-MM-ddTHH:mm:ss")
$trigger2 = New-ScheduledTaskTrigger -Once -At $startAtStr -RepetitionInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName "AmazonDashboard-HealthCheck" `
    -Action $action2 `
    -Trigger $trigger2 `
    -Principal $principal `
    -Settings $settings `
    -Description "Dashboard 每5分钟健康检查 · 端口8501无响应自动拉起" `
    -Force

Write-Host "✓ 两个计划任务已创建成功"
Write-Host "  - AmazonDashboard-Startup   (开机自启)"
Write-Host "  - AmazonDashboard-HealthCheck (每5分钟健康检查)"
