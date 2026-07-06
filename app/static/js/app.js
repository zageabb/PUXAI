const chatForm = document.getElementById("chat-form");
const chatHistory = document.getElementById("chat-history");
const chatMessage = document.getElementById("chat-message");

function appendMessage(role, content) {
  if (!chatHistory) {
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.className = `chat-message ${role}`;

  const roleNode = document.createElement("div");
  roleNode.className = "chat-role";
  roleNode.textContent = role;

  const body = document.createElement("div");
  body.className = "chat-message-body";
  body.textContent = content;

  wrapper.append(roleNode, body);
  chatHistory.appendChild(wrapper);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

if (chatForm && chatMessage) {
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = chatMessage.value.trim();
    if (!message) {
      return;
    }

    appendMessage("user", message);
    chatMessage.value = "";

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const payload = await response.json();
      appendMessage("assistant", payload.reply || "The assistant returned an empty response.");
    } catch (error) {
      appendMessage("assistant", `The assistant request failed: ${error}`);
    }
  });
}
