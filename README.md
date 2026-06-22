# Servidor de Inferencia (compartido)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![OpenVINO](https://img.shields.io/badge/OpenVINO-2026.0-0068B5?logo=intel&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![Modelo](https://img.shields.io/badge/Modelo-Qwen3--4B%20INT4-00C7FD)

Servicio local de inferencia LLM, **OpenAI-compatible**, pensado para que **varios
programas** lo compartan. Corre un modelo Qwen3-4B INT4 sobre **OpenVINO** en la iGPU Intel
(Lunar Lake). Todo es local: el servidor solo escucha en `127.0.0.1` (loopback) y nada sale
a internet en tiempo de ejecucion.

## Indice

- [Que es](#que-es)
- [Requisitos](#requisitos)
- [Instalacion](#instalacion)
- [Arranque](#arranque)
- [Como lo usan otros programas](#como-lo-usan-otros-programas)
- [Configuracion](#configuracion)
- [Limites y evolucion](#limites-y-evolucion)

## Que es

Un proceso aparte que expone dos endpoints estilo OpenAI en `http://127.0.0.1:8200/v1`:

- `POST /v1/chat/completions` — generacion de chat (soporta `stream` y `tools`).
- `GET /v1/models` — health check / modelo cargado.

Al ser un servicio independiente, el modelo se carga **una sola vez** y queda residente,
disponible para cualquier aplicacion cliente sin recargarse.

## Requisitos

- Windows con Python 3.12 instalado.
- iGPU Intel (Arc/Xe2) para aceleracion; tambien corre en CPU si hace falta.
- Espacio en disco para el modelo (~2.3 GB).

## Instalacion

Una vez:

```cmd
setup.bat
```

Crea el entorno `.venv`, instala dependencias y obtiene el modelo. Si ya tienes el modelo
descargado en el proyecto `otro proyecto local`, lo **copia** desde ahi (no vuelve a
descargar); si no, lo baja de Hugging Face (`OpenVINO/Qwen3-4B-int4-ov`).

## Arranque

Doble clic en `run.bat` (o desde terminal). Abre una ventana que queda sirviendo; tarda
~20 s en cargar el modelo y luego muestra:

```
[inference] Listo. Escuchando en http://127.0.0.1:8200/v1
```

Deja esa ventana abierta mientras lo uses. Cierrala para detener el servicio.

Medir latencia sin levantar el servidor (opcional):

```cmd
.venv\Scripts\python.exe smoke.py
```

## Como lo usan otros programas

Cualquier cliente que hable el API de OpenAI funciona apuntando a `http://127.0.0.1:8200/v1`.

PowerShell:
```powershell
(Invoke-RestMethod -Uri http://127.0.0.1:8200/v1/chat/completions -Method Post -ContentType "application/json" -Body '{"messages":[{"role":"user","content":"En una frase, que es un procesador?"}]}').choices[0].message.content
```

curl (usa `curl.exe`, no el alias de PowerShell):
```powershell
curl.exe -X POST http://127.0.0.1:8200/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hola"}]}'
```

Python (libreria `requests`):
```python
import requests
r = requests.post("http://127.0.0.1:8200/v1/chat/completions",
                  json={"messages": [{"role": "user", "content": "hola"}]}, timeout=(2, 30))
print(r.json()["choices"][0]["message"]["content"])
```

Python (cliente oficial `openai`, apuntando al servidor local):
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8200/v1", api_key="local")
resp = client.chat.completions.create(model="qwen3-4b-int4-ov",
                                      messages=[{"role": "user", "content": "hola"}])
print(resp.choices[0].message.content)
```

El proyecto `otro proyecto local` ya lo consume via `src/nlp/llm_client.py`, que usa
la variable `INFERENCE_URL` (default `http://127.0.0.1:8200/v1`).

## Configuracion

Variables de entorno (opcionales):

- `INFERENCE_DEVICE` — `GPU` (default, iGPU Arc), `NPU` o `CPU`.
- `INFERENCE_PORT` — puerto (default `8200`).
- `INFERENCE_MODEL_DIR` — ruta a otra carpeta de modelo OV IR.

## Limites y evolucion

- Atiende bien a uno o pocos clientes secuenciales (un modelo, una iGPU). Para concurrencia
  real de muchos programas a la vez conviene migrar a **OpenVINO Model Server (OVMS)**, que
  trae *batching*; ese es tambien el camino para desplegarlo en un servidor **Xeon** (CPU con
  AMX) sin cambiar el contrato HTTP de los clientes.
- No metas este servicio en Docker en la notebook: el passthrough de la iGPU/NPU Intel a un
  contenedor en Windows es limitado y perderias la aceleracion. Docker es para el destino
  Xeon/Linux.
