# Script para iniciar el Dashboard de Metratron Bot
# Ejecutar desde PowerShell: .\INICIAR_DASHBOARD.ps1

Write-Host "🚀 Iniciando Dashboard de Metratron Bot..." -ForegroundColor Green

# Activar entorno virtual
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "✅ Activando entorno virtual..." -ForegroundColor Yellow
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "⚠️ Entorno virtual no encontrado. Usando Python global." -ForegroundColor Yellow
}

# Verificar si ya está corriendo
$existingProcess = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($existingProcess) {
    Write-Host "⚠️ El dashboard ya está corriendo en el puerto 8501" -ForegroundColor Yellow
    Write-Host "🌐 Accede a: http://localhost:8501" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "¿Deseas detenerlo primero? (S/N)"
    $response = Read-Host
    if ($response -eq "S" -or $response -eq "s") {
        Get-Process | Where-Object {$_.ProcessName -eq "streamlit"} | Stop-Process -Force
        Start-Sleep -Seconds 2
        Write-Host "✅ Proceso detenido. Reiniciando..." -ForegroundColor Green
    } else {
        exit
    }
}

# Iniciar dashboard
Write-Host "📊 Iniciando Streamlit Dashboard..." -ForegroundColor Cyan
& .\.venv\Scripts\streamlit.exe run dashboard.py







