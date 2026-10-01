# Instala OpenVINO Model Server, los modelos y los servables, y compila las caches.
#   -ModelsFrom <carpeta>  copia los modelos desde una carpeta local en vez de descargarlos
#   -OvmsZip <archivo>     usa un zip de OVMS ya descargado
#   -SkipWarmup            no hace el primer arranque que compila las caches
param([string]$ModelsFrom, [string]$OvmsZip, [switch]$SkipWarmup)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

Assert-NoForeignOvms
foreach ($n in 'main', 'stt') {
    if (Test-Port $Versions.processes.$n.port) {
        Write-Host "[instalar] El proceso '$n' esta en marcha. Ejecuta stop.bat antes de instalar." -ForegroundColor Red
        exit 2
    }
}

foreach ($d in $Root, $ModelsDir, $CacheDir, $ServablesDir, $RunDir, $LogsDir) {
    New-Item -ItemType Directory -Force $d | Out-Null
}

# 1. Binario de OVMS
if (-not (Test-Path (Join-Path $OvmsDir 'ovms.exe'))) {
    $zip = Join-Path $Root 'ovms.zip'
    if ($OvmsZip) {
        Write-Host "[instalar] Copiando OVMS desde $OvmsZip"
        Copy-Item $OvmsZip $zip -Force
    } else {
        Write-Host "[instalar] Descargando OVMS $($Versions.ovms.version)..."
        & curl.exe -L --fail --silent --show-error --connect-timeout 20 --max-time 1800 -o $zip $Versions.ovms.url
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo descargar OVMS.' }
    }
    $hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $Versions.ovms.sha256) { throw "El zip de OVMS no coincide con el hash esperado ($hash)." }
    & tar.exe -xf $zip -C $Root
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo descomprimir OVMS.' }
    Remove-Item $zip -Force
}
Write-Host "[instalar] OVMS listo en $OvmsDir"

# 2. Modelos
. (Join-Path $OvmsDir 'setupvars.ps1') | Out-Null
foreach ($m in $Versions.models) {
    $name = $m.id.Split('/')[1]
    $dest = Join-Path $ModelsDir $name
    if (@(Get-ChildItem $dest -Filter '*.xml' -Recurse -ErrorAction SilentlyContinue).Count -gt 0) {
        Write-Host "[instalar] Modelo presente: $name"
        continue
    }
    $local = $null
    if ($ModelsFrom) {
        $local = @((Join-Path $ModelsFrom $name), (Join-Path $ModelsFrom "OpenVINO\$name")) |
            Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if ($local) {
        Write-Host "[instalar] Copiando $name desde $local"
        Copy-Item $local $dest -Recurse -Force
    } else {
        Write-Host "[instalar] Descargando $($m.id)..."
        & ovms --pull --source_model $m.id --model_repository_path (Join-Path $Root 'models') --model_name $name @($m.pull)
        if ($LASTEXITCODE -ne 0) { throw "No se pudo descargar $($m.id)." }
    }
}

# 3. Servables: un grafo por servable, generado desde las plantillas del repo
$models = $ModelsDir.Replace('\', '/')
$cache = $CacheDir.Replace('\', '/')
foreach ($g in Get-ChildItem (Join-Path $PSScriptRoot 'graphs') -Directory) {
    $dir = Join-Path $ServablesDir $g.Name
    New-Item -ItemType Directory -Force $dir | Out-Null
    $txt = (Get-Content (Join-Path $g.FullName 'graph.pbtxt') -Raw).Replace('{{MODELS}}', $models).Replace('{{CACHE}}', $cache)
    [IO.File]::WriteAllText((Join-Path $dir 'graph.pbtxt'), $txt)
}

function Write-Config([string]$File, [hashtable]$Map) {
    $list = foreach ($k in $Map.Keys) {
        @{ config = @{ name = $k; base_path = (Join-Path $ServablesDir $Map[$k]).Replace('\', '/') } }
    }
    $json = @{ model_config_list = @($list) } | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText((Join-Path $Root $File), $json)
}
Write-Config 'config_main.json' @{ llm = 'llm'; embed = 'embed'; 'embed-ingest' = 'embed-ingest' }
Write-Config 'config_stt.json' @{ whisper = 'whisper' }
Write-Config 'config_stt_gpu.json' @{ whisper = 'whisper-gpu' }
Write-Config 'config_tts.json' @{ kokoro = 'kokoro' }
Write-Host '[instalar] Servables y configuracion generados.'

# 4. Primer arranque: compila las caches (la de NPU tarda varios minutos, una sola vez)
if (-not $SkipWarmup) {
    foreach ($n in 'stt', 'main') {
        $port = $Versions.processes.$n.port
        Write-Host "[instalar] Compilando cache de '$n' (puede tardar varios minutos)..."
        $p = Start-Process -FilePath (Join-Path $OvmsDir 'ovms.exe') -PassThru -WindowStyle Hidden -ArgumentList @(
            '--rest_port', $port, '--rest_bind_address', '127.0.0.1',
            '--config_path', "`"$(Join-Path $Root "config_$n.json")`"",
            '--log_path', "`"$(Join-Path $LogsDir "install_$n.log")`"")
        $ok = Wait-Servables $n 900
        Stop-Process -Id $p.Id -Force -Confirm:$false -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
        if (-not $ok) { throw "El proceso '$n' no quedo disponible. Revisa $LogsDir\install_$n.log" }
    }
}
Write-Host '[instalar] Servidor de inferencia instalado.' -ForegroundColor Green
