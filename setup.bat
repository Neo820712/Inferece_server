@echo off
REM Prepara el servidor de inferencia: crea el venv, instala dependencias y obtiene el modelo.
REM Ejecutar UNA VEZ (requiere internet solo si hay que descargar el modelo).
title Setup - Servidor de Inferencia
set HERE=%~dp0
set VENV=%HERE%.venv
set PY=C:\Program Files\Python312\python.exe
set MODEL=%HERE%models\qwen3-4b-int4-ov
REM Copia local opcional del modelo para evitar descargarlo. Define MODEL_SRC con la ruta
REM a una carpeta que contenga el modelo OV; si no se define, se descarga de HuggingFace.
set SRC=%MODEL_SRC%

echo [setup] Creando entorno virtual en %VENV%
"%PY%" -m venv "%VENV%"
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install -r "%HERE%requirements.txt"
if errorlevel 1 (
    echo [setup] Fallo la instalacion de dependencias. Revisa el error de arriba.
    pause
    exit /b 1
)

if exist "%MODEL%\openvino_model.bin" (
    echo [setup] El modelo ya esta presente. Nada que descargar.
    goto fin
)
if exist "%SRC%\openvino_model.bin" (
    echo [setup] Copiando el modelo desde el proyecto comparativa (sin descargar de internet)...
    robocopy "%SRC%" "%MODEL%" /E >nul
    goto fin
)
echo [setup] Descargando modelo Qwen3-4B INT4 OV (preconvertido)...
"%VENV%\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; snapshot_download('OpenVINO/Qwen3-4B-int4-ov', local_dir=r'%MODEL%')"

:fin
echo.
echo [setup] Listo. Arranca el servidor con run.bat
pause
