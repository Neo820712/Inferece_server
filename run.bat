@echo off
REM Arranca el servidor de inferencia compartido en http://127.0.0.1:8200/v1
REM Doble clic para usarlo. La ventana queda abierta sirviendo; cierrala para detenerlo.
title Servidor de Inferencia (Qwen3-4B / OpenVINO)
set HERE=%~dp0
set VENV=%HERE%.venv

if not exist "%VENV%\Scripts\python.exe" (
    echo No existe el entorno. Ejecuta setup.bat primero.
    pause
    exit /b 1
)

REM Dispositivo: GPU (iGPU Arc) por defecto. Cambia a NPU o CPU si lo necesitas.
if "%INFERENCE_DEVICE%"=="" set INFERENCE_DEVICE=GPU

REM Whisper: NPU por defecto (el LLM usa la iGPU). Cae a CPU si NPU falla.
if "%WHISPER_DEVICE%"=="" set WHISPER_DEVICE=NPU

"%VENV%\Scripts\python.exe" "%HERE%server.py"
pause
