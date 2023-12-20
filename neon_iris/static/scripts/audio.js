// Manages audio capture and processing
const AudioHandler = (() => {
  let audioStream;
  let audioContext;
  let recorder;
  let volume;
  let sampleRate;
  let isRecording = false;

  // Ensure the getUserMedia is correctly referenced
  const getUserMedia =
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia;

  const startAudio = () => {
    if (getUserMedia) {
      getUserMedia.call(
        navigator,
        { audio: true },
        (stream) => {
          audioStream = stream;
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          audioContext = new AudioContext();
          sampleRate = audioContext.sampleRate;
          volume = audioContext.createGain();
          const audioInput = audioContext.createMediaStreamSource(audioStream);
          audioInput.connect(volume);

          const bufferSize = 4096;
          // Use the audio context to create the script processor
          recorder = audioContext.createScriptProcessor(bufferSize, 1, 1);

          recorder.onaudioprocess = (event) => {
            const samples = event.inputBuffer.getChannelData(0);
            const PCM16iSamples = convertFloat32ToInt16(samples);
            WebSocketHandler.send(
              new Blob([PCM16iSamples], { type: "application/octet-stream" })
            );
          };

          volume.connect(recorder);
          recorder.connect(audioContext.destination);
          WebSocketHandler.setSampleRate(sampleRate);
          isRecording = true;
        },
        (error) => {
          console.error("Error capturing audio.", error);
        }
      );
    } else {
      console.error("getUserMedia not supported in this browser.");
    }
  };

  const stopAudio = () => {
    if (isRecording) {
      if (recorder) {
        recorder.disconnect();
        volume.disconnect();
        // Disconnecting the audio context might not be necessary
        // audioContext.close();
      }
      if (audioStream) {
        const tracks = audioStream.getTracks();
        tracks.forEach((track) => track.stop());
      }
    }
  };

  const toggle = () => {
    if (!isRecording) {
      startAudio();
    } else {
      stopAudio();
    }
    isRecording = !isRecording; // Toggle the recording state
  };

  const isCurrentlyRecording = () => isRecording;

  const convertFloat32ToInt16 = (buffer) => {
    let l = buffer.length;
    let buf = new Int16Array(l);
    while (l--) {
      buf[l] = Math.min(1, buffer[l]) * 0x7fff;
    }
    return buf.buffer;
  };

  return {
    toggle,
    isRecording: isCurrentlyRecording,
  };
})();

const startButton = document.getElementById("startButton");
startButton.addEventListener("click", function () {
  AudioHandler.toggle();

  // Update the button's text and class based on the recording state
  if (AudioHandler.isRecording()) {
    startButton.classList.add("listening");
    startButton.textContent = "Listening...";
  } else {
    startButton.classList.remove("listening");
    startButton.textContent = "Start Listening";
  }
});
