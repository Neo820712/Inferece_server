@echo off
REM Arranca el servidor de inferencia compartido en http://127.0.0.1:8200/v1
REM Doble clic para usarlo. La ventana queda abierta sirviendo; cierrala para detenerlo.
title Servidor de Inferencia (OpenVINO)
set HERE=%~dp0
set VENV=%HERE%.venv

REM Modelo: Qwen3-30B-A3B si esta descargado (mejor espanol y seguimiento de
REM instrucciones a la misma velocidad); si no, el Qwen3-4B que instala setup.bat.
if "%INFERENCE_MODEL_DIR%"=="" if exist "%HERE%models\qwen3-30b-a3b-int4-ov\openvino_model.xml" set INFERENCE_MODEL_DIR=%HERE%models\qwen3-30b-a3b-int4-ov

if not exist "%VENV%\Scripts\python.exe" (
    echo No existe el entorno. Ejecuta setup.bat primero.
    pause
    exit /b 1
)

REM Dispositivo: GPU (iGPU Arc) por defecto. Cambia a NPU o CPU si lo necesitas.
if "%INFERENCE_DEVICE%"=="" set INFERENCE_DEVICE=GPU

REM Whisper: CPU por defecto. El decoder autoregresivo no arranca en la NPU con esta
REM version de OpenVINO (cae a CPU igual); usar WHISPER_DEVICE=NPU para reintentar en el futuro.
if "%WHISPER_DEVICE%"=="" set WHISPER_DEVICE=CPU

"%VENV%\Scripts\python.exe" "%HERE%server.py"
pause
