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
      if (payload.refresh_board) {
        window.setTimeout(() => {
          window.location.reload();
        }, 500);
      }
    } catch (error) {
      appendMessage("assistant", `The assistant request failed: ${error}`);
    }
  });
}

let draggedTaskId = null;

document.querySelectorAll("[data-task-id]").forEach((card) => {
  card.addEventListener("dragstart", () => {
    draggedTaskId = card.dataset.taskId;
    card.classList.add("is-dragging");
  });
  card.addEventListener("dragend", () => {
    card.classList.remove("is-dragging");
    draggedTaskId = null;
  });
});

document.querySelectorAll(".task-detail-shell").forEach((detail) => {
  detail.addEventListener("toggle", () => {
    const card = detail.closest(".task-card");
    if (!card) {
      return;
    }
    card.classList.toggle("task-card-expanded", detail.open);
  });
});

document.querySelectorAll("[data-dropzone]").forEach((zone) => {
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("dropzone-active");
  });
  zone.addEventListener("dragleave", () => {
    zone.classList.remove("dropzone-active");
  });
  zone.addEventListener("drop", async (event) => {
    event.preventDefault();
    zone.classList.remove("dropzone-active");
    if (!draggedTaskId) {
      return;
    }
    const status = zone.dataset.dropzone;
    try {
      const response = await fetch(`/api/tasks/${draggedTaskId}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const payload = await response.json();
      if (!payload.ok) {
        throw new Error(payload.message || "Move failed.");
      }
      window.location.reload();
    } catch (error) {
      window.alert(`Task move failed: ${error}`);
    }
  });
});

const mermaidModalElement = document.getElementById("mermaidPreviewModal");
const mermaidModalTitle = document.getElementById("mermaidPreviewModalLabel");
const mermaidModalDiagram = document.getElementById("mermaidPreviewModalDiagram");

if (mermaidModalElement && mermaidModalTitle && mermaidModalDiagram && window.bootstrap) {
  const mermaidModal = new window.bootstrap.Modal(mermaidModalElement);
  let mermaidModalRenderIndex = 0;
  let pendingMermaidRenderNode = null;

  mermaidModalElement.addEventListener("shown.bs.modal", async () => {
    if (!pendingMermaidRenderNode || !window.puxaiMermaid) {
      return;
    }
    try {
      await window.puxaiMermaid.run({
        nodes: [pendingMermaidRenderNode],
      });
    } catch (error) {
      console.error("Mermaid modal render failed", error);
    } finally {
      pendingMermaidRenderNode = null;
    }
  });

  document.querySelectorAll("[data-mermaid-modal-body]").forEach((button) => {
    button.addEventListener("click", async () => {
      const title = button.dataset.mermaidModalTitle || "Mermaid preview";
      const body = button.dataset.mermaidModalBody || "";
      mermaidModalTitle.textContent = title;
      mermaidModalRenderIndex += 1;
      const renderId = `mermaid-modal-${mermaidModalRenderIndex}`;
      mermaidModalDiagram.innerHTML = "";
      const renderNode = document.createElement("div");
      renderNode.className = "mermaid";
      renderNode.id = renderId;
      renderNode.textContent = body;
      mermaidModalDiagram.appendChild(renderNode);
      pendingMermaidRenderNode = renderNode;
      mermaidModal.show();
    });
  });
}

const sideRailToggle = document.getElementById("sideRailToggle");
const layoutGrid = document.querySelector(".layout-grid");
const sideRail = document.getElementById("workspaceSideRail");
const sideRailStorageKey = "puxai-side-rail-collapsed";

function syncSideRailState(isCollapsed) {
  if (!layoutGrid || !sideRailToggle || !sideRail) {
    return;
  }
  layoutGrid.classList.toggle("side-rail-collapsed", isCollapsed);
  sideRail.hidden = isCollapsed;
  sideRailToggle.textContent = isCollapsed ? "Show AI side" : "Hide AI side";
  sideRailToggle.setAttribute("aria-expanded", String(!isCollapsed));
}

if (sideRailToggle && layoutGrid && sideRail) {
  const storedPreference = window.localStorage.getItem(sideRailStorageKey);
  syncSideRailState(storedPreference === "true");

  sideRailToggle.addEventListener("click", () => {
    const nextState = !layoutGrid.classList.contains("side-rail-collapsed");
    window.localStorage.setItem(sideRailStorageKey, String(nextState));
    syncSideRailState(nextState);
  });
}

const testAiConnectionButton = document.getElementById("testAiConnectionButton");
const settingsBackendName = document.getElementById("settingsBackendName");
const settingsBackendReachable = document.getElementById("settingsBackendReachable");
const settingsBackendUrl = document.getElementById("settingsBackendUrl");
const settingsDefaultModel = document.getElementById("settingsDefaultModel");
const settingsAgentModel = document.getElementById("settingsAgentModel");
const settingsAiModels = document.getElementById("settingsAiModels");

if (
  testAiConnectionButton &&
  settingsBackendName &&
  settingsBackendReachable &&
  settingsBackendUrl &&
  settingsDefaultModel &&
  settingsAgentModel &&
  settingsAiModels
) {
  testAiConnectionButton.addEventListener("click", async () => {
    testAiConnectionButton.disabled = true;
    testAiConnectionButton.textContent = "Testing...";
    try {
      const response = await fetch("/api/ai/status");
      const payload = await response.json();
      settingsBackendName.textContent = payload.backend || "unknown";
      settingsBackendReachable.textContent = payload.available ? "Online" : "Offline";
      settingsBackendReachable.className = payload.available ? "text-success" : "text-danger";
      settingsBackendUrl.textContent = payload.url || "n/a";
      settingsDefaultModel.textContent = payload.default_model || "n/a";
      settingsAgentModel.textContent = payload.agent_model || "n/a";
      settingsAiModels.innerHTML = "";
      if (payload.models && payload.models.length) {
        payload.models.forEach((model) => {
          const chip = document.createElement("span");
          chip.className = "tag-chip";
          chip.textContent = model;
          settingsAiModels.appendChild(chip);
        });
      } else {
        const emptyState = document.createElement("span");
        emptyState.className = "small text-muted";
        emptyState.textContent = "No models reported.";
        settingsAiModels.appendChild(emptyState);
      }
    } catch (error) {
      settingsBackendReachable.textContent = "Offline";
      settingsBackendReachable.className = "text-danger";
      settingsAiModels.innerHTML = "";
      const errorState = document.createElement("span");
      errorState.className = "small text-danger";
      errorState.textContent = `Connection test failed: ${error}`;
      settingsAiModels.appendChild(errorState);
    } finally {
      testAiConnectionButton.disabled = false;
      testAiConnectionButton.textContent = "Test Ollama connection";
    }
  });
}
