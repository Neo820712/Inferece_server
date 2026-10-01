# Lanza los procesos de OVMS que no esten en marcha, cada uno en su ventana con supervisor.
#   -Detach        vuelve enseguida sin esperar a que los modelos carguen
#   -Profile gpu   sirve Whisper en GPU en vez de NPU (metas de latencia no garantizadas)
param([switch]$Detach, [ValidateSet('npu', 'gpu')][string]$Profile = 'npu')

. (Join-Path $PSScriptRoot 'common.ps1')

if (-not (Test-Path (Join-Path $Root 'config_main.json'))) {
    Write-Host '[ovms] El servidor no esta instalado. Ejecuta install.bat primero.' -ForegroundColor Red
    exit 1
}
Assert-NoForeignOvms
if (Test-Port 8200) {
    Write-Host '[ovms] Aviso: hay un servidor en el puerto 8200 (Flask). Comparte la GPU con este y lo vuelve mas lento.' -ForegroundColor Yellow
}

$sttConfig = if ($Profile -eq 'gpu') { 'config_stt_gpu.json' } else { 'config_stt.json' }
$procesos = @(
    @{ Name = 'main'; Config = 'config_main.json' },
    @{ Name = 'stt'; Config = $sttConfig }
)
foreach ($p in $procesos) {
    $port = $Versions.processes.($p.Name).port
    if (Test-Port $port) {
        Write-Host "[ovms] '$($p.Name)' ya esta escuchando en $port."
        continue
    }
    Start-Process powershell -WindowStyle Minimized -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$(Join-Path $PSScriptRoot 'supervise.ps1')`"",
        '-Name', $p.Name, '-Port', $port, '-Config', "`"$(Join-Path $Root $p.Config)`"")
    Write-Host "[ovms] Lanzado '$($p.Name)' en 127.0.0.1:$port."
}

if (-not $Detach) {
    foreach ($p in $procesos) {
        if (-not (Wait-Servables $p.Name 900)) {
            Write-Host "[ovms] '$($p.Name)' no quedo disponible. Revisa $LogsDir\$($p.Name).log" -ForegroundColor Red
            exit 1
        }
    }
    Write-Host '[ovms] Servidor de inferencia listo.' -ForegroundColor Green
}
