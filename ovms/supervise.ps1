# Mantiene vivo un proceso de OVMS: lo lanza y lo relanza si muere o si deja de responder
# (8 consultas seguidas a /v1/config sin respuesta, unos 3 minutos: un proceso caido que Windows retiene para
# el reporte de errores sigue vivo pero ya no atiende). Se detiene solo tras 3 caidas en 60 segundos.
#   -Oculto   sin ventana: lo que mostraria va a logs\<Name>.supervisor.log y no espera Enter al rendirse
param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][int]$Port, [Parameter(Mandatory)][string]$Config,
      [switch]$Oculto)

. (Join-Path $PSScriptRoot 'common.ps1')
if ($Oculto) { Start-Transcript -Path (Join-Path $LogsDir "$Name.supervisor.log") -Append | Out-Null }
$Host.UI.RawUI.WindowTitle = "OVMS $Name ($Port)"
Set-Content -Path (Join-Path $RunDir "$Name.supervisor.pid") -Value $PID
. (Join-Path $OvmsDir 'setupvars.ps1') | Out-Null

$caidas = @()
while ($true) {
    Write-Host "[$(Get-Date -Format HH:mm:ss)] Iniciando OVMS '$Name' en 127.0.0.1:$Port"
    $p = Start-Process -FilePath (Join-Path $OvmsDir 'ovms.exe') -NoNewWindow -PassThru -ArgumentList (
        "--rest_port $Port --rest_bind_address 127.0.0.1 --config_path `"$Config`" " +
        "--log_path `"$(Join-Path $LogsDir "$Name.log")`" --log_level INFO")
    $null = $p.Handle
    $fallos = 0
    while (-not $p.WaitForExit(15000)) {
        try { $null = Invoke-WebRequest "http://127.0.0.1:$Port/v1/config" -UseBasicParsing -TimeoutSec 10; $fallos = 0 }
        catch { $fallos++ }
        if ($fallos -ge 8) {
            Write-Host "[$(Get-Date -Format HH:mm:ss)] OVMS '$Name' no responde. Se termina." -ForegroundColor Yellow
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            $p.WaitForExit()
        }
    }
    $ahora = Get-Date
    Write-Host "[$($ahora.ToString('HH:mm:ss'))] OVMS '$Name' termino con codigo $($p.ExitCode)" -ForegroundColor Yellow
    $caidas = @($caidas | Where-Object { ($ahora - $_).TotalSeconds -lt 60 }) + $ahora
    if ($caidas.Count -ge 3) {
        Write-Host "[ovms] '$Name' cayo 3 veces en un minuto. No se relanza. Revisa $LogsDir\$Name.log" -ForegroundColor Red
        Remove-Item (Join-Path $RunDir "$Name.supervisor.pid") -Force -ErrorAction SilentlyContinue
        if (-not $Oculto) { Read-Host 'Enter para cerrar' }
        exit 1
    }
    Start-Sleep -Seconds 1
}
