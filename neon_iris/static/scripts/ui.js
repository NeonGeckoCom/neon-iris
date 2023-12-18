function submitMessage() {
  const inputElement = document.getElementById("chatInput");
  const userMessage = inputElement.value.trim();

  if (userMessage !== "") {
    const userMessageDiv = createMessageDiv("user", userMessage);
    appendMessageToHistory(userMessageDiv);

    // Save the message to localStorage
    saveMessageToLocalStorage("user", userMessage);

    inputElement.value = "";

    // Get AI response and update the chat history
    getAIResponse(userMessage); // Pass the user message to the function
  }
}

async function getAIResponse(text = "", recording = "") {
  try {
    const payload =
      text !== "" && recording === ""
        ? { utterance: text }
        : { audio_input: recording };
    // Make the POST request to the server
    const response = await fetch("/user_input", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload), // Send the user message in the body
    });

    // Check if the response is okay
    if (!response.ok) {
      throw new Error("Network response was not ok: " + response.statusText);
    }

    // Convert the response payload into JSON
    const data = await response.json();
    console.debug(data, null, 4);

    // Assuming 'data' contains the AI response in a property named 'reply'
    const aiMessage = data.transcription;

    // Add in the user's transcription if STT
    if (text === "" && recording !== "") {
      const userMessage = createMessageDiv("user", data.utterance);
      appendMessageToHistory(userMessage);
      saveMessageToLocalStorage("user", data.utterance);
    }

    // Create the AI message div and append it to the history
    const aiMessageDiv = createMessageDiv("ai", aiMessage);
    appendMessageToHistory(aiMessageDiv);

    // Save the AI message to localStorage
    saveMessageToLocalStorage("ai", aiMessage);

    // Play the TTS audio
    const audioBlob = base64ToBlob(data.audio_output, "audio/wav");
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.type = "audio/wav";
    await audio.play();
    audio.onended = () => {
      if (shouldListen && myVad) {
        myVad.start();
      } else {
        myVad.pause();
      }
    };
  } catch (error) {
    console.error("Error fetching AI response:", error);
    // Handle the error, such as showing a message to the user
  }
}

function simulateAIResponse() {
  setTimeout(() => {
    const aiMessage = "This is a sample AI response.";
    const aiMessageDiv = createMessageDiv("ai", aiMessage);
    appendMessageToHistory(aiMessageDiv);

    // Save the AI response to localStorage
    saveMessageToLocalStorage("ai", aiMessage);
  }, 1000); // Simulated delay of 1 second
}

function createMessageDiv(sender, message) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `${sender}-message`;
  messageDiv.textContent = message;
  return messageDiv;
}

function appendMessageToHistory(messageDiv) {
  const messageContainer = document.getElementById("chatHistory");
  messageContainer.appendChild(messageDiv);
  setTimeout(() => {
    messageContainer.scrollTop = messageContainer.scrollHeight;
  }, 0);
}

function saveMessageToLocalStorage(sender, message) {
  // Retrieve existing chat history from localStorage
  const chatHistory = JSON.parse(localStorage.getItem("chatHistory")) || [];

  // Add the new message to the chat history
  chatHistory.push({ sender, message });

  // Store the updated chat history back in localStorage
  localStorage.setItem("chatHistory", JSON.stringify(chatHistory));
}

function base64ToBlob(base64, mimeType) {
  const byteCharacters = atob(base64.replace(/^data:audio\/wav;base64,/, ""));
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: mimeType });
}

// Load chat history from localStorage when the page loads
window.addEventListener("load", () => {
  const chatHistory = JSON.parse(localStorage.getItem("chatHistory")) || [];

  for (const { sender, message } of chatHistory) {
    const messageDiv = createMessageDiv(sender, message);
    appendMessageToHistory(messageDiv);
  }
});

document.addEventListener("DOMContentLoaded", function () {
  // Get the input element
  const inputElement = document.getElementById("chatInput");

  // Add the keydown event listener to the input element
  inputElement.addEventListener("keydown", function (event) {
    // Check if Enter was pressed, or Ctrl+Enter
    if (event.key === "Enter" && (event.ctrlKey || !event.shiftKey)) {
      event.preventDefault();
      submitMessage();
    }
  });
});
