"""Runs a web server that serves the Neon AI Web UI and Voice Satellite."""
import json
from os import makedirs
from os.path import isdir, join
from threading import Event
from typing import Dict, List
from uuid import uuid4

import numpy as np
import resampy
from fastapi import APIRouter, FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openwakeword import Model
from ovos_config import Configuration
from ovos_utils import LOG
from ovos_utils.xdg_utils import xdg_data_home

from neon_iris.client import NeonAIClient


class WebSatNeonClient(NeonAIClient):
    """Neon AI Web UI and Voice Satellite client."""

    def __init__(self, lang: str = None):
        config = Configuration()
        self.config = config.get("iris") or dict()
        self.mq_config = config.get("MQ")
        if not self.mq_config:
            raise ValueError(
                "Missing MQ configuration, please set it in ~/.config/neon/neon.yaml"
            )
        NeonAIClient.__init__(self, self.mq_config)
        self.router = APIRouter()
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
        # OpenWW
        self.oww_model = Model(inference_framework="tflite")
        # FastAPI
        self.templates = Jinja2Templates(directory="neon_iris/static/templates")
        self.router.add_api_websocket_route("/ws", self.websocket_endpoint)
        self.router.add_route("/", self.read_root, methods=["GET"])

    def get_lang(self, session_id: str):
        """Get the language for a session."""
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

    async def websocket_endpoint(self, websocket: WebSocket):
        """Handles websocket connections to OpenWakeWord, which runs as part of this service."""
        await websocket.accept()
        # Send loaded models
        await websocket.send_text(
            json.dumps({"loaded_models": list(self.oww_model.models.keys())})
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
                    predictions = self.oww_model.predict(audio_data)

                    activations = [
                        key for key, value in predictions.items() if value >= 0.5
                    ]

                    if activations:
                        await websocket.send_text(
                            json.dumps({"activations": activations})
                        )

    async def read_root(self, request: Request):
        """Render the Neon AI Web UI and Voice Satellite."""
        description = self.config.get("webui_description", "Chat With Neon")
        title = self.config.get("webui_title", "Neon AI")
        chatbot_label = self.config.get("webui_chatbot_label") or description
        text_label = self.config.get("webui_text_label") or description
        placeholder = self.config.get("webui_input_placeholder", "Ask me something")

        context = {
            "request": request,
            "title": title,
            "description": description,
            "chatbot_label": chatbot_label,
            "text_label": text_label,
            "placeholder": placeholder,
        }
        return self.templates.TemplateResponse("index.html", context)


app = FastAPI()
neon_client = WebSatNeonClient()
app.mount(
    "/static",
    StaticFiles(directory="neon_iris/static"),
    name="Neon Web Voice Satellite",
)
app.include_router(neon_client.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
