# Funciones compartidas por los scripts de OVMS. Se carga con dot-sourcing.

$script:Root = Join-Path $env:LOCALAPPDATA 'InferenceServer'
$script:OvmsDir = Join-Path $Root 'ovms'
$script:ModelsDir = Join-Path $Root 'models\OpenVINO'
$script:CacheDir = Join-Path $Root 'cache'
$script:ServablesDir = Join-Path $Root 'servables'
$script:RunDir = Join-Path $Root 'run'
$script:LogsDir = Join-Path $Root 'logs'
$script:Versions = Get-Content (Join-Path $PSScriptRoot 'versions.json') -Raw | ConvertFrom-Json

function Test-Port([int]$Port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try {
        $r = $c.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $r.AsyncWaitHandle.WaitOne(500)) { return $false }
        $c.EndConnect($r)
        return $true
    } catch { return $false } finally { $c.Close() }
}

# Procesos ovms.exe que no pertenecen a esta instalacion. Con uno vivo no se arranca nada:
# dos procesos sobre la NPU tumbaron el servidor en las pruebas.
function Get-ForeignOvms {
    Get-CimInstance Win32_Process -Filter "Name='ovms.exe'" |
        Where-Object { -not $_.ExecutablePath -or -not $_.ExecutablePath.StartsWith($OvmsDir, [StringComparison]::OrdinalIgnoreCase) }
}

function Assert-NoForeignOvms {
    $f = @(Get-ForeignOvms)
    if ($f.Count -gt 0) {
        Write-Host "[ovms] Hay otro ovms.exe en marcha que no es de esta instalacion (PID $($f.ProcessId -join ', '))." -ForegroundColor Red
        Write-Host "[ovms] Cerralo antes de continuar: nunca dos procesos sobre la NPU." -ForegroundColor Red
        exit 2
    }
}

function Get-ServableStates([int]$Port) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/config" -TimeoutSec 3
    } catch { return $null }
    $out = @{}
    foreach ($p in $r.PSObject.Properties) { $out[$p.Name] = $p.Value.model_version_status[0].state }
    return $out
}

# Espera a que los servables del proceso queden AVAILABLE. Devuelve $true o $false.
function Wait-Servables([string]$Name, [int]$TimeoutSec) {
    $proc = $Versions.processes.$Name
    $t = Get-Date
    while (((Get-Date) - $t).TotalSeconds -lt $TimeoutSec) {
        $s = Get-ServableStates $proc.port
        if ($s) {
            $ok = @($proc.servables | Where-Object { $s[$_] -eq 'AVAILABLE' }).Count
            Write-Host ("`r[ovms] {0}: {1}/{2} servables listos ({3:N0} s)   " -f $Name, $ok, $proc.servables.Count, ((Get-Date) - $t).TotalSeconds) -NoNewline
            if ($ok -eq $proc.servables.Count) { Write-Host ''; return $true }
        }
        Start-Sleep -Seconds 2
    }
    Write-Host ''
    return $false
}

function Stop-OvmsProcess([string]$Name) {
    $pidFile = Join-Path $RunDir "$Name.supervisor.pid"
    if (Test-Path $pidFile) {
        $sp = [int](Get-Content $pidFile)
        Stop-Process -Id $sp -Force -Confirm:$false -ErrorAction SilentlyContinue
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    $port = $Versions.processes.$Name.port
    Get-CimInstance Win32_Process -Filter "Name='ovms.exe'" |
        Where-Object { $_.CommandLine -match "--rest_port $port\b" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
}
