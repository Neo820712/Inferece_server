"""Motor de transcripcion Whisper sobre OpenVINO GenAI.

Import perezoso de openvino_genai (dentro de __init__) para poder importar el modulo
sin OpenVINO en el entorno de pruebas. Intenta NPU; si el pipeline NPU falla al
inicializar (el decoder autoregresivo es el punto flojo del soporte NPU), cae a CPU.
"""


class WhisperEngine:
    def __init__(self, model_dir: str, device: str = "NPU", fallback: str = "CPU"):
        import openvino_genai as ov_genai
        self._ov_genai = ov_genai
        self.active_device = device
        try:
            self.pipe = ov_genai.WhisperPipeline(model_dir, device)
        except Exception as exc:
            print(f"[whisper] {device} no disponible ({str(exc)[:120]}); "
                  f"cayendo a {fallback}")
            self.active_device = fallback
            self.pipe = ov_genai.WhisperPipeline(model_dir, fallback)

    def transcribe(self, samples, language: str = "es") -> str:
        cfg = self.pipe.get_generation_config()
        cfg.language = f"<|{language}|>"
        cfg.task = "transcribe"
        cfg.return_timestamps = False
        result = self.pipe.generate(samples, cfg)
        return str(result).strip()
