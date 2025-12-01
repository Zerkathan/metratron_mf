# Script para verificar el estado del Dashboard
# Ejecutar desde PowerShell: .\VERIFICAR_ESTADO.ps1

Write-Host "🔍 Verificando estado del Dashboard..." -ForegroundColor Cyan
Write-Host ""

# Verificar puerto 8501
$portStatus = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($portStatus) {
    Write-Host "✅ Puerto 8501: EN USO" -ForegroundColor Green
    $portStatus | Select-Object LocalAddress, LocalPort, State, OwningProcess | Format-Table
    Write-Host "🌐 Dashboard disponible en: http://localhost:8501" -ForegroundColor Cyan
} else {
    Write-Host "❌ Puerto 8501: NO EN USO" -ForegroundColor Red
    Write-Host "💡 El dashboard no está corriendo. Ejecuta: .\INICIAR_DASHBOARD.ps1" -ForegroundColor Yellow
}

Write-Host ""

# Verificar proceso Streamlit
$streamlitProcess = Get-Process | Where-Object {$_.ProcessName -eq "streamlit"} -ErrorAction SilentlyContinue
if ($streamlitProcess) {
    Write-Host "✅ Proceso Streamlit: ACTIVO" -ForegroundColor Green
    $streamlitProcess | Select-Object Id, ProcessName, StartTime | Format-Table
} else {
    Write-Host "❌ Proceso Streamlit: NO ENCONTRADO" -ForegroundColor Red
}







