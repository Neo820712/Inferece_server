# Servidor de inferencia con OpenVINO Model Server

Variante multi-modelo del servidor de inferencia, sobre OpenVINO Model Server (OVMS)
2026.4. Convive con el servidor Flask de la raiz del repo: no lo reemplaza ni lo modifica.

## Indice

- [Que sirve](#que-sirve)
- [Requisitos](#requisitos)
- [Instalacion](#instalacion)
- [Arranque y parada](#arranque-y-parada)
- [Como lo usan los clientes](#como-lo-usan-los-clientes)
- [Perfil alternativo](#perfil-alternativo)
- [Reglas de operacion](#reglas-de-operacion)
- [Mediciones](#mediciones)

## Que sirve

Dos procesos, ambos solo en `127.0.0.1`:

| Proceso | Puerto | Servable | Modelo | Dispositivo |
|---|---|---|---|---|
| `main` | 8300 | `llm` | `OpenVINO/gemma-4-E4B-it-int4-ov` | GPU |
| `main` | 8300 | `embed` | `OpenVINO/Qwen3-Embedding-0.6B-int8-ov` | CPU |
| `main` | 8300 | `embed-ingest` | `OpenVINO/Qwen3-Embedding-0.6B-int8-ov` | GPU |
| `stt` | 8310 | `whisper` | `OpenVINO/whisper-large-v3-turbo-fp16-ov` | NPU |

Whisper corre en un proceso propio: un fallo del driver de la NPU cierra el proceso que lo
aloja, y asi solo se interrumpe la transcripcion.

Un tercer proceso opcional, `tts` (puerto 8320, `kokoro` en CPU), genera voz sintetica. Se
levanta con `tts.ps1 -Start` y se detiene con `tts.ps1 -Stop`.

## Requisitos

- Windows 11 en una AI PC Intel con NPU y GPU integrada, drivers al dia.
- 32 GB de RAM. Los dos procesos ocupan cerca de 11 GB.
- Microsoft Visual C++ Redistributable.
- Unos 15 GB libres en disco.

Todo lo pesado se instala en `%LOCALAPPDATA%\InferenceServer\` (binarios, modelos, cache y
logs), fuera de la carpeta del repo.

## Instalacion

Doble clic en `install.bat`. Descarga OVMS (verifica su hash), baja los modelos, genera los
servables desde `graphs/` y hace un primer arranque que compila las caches. La de la NPU
tarda unos 4 minutos y se hace una sola vez.

Con los archivos ya descargados (sin red):

```cmd
install.bat -ModelsFrom D:\modelos -OvmsZip D:\ovms_windows_2026.4.0_python_on.zip
```

`-ModelsFrom` espera una carpeta con una subcarpeta por modelo (con o sin el prefijo
`OpenVINO\`).

## Arranque y parada

```cmd
run.bat            lanza los procesos que falten y espera a que carguen
run.bat -Detach    los lanza y vuelve enseguida
stop.bat           detiene todo
stop.bat -Name stt detiene un proceso
```

Cada proceso corre en su ventana con un supervisor que lo relanza si muere. Tras tres
caidas en un minuto deja de relanzar y lo avisa.

Comprobacion:

```cmd
uv run --no-project --with httpx==0.28.1 --python 3.12 smoke.py
```

## Como lo usan los clientes

API estilo OpenAI. El campo `model` es obligatorio: sin el, OVMS responde 412.

| Tarea | Ruta | `model` |
|---|---|---|
| Chat | `POST http://127.0.0.1:8300/v3/chat/completions` | `llm` |
| Embeddings | `POST http://127.0.0.1:8300/v3/embeddings` | `embed` o `embed-ingest` |
| Voz a texto | `POST http://127.0.0.1:8310/v3/audio/transcriptions` | `whisper` |
| Estado | `GET http://127.0.0.1:<puerto>/v1/config` | |

Los embeddings rechazan con 400 las entradas de mas de 512 tokens. Mientras un proceso
carga, `/v1/config` responde `{}`.

## Perfil alternativo

`run.bat -Profile gpu` sirve Whisper en la GPU en vez de la NPU, para equipos donde la NPU
no este disponible. Comparte la GPU con el modelo de lenguaje, asi que la latencia de
transcripcion no esta garantizada.

## Reglas de operacion

- Nunca dos procesos usando la NPU a la vez. Los scripts no arrancan si encuentran un
  `ovms.exe` ajeno a esta instalacion.
- Para detener, usar `stop.bat`: matar `ovms.exe` a mano hace que el supervisor lo relance.
- El servidor Flask del puerto 8200 puede seguir existiendo, pero si corre al mismo tiempo
  comparte la GPU. `run.bat` lo avisa.
- No ejecutar `setupvars` de OVMS en una consola donde corra otro Python: fija `PYTHONHOME`.
- Esta rama no se fusiona a `master` hasta que sirva tambien el modelo con herramientas que
  usan los clientes actuales de Flask y pase `smoke_tools.py` contra OVMS.

## Mediciones

Core Ultra 7 268V, Arc 140V, NPU, 32 GB, 2026-10-01.

| Que | Valor |
|---|---|
| Primer arranque de `stt` (compila la cache de NPU) | 223 s |
| Primer arranque de `main` | 41 s |
| Arranque de ambos con cache | 20 s |
| Recuperacion de `stt` tras matar el proceso | 6,8 s |
| Arranque de `stt` en el perfil GPU | 17 s |
| Memoria de `main` y `stt` | 8,2 GB y 2,6 GB |
| Coseno entre el embedding de CPU y el de GPU del mismo texto | 0,9996 |
