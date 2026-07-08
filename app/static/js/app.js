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
const mermaidSourceEditor = document.getElementById("mermaidSourceEditor");
const mermaidSaveForm = document.getElementById("mermaidSaveForm");
const mermaidSaveInput = document.getElementById("mermaidSaveInput");
const mermaidCopyButton = document.getElementById("mermaidCopyButton");
const mermaidDownloadMmdButton = document.getElementById("mermaidDownloadMmdButton");
const mermaidDownloadMdButton = document.getElementById("mermaidDownloadMdButton");
const mermaidPreviewRefreshButton = document.getElementById("mermaidPreviewRefreshButton");
const mermaidValidationMessage = document.getElementById("mermaidValidationMessage");
const mermaidRenderErrorShell = document.getElementById("mermaidRenderErrorShell");
const mermaidFixAiButton = document.getElementById("mermaidFixAiButton");

function validateMermaidText(text) {
  const trimmed = (text || "").trim();
  const warnings = [];
  if (!trimmed) {
    warnings.push("Mermaid text is empty.");
    return { ok: false, warnings, diagramType: "", firstLine: "" };
  }

  const lines = trimmed.split("\n").map((line) => line.trim()).filter(Boolean);
  const firstLine = lines[0] || "";
  const validPrefixes = new Set([
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "journey",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
    "gitGraph",
    "kanban",
    "quadrantChart",
    "requirementDiagram",
    "sankey-beta",
    "xychart-beta",
    "block-beta",
    "packet-beta",
    "architecture-beta",
  ]);
  const firstToken = firstLine.split(/\s+/)[0] || "";
  if (!validPrefixes.has(firstToken)) {
    warnings.push("The first Mermaid line should start with a diagram type like `flowchart TD`, `kanban`, or `sequenceDiagram`.");
  }
  return { ok: warnings.length === 0, warnings, diagramType: firstToken, firstLine };
}

function syncMermaidValidation(messageNode, text, renderError = "") {
  if (!messageNode) {
    return validateMermaidText(text);
  }
  const validation = validateMermaidText(text);
  messageNode.className = "mermaid-validation";
  if (validation.ok && !renderError) {
    messageNode.textContent = `Detected ${validation.diagramType || "Mermaid"} diagram.`;
  } else {
    const parts = [...validation.warnings];
    if (renderError) {
      parts.push(`Render issue: ${renderError}`);
    }
    messageNode.textContent = parts.join(" ");
    messageNode.classList.add("is-warning");
  }
  return validation;
}

if (
  mermaidModalElement &&
  mermaidModalTitle &&
  mermaidModalDiagram &&
  mermaidSourceEditor &&
  mermaidCopyButton &&
  mermaidDownloadMmdButton &&
  mermaidDownloadMdButton &&
  mermaidPreviewRefreshButton &&
  window.bootstrap
) {
  const mermaidModal = new window.bootstrap.Modal(mermaidModalElement);
  let mermaidModalRenderIndex = 0;
  let currentMermaidConfig = {
    mode: "board",
    saveUrl: "",
    aiFixUrl: "",
    artifactName: "",
  };
  let lastRenderError = "";

  async function renderMermaidPreview() {
    if (!window.puxaiMermaid) {
      return;
    }
    const body = mermaidSourceEditor.value || "";
    const validation = syncMermaidValidation(mermaidValidationMessage, body);
    mermaidModalRenderIndex += 1;
    const renderId = `mermaid-modal-${mermaidModalRenderIndex}`;
    mermaidModalDiagram.innerHTML = "";
    const renderNode = document.createElement("div");
    renderNode.className = "mermaid";
    renderNode.id = renderId;
    renderNode.textContent = body;
    mermaidModalDiagram.appendChild(renderNode);
    lastRenderError = "";
    if (mermaidRenderErrorShell) {
      mermaidRenderErrorShell.classList.add("d-none");
      mermaidRenderErrorShell.textContent = "";
    }
    try {
      await window.puxaiMermaid.run({ nodes: [renderNode] });
      syncMermaidValidation(mermaidValidationMessage, body);
    } catch (error) {
      lastRenderError = String(error);
      syncMermaidValidation(mermaidValidationMessage, body, lastRenderError);
      if (mermaidRenderErrorShell) {
        mermaidRenderErrorShell.textContent = lastRenderError;
        mermaidRenderErrorShell.classList.remove("d-none");
      }
    }
    return validation;
  }

  function syncMermaidModalMode() {
    const isTaskMode = currentMermaidConfig.mode === "task";
    if (mermaidSaveForm) {
      mermaidSaveForm.hidden = !isTaskMode;
      mermaidSaveForm.action = currentMermaidConfig.saveUrl || "";
    }
    if (mermaidSourceEditor) {
      mermaidSourceEditor.readOnly = !isTaskMode;
    }
    if (mermaidFixAiButton) {
      mermaidFixAiButton.hidden = !isTaskMode || !currentMermaidConfig.aiFixUrl;
      mermaidFixAiButton.disabled = !currentMermaidConfig.aiFixUrl;
    }
  }

  document.querySelectorAll("[data-mermaid-modal-body]").forEach((button) => {
    button.addEventListener("click", async () => {
      currentMermaidConfig = {
        mode: button.dataset.mermaidModalMode || "board",
        saveUrl: button.dataset.mermaidSaveUrl || "",
        aiFixUrl: button.dataset.mermaidAiFixUrl || "",
        artifactName: button.dataset.mermaidArtifactName || "",
      };
      mermaidModalTitle.textContent = button.dataset.mermaidModalTitle || "Mermaid preview";
      mermaidSourceEditor.value = button.dataset.mermaidModalBody || "";
      mermaidDownloadMmdButton.href = button.dataset.mermaidDownloadMmdUrl || "#";
      mermaidDownloadMdButton.href = button.dataset.mermaidDownloadMdUrl || "#";
      syncMermaidModalMode();
      mermaidModal.show();
      await renderMermaidPreview();
    });
  });

  mermaidPreviewRefreshButton.addEventListener("click", async () => {
    await renderMermaidPreview();
  });

  mermaidSourceEditor.addEventListener("input", () => {
    syncMermaidValidation(mermaidValidationMessage, mermaidSourceEditor.value);
  });

  mermaidCopyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(mermaidSourceEditor.value || "");
      mermaidCopyButton.textContent = "Copied";
      window.setTimeout(() => {
        mermaidCopyButton.textContent = "Copy Mermaid";
      }, 1200);
    } catch (error) {
      window.alert(`Copy failed: ${error}`);
    }
  });

  if (mermaidSaveForm && mermaidSaveInput) {
    mermaidSaveForm.addEventListener("submit", (event) => {
      const validation = validateMermaidText(mermaidSourceEditor.value);
      if (!validation.ok) {
        event.preventDefault();
        syncMermaidValidation(mermaidValidationMessage, mermaidSourceEditor.value, lastRenderError);
        window.alert(validation.warnings.join(" "));
        return;
      }
      mermaidSaveInput.value = mermaidSourceEditor.value;
    });
  }

  if (mermaidFixAiButton) {
    mermaidFixAiButton.addEventListener("click", async () => {
      if (!currentMermaidConfig.aiFixUrl) {
        return;
      }
      mermaidFixAiButton.disabled = true;
      mermaidFixAiButton.textContent = "Fixing...";
      try {
        const response = await fetch(currentMermaidConfig.aiFixUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            artifact_name: currentMermaidConfig.artifactName,
            mermaid_code: mermaidSourceEditor.value,
            render_error: lastRenderError,
          }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.message || "AI Mermaid fix failed.");
        }
        mermaidSourceEditor.value = payload.mermaid_code || mermaidSourceEditor.value;
        await renderMermaidPreview();
      } catch (error) {
        window.alert(`AI Mermaid fix failed: ${error}`);
      } finally {
        mermaidFixAiButton.disabled = false;
        mermaidFixAiButton.textContent = "Fix Mermaid with AI";
      }
    });
  }
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
