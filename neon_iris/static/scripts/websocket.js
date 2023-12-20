function float32ArrayToWavBlob(float32Array, sampleRate = 16000) {
  const buffer = new ArrayBuffer(44 + float32Array.length * 2);
  const view = new DataView(buffer);

  // Write WAV header to the buffer
  // RIFF chunk descriptor
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + float32Array.length * 2, true);
  writeString(view, 8, "WAVE");
  // FMT sub-chunk
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true); // AudioFormat (PCM = 1)
  view.setUint16(22, 1, true); // NumChannels (Mono = 1, Stereo = 2)
  view.setUint32(24, sampleRate, true); // SampleRate
  view.setUint32(28, sampleRate * 2, true); // ByteRate (SampleRate * NumChannels * BitsPerSample/8)
  view.setUint16(32, 2, true); // BlockAlign (NumChannels * BitsPerSample/8)
  view.setUint16(34, 16, true); // BitsPerSample
  // Data sub-chunk
  writeString(view, 36, "data");
  view.setUint32(40, float32Array.length * 2, true);

  // Write the audio data
  float32To16BitPCM(view, 44, float32Array);

  return new Blob([view], { type: "audio/wav" });
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

function float32To16BitPCM(output, offset, input) {
  for (let i = 0; i < input.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
}

function wavBlobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(blob);
    reader.onloadend = () => {
      const base64data = reader.result;
      // Extract the base64 part
      const base64String = base64data.split(",")[1];
      resolve(base64String);
    };
    reader.onerror = (error) => {
      reject(error);
    };
  });
}

let shouldListen = false; // Global state flag for controlling VAD listening state
let myVad; // VAD instance
let isVadRunning = false;

async function initializeVad() {
  myVad = await vad.MicVAD.new({
    onSpeechEnd: handleSpeechEnd,
  });
  if (shouldListen && !isVadRunning) {
    myVad.start();
    isVadRunning = true;
  }
}

async function handleSpeechEnd(audio) {
  const wavBlob = float32ArrayToWavBlob(audio);
  const audioUrl = URL.createObjectURL(wavBlob);
  const audioOutput = await wavBlobToBase64(wavBlob);

  // Save the spoken audio as a downloadable file
  const downloadArea = document.getElementById("download-area");
  if (downloadArea) {
    downloadArea.innerHTML = "";
    const downloadLink = document.createElement("a");
    downloadLink.href = audioUrl;
    downloadLink.download = "recorded_audio.wav";
    downloadLink.textContent = "Download Recorded Audio";
    downloadArea.appendChild(downloadLink);
  } else {
    console.error("Download area not found");
  }
  if (myVad && isVadRunning) {
    myVad.pause();
    isVadRunning = false;
    shouldListen = false;
  }

  // Send audio to STT
  getAIResponse("", audioOutput);
}

function toggleListeningState() {
  shouldListen = !shouldListen;
  if (shouldListen && !isVadRunning) {
    startVad();
    isVadRunning = true;
  } else {
    stopVad();
    isVadRunning = false;
  }
}

// Handles WebSocket connection and message events
const WebSocketHandler = (() => {
  let lastActivationTime = 0;
  const activationCooldown = 3000; // 3 seconds cooldown
  const ws = new WebSocket(WS_URL);
  const audio = new Audio("/static/wake.mp3"); // Wakeword acknowledgment sound

  ws.onopen = () => {
    console.info("WebSocket connection is open");
  };

  ws.onmessage = async (event) => {
    console.log(event.data);
    const model_payload = JSON.parse(event.data);
    const currentTime = Date.now();
    if ("activations" in model_payload) {
      if (
        model_payload.activations.includes("hey_neon_high") &&
        currentTime - lastActivationTime > activationCooldown
      ) {
        shouldListen = true;
        audio.onended = () => {
          console.log("Activation sound is done playing");
          if (myVad && !isVadRunning) {
            myVad.start();
            isVadRunning = true;
          } else if (!shouldListen && isVadRunning) {
            myVad.pause();
            isVadRunning = false;
          }
        };
        audio.play();
        lastActivationTime = currentTime;
      }
    }
  };

  return {
    send: (data) => ws.send(data),
    setSampleRate: (rate) => ws.send(rate),
  };
})();

// Initialize VAD when the page is ready
window.addEventListener("DOMContentLoaded", (event) => {
  initializeVad();
});
WebSocketHandler;
