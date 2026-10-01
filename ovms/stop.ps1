# Detiene los procesos de OVMS de esta instalacion: primero el supervisor, luego ovms.exe.
#   -Name main|stt|tts   detiene solo ese proceso
param([ValidateSet('main', 'stt', 'tts')][string]$Name)

. (Join-Path $PSScriptRoot 'common.ps1')
$nombres = if ($Name) { @($Name) } else { @('main', 'stt', 'tts') }
foreach ($n in $nombres) { Stop-OvmsProcess $n }
Start-Sleep -Seconds 2
Write-Host "[ovms] Detenido: $($nombres -join ', ')."
