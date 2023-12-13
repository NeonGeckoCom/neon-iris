import json
from os import makedirs
from os.path import isdir, join
from threading import Event
from typing import Dict, List
from uuid import uuid4

import numpy as np
import resampy
from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from openwakeword import Model
from ovos_config import Configuration
from ovos_utils import LOG
from ovos_utils.xdg_utils import xdg_data_home

from neon_iris.client import NeonAIClient


class CustomNeonClient(NeonAIClient):
    def __init__(self, lang: str = None):
        config = Configuration()
        self.config = config.get("iris") or dict()
        # NeonAIClient.__init__(self, config.get("MQ"))  # TODO: Handle connection error
        self._await_response = Event()
        self._response = None
        self._transcribed = None
        self._current_tts = dict()
        self._profiles: Dict[str, dict] = dict()
        self._audio_path = join(xdg_data_home(), "iris", "stt")
        if not isdir(self._audio_path):
            makedirs(self._audio_path)
        self.default_lang = lang or self.config.get("default_lang")
        LOG.name = "iris"
        LOG.init(self.config.get("logs"))

    def get_lang(self, session_id: str):
        if session_id and session_id in self._profiles:
            return self._profiles[session_id]["speech"]["stt_language"]
        return self.user_config["speech"]["stt_language"] or self.default_lang

    @property
    def supported_languages(self) -> List[str]:
        """
        Get a list of supported languages from configuration
        @returns: list of BCP-47 language codes
        """
        return self.config.get("languages") or [self.default_lang]

    def _start_session(self):
        sid = uuid4().hex
        self._current_tts[sid] = None
        self._profiles[sid] = self.user_config
        self._profiles[sid]["user"]["username"] = sid
        return sid


app = FastAPI()
owwModel = Model(inference_framework="tflite")
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="neon_iris/static/templates")
neon_client = CustomNeonClient()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Send loaded models
    await websocket.send_text(
        json.dumps({"loaded_models": list(owwModel.models.keys())})
    )

    while True:
        message = await websocket.receive()

        if message["type"] == "websocket.disconnect":
            break

        if message["type"] == "websocket.receive":
            if "text" in message:
                # Process text message
                sample_rate = int(message["text"])
            elif "bytes" in message:
                # Process bytes message
                audio_bytes = message["bytes"]

                # Add extra bytes of silence if needed
                if len(audio_bytes) % 2 == 1:
                    audio_bytes += b"\x00"

                # Convert audio to correct format and sample rate
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                if sample_rate != 16000:
                    audio_data = resampy.resample(audio_data, sample_rate, 16000)

                # Get openWakeWord predictions and send to browser client
                predictions = owwModel.predict(audio_data)

                activations = [
                    key for key, value in predictions.items() if value >= 0.5
                ]

                if activations:
                    await websocket.send_text(json.dumps({"activations": activations}))


# Serve static files
app.mount(
    "/static",
    StaticFiles(directory="neon_iris/static"),
    name="Neon Web Voice Satellite",
)


@app.get("/")
async def read_root(request: Request):
    """Render the Neon AI Web UI and Voice Satellite."""
    context = {
        "request": request,
        "title": neon_client.config.get("webui_title", "Neon AI"),
        "description": neon_client.config.get("webui_description", "Chat With Neon"),
        # TODO: Add other configurations
    }
    return templates.TemplateResponse("index.html", context)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
