import json

import numpy as np
import resampy
from fastapi import FastAPI, WebSocket
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from openwakeword import Model

from neon_iris.client import NeonAIClient


class CustomNeonClient(NeonAIClient):
    # Extend this class with your custom methods
    pass


app = FastAPI()
owwModel = Model(inference_framework="tflite")


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
    "/voicesat",
    StaticFiles(directory="neon_iris/static"),
    name="Neon Web Voice Satellite",
)


@app.get("/")
async def read_root() -> RedirectResponse:
    """Redirect to /voicesat/index.html when accessing the root URL."""
    return RedirectResponse(url="/voicesat/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
