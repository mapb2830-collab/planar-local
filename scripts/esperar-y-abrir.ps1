$ErrorActionPreference = 'Stop'
Write-Host 'Esperando a que ambos servidores esten listos...'
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $api = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        $web = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173' -TimeoutSec 2
        $health = $api.Content | ConvertFrom-Json
        if ($api.StatusCode -eq 200 -and $health.status -eq 'ok' -and $web.StatusCode -eq 200 -and $web.Content -match 'PLANAR') {
            Start-Process 'http://127.0.0.1:5173'
            exit 0
        }
    } catch {
        # Startup is asynchronous; retry until both servers answer.
    }
    Start-Sleep -Seconds 1
}
Write-Host 'No respondieron ambos servidores. Revisa sus ventanas para ver el error.'
exit 1
