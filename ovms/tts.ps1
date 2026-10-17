# Proceso temporal de voz sintetica (Kokoro en CPU, puerto 8320). No forma parte de la demo:
# solo lo usa el script que genera las llamadas de ejemplo.
param([switch]$Start, [switch]$Stop)

. (Join-Path $PSScriptRoot 'common.ps1')
$port = $Versions.processes.tts.port

if ($Stop) {
    Stop-OvmsProcess 'tts'
    exit 0
}
if (Test-Port $port) { Write-Host '[tts] Ya esta en marcha.'; exit 0 }
Assert-NoForeignOvms
. (Join-Path $OvmsDir 'setupvars.ps1') | Out-Null
Start-Process -FilePath (Join-Path $OvmsDir 'ovms.exe') -WindowStyle Hidden -ArgumentList @(
    '--rest_port', $port, '--rest_bind_address', '127.0.0.1',
    '--config_path', "`"$(Join-Path $Root 'config_tts.json')`"",
    '--log_path', "`"$(Join-Path $LogsDir 'tts.log')`"")
if (-not (Wait-Servables 'tts' 300)) {
    Write-Host "[tts] Kokoro no quedo disponible. Revisa $LogsDir\tts.log" -ForegroundColor Red
    exit 1
}
