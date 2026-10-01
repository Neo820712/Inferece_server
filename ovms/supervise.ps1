# Mantiene vivo un proceso de OVMS: lo lanza y lo relanza si muere.
# Se detiene solo tras 3 caidas en 60 segundos.
param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][int]$Port, [Parameter(Mandatory)][string]$Config)

. (Join-Path $PSScriptRoot 'common.ps1')
$Host.UI.RawUI.WindowTitle = "OVMS $Name ($Port)"
Set-Content -Path (Join-Path $RunDir "$Name.supervisor.pid") -Value $PID
. (Join-Path $OvmsDir 'setupvars.ps1') | Out-Null

$caidas = @()
while ($true) {
    Write-Host "[$(Get-Date -Format HH:mm:ss)] Iniciando OVMS '$Name' en 127.0.0.1:$Port"
    & (Join-Path $OvmsDir 'ovms.exe') --rest_port $Port --rest_bind_address 127.0.0.1 `
        --config_path $Config --log_path (Join-Path $LogsDir "$Name.log") --log_level INFO
    $ahora = Get-Date
    Write-Host "[$($ahora.ToString('HH:mm:ss'))] OVMS '$Name' termino con codigo $LASTEXITCODE" -ForegroundColor Yellow
    $caidas = @($caidas | Where-Object { ($ahora - $_).TotalSeconds -lt 60 }) + $ahora
    if ($caidas.Count -ge 3) {
        Write-Host "[ovms] '$Name' cayo 3 veces en un minuto. No se relanza. Revisa $LogsDir\$Name.log" -ForegroundColor Red
        Remove-Item (Join-Path $RunDir "$Name.supervisor.pid") -Force -ErrorAction SilentlyContinue
        Read-Host 'Enter para cerrar'
        exit 1
    }
    Start-Sleep -Seconds 1
}
