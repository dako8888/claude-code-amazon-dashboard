# Dashboard 健康检查 — 端口8501没响应就拉起
$port = 8501
$url = "http://localhost:$port"
$logFile = "E:\WorkBuddy\amazon-dashboard\healthcheck.log"

try {
    $response = Invoke-WebRequest -Uri $url -TimeoutSec 10 -UseBasicParsing
    if ($response.StatusCode -ne 200) {
        throw "Status: $($response.StatusCode)"
    }
} catch {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts | Dashboard 无响应，正在重启..." | Out-File -Append -Encoding UTF8 $logFile
    Start-Process -FilePath "E:\WorkBuddy\amazon-dashboard\start_streamlit.bat" -WindowStyle Hidden
}
