const fileInput = document.querySelector("#fileInput");
const uploadForm = document.querySelector("#uploadForm");
const dropZone = document.querySelector("#dropZone");
const fileName = document.querySelector("#fileName");
const uploadButton = document.querySelector("#uploadButton");
const processButton = document.querySelector("#processButton");
const serviceState = document.querySelector("#serviceState");
const jobIdNode = document.querySelector("#jobId");
const currentStatus = document.querySelector("#currentStatus");
const updatedAt = document.querySelector("#updatedAt");
const eventLog = document.querySelector("#eventLog");
const downloadLink = document.querySelector("#downloadLink");
const timelineItems = [...document.querySelectorAll("#timeline li")];
const detectionsList = document.querySelector("#detectionsList");
const detectionCount = document.querySelector("#detectionCount");
const emptyDetections = document.querySelector("#emptyDetections");
const planList = document.querySelector("#planList");
const planCount = document.querySelector("#planCount");
const emptyPlan = document.querySelector("#emptyPlan");
const sourceText = document.querySelector("#sourceText");
const sourceTextCount = document.querySelector("#sourceTextCount");
const emptySourceText = document.querySelector("#emptySourceText");
const redactedText = document.querySelector("#redactedText");
const redactedTextCount = document.querySelector("#redactedTextCount");
const emptyRedactedText = document.querySelector("#emptyRedactedText");

const terminalStatuses = new Set([
  "ready",
  "failed",
  "failed_verification",
  "cancelled",
]);
const timelineOrder = timelineItems.map((item) => item.dataset.status);

let currentJobId = null;
let pollTimer = null;

function logEvent(message) {
  const timestamp = new Date().toLocaleTimeString();
  eventLog.textContent = `[${timestamp}] ${message}\n${eventLog.textContent}`.trim();
}

function setBusy(isBusy) {
  uploadButton.disabled = isBusy;
  processButton.disabled = isBusy || !currentJobId;
}

function setDownloadReady(job) {
  const isReady = job.status === "ready";
  downloadLink.classList.toggle("is-disabled", !isReady);
  downloadLink.setAttribute("aria-disabled", String(!isReady));
  downloadLink.href = isReady ? `/api/jobs/${job.job_id}/download` : "#";
}

function renderJob(job) {
  currentJobId = job.job_id;
  jobIdNode.textContent = job.job_id;
  currentStatus.textContent = job.status;
  updatedAt.textContent = new Date(job.updated_at).toLocaleTimeString();
  processButton.disabled = job.status !== "uploaded";
  setDownloadReady(job);

  const currentIndex = timelineOrder.indexOf(job.status);
  const isFailed = job.status.includes("failed");

  timelineItems.forEach((item, index) => {
    item.classList.remove("is-complete", "is-active", "is-failed");
    if (isFailed) {
      item.classList.add("is-failed");
      return;
    }
    if (currentIndex === -1) {
      return;
    }
    if (index < currentIndex) {
      item.classList.add("is-complete");
    }
    if (index === currentIndex) {
      item.classList.add("is-active");
    }
  });
}

function clearDetections() {
  detectionCount.textContent = "0 candidates";
  emptyDetections.hidden = false;
  detectionsList.replaceChildren();
}

function clearRedactionPlan() {
  planCount.textContent = "0 decisions";
  emptyPlan.hidden = false;
  planList.replaceChildren();
}

function clearTextViews() {
  sourceTextCount.textContent = "0 characters";
  sourceText.textContent = "";
  sourceText.hidden = true;
  emptySourceText.hidden = false;

  redactedTextCount.textContent = "0 characters";
  redactedText.textContent = "";
  redactedText.hidden = true;
  emptyRedactedText.hidden = false;
}

function formatDocumentText(payload) {
  return (payload.pages || [])
    .map((page) => `Page ${page.page_number}\n${page.text.trim() || "(no extractable text)"}`)
    .join("\n\n");
}

function renderDetections(payload) {
  const candidates = payload.candidates || [];
  detectionCount.textContent = `${candidates.length} candidate${candidates.length === 1 ? "" : "s"}`;
  detectionsList.replaceChildren();
  emptyDetections.hidden = candidates.length > 0;

  for (const candidate of candidates) {
    const item = document.createElement("article");
    item.className = "detection-item";

    const heading = document.createElement("div");
    heading.className = "detection-heading";

    const label = document.createElement("strong");
    label.textContent = candidate.label;

    const confidence = document.createElement("span");
    confidence.textContent = `${Math.round(candidate.confidence * 100)}%`;

    heading.append(label, confidence);

    const text = document.createElement("p");
    text.textContent = candidate.text;

    const meta = document.createElement("div");
    meta.className = "detection-meta";
    meta.textContent = `Page ${candidate.page_number} / ${candidate.detector}${
      candidate.needs_llm_review ? " / needs LLM review" : ""
    }`;

    const reviewActions = document.createElement("div");
    reviewActions.className = "review-actions";

    const maskButton = document.createElement("button");
    maskButton.type = "button";
    maskButton.textContent = "Mask";
    maskButton.addEventListener("click", () => {
      reviewDetection(candidate.candidate_id, "mask").catch((error) => logEvent(error.message));
    });

    const skipButton = document.createElement("button");
    skipButton.type = "button";
    skipButton.textContent = "Skip";
    skipButton.addEventListener("click", () => {
      reviewDetection(candidate.candidate_id, "skip").catch((error) => logEvent(error.message));
    });

    reviewActions.append(maskButton, skipButton);
    item.append(heading, text, meta, reviewActions);
    detectionsList.append(item);
  }
}

function renderTextView(payload, target, emptyState, countNode) {
  const text = formatDocumentText(payload);
  countNode.textContent = `${payload.char_count} character${payload.char_count === 1 ? "" : "s"}`;
  target.textContent = text;
  target.hidden = text.length === 0;
  emptyState.hidden = text.length > 0;
}

function renderRedactionPlan(payload) {
  const decisions = payload.decisions || [];
  const regionCount = payload.region_count || 0;
  planCount.textContent = `${decisions.length} decision${decisions.length === 1 ? "" : "s"} / ${
    regionCount
  } box${regionCount === 1 ? "" : "es"}`;
  planList.replaceChildren();
  emptyPlan.hidden = decisions.length > 0;

  for (const decision of decisions) {
    const item = document.createElement("article");
    item.className = "plan-item";

    const heading = document.createElement("div");
    heading.className = "detection-heading";

    const label = document.createElement("strong");
    label.textContent = decision.label;

    const confidence = document.createElement("span");
    confidence.textContent = `${Math.round(decision.confidence * 100)}%`;

    heading.append(label, confidence);

    const text = document.createElement("p");
    text.textContent = decision.text;

    const meta = document.createElement("div");
    meta.className = "detection-meta";
    meta.textContent = `Page ${decision.page_number} / ${decision.detector_names.join(", ")}`;

    item.append(heading, text, meta);
    planList.append(item);
  }
}

async function loadDetections() {
  if (!currentJobId) {
    return;
  }

  const response = await fetch(`/api/jobs/${currentJobId}/detections`);
  if (response.status === 404) {
    return;
  }
  if (!response.ok) {
    throw new Error("Detection request failed");
  }

  const payload = await response.json();
  renderDetections(payload);
  logEvent(`Loaded ${payload.candidates.length} detection candidates`);
}

async function loadRedactionPlan() {
  if (!currentJobId) {
    return;
  }

  const response = await fetch(`/api/jobs/${currentJobId}/redaction-plan`);
  if (response.status === 404) {
    return;
  }
  if (!response.ok) {
    throw new Error("Redaction plan request failed");
  }

  const payload = await response.json();
  renderRedactionPlan(payload);
  logEvent(`Loaded ${payload.decision_count} redaction decisions`);
}

async function loadExtractedText() {
  if (!currentJobId) {
    return;
  }

  const response = await fetch(`/api/jobs/${currentJobId}/text/extracted`);
  if (response.status === 404) {
    return;
  }
  if (!response.ok) {
    throw new Error("Extracted text request failed");
  }

  const payload = await response.json();
  renderTextView(payload, sourceText, emptySourceText, sourceTextCount);
  logEvent(`Loaded extracted text from ${payload.page_count} page${payload.page_count === 1 ? "" : "s"}`);
}

async function loadRedactedText() {
  if (!currentJobId) {
    return;
  }

  const response = await fetch(`/api/jobs/${currentJobId}/text/redacted`);
  if (response.status === 404) {
    return;
  }
  if (!response.ok) {
    throw new Error("Redacted text request failed");
  }

  const payload = await response.json();
  renderTextView(payload, redactedText, emptyRedactedText, redactedTextCount);
  logEvent(`Loaded redacted text from ${payload.page_count} page${payload.page_count === 1 ? "" : "s"}`);
}

async function reviewDetection(candidateId, action) {
  if (!currentJobId) {
    return;
  }

  const response = await fetch(`/api/jobs/${currentJobId}/detections/${candidateId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, reason: "Reviewed in frontend" }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Review update failed");
  }
  logEvent(`Marked detection ${action}`);

  const rebuildResponse = await fetch(`/api/jobs/${currentJobId}/redaction-plan/rebuild`, {
    method: "POST",
  });
  if (!rebuildResponse.ok) {
    const error = await rebuildResponse.json();
    throw new Error(error.detail || "Redaction rebuild failed");
  }
  await loadRedactionPlan();
  await loadRedactedText();
  const jobResponse = await fetch(`/api/jobs/${currentJobId}`);
  if (jobResponse.ok) {
    renderJob(await jobResponse.json());
  }
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    serviceState.textContent = `${health.service} / ${health.environment}`;
  } catch {
    serviceState.textContent = "Service unavailable";
  }
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  setBusy(true);
  logEvent(`Uploading ${file.name}`);

  const response = await fetch("/api/documents", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Upload failed");
  }

  const job = await response.json();
  clearDetections();
  clearRedactionPlan();
  clearTextViews();
  setDownloadReady(job);
  renderJob(job);
  logEvent(`Uploaded ${job.filename}`);
  setBusy(false);
}

async function startProcessing() {
  if (!currentJobId) {
    return;
  }

  setBusy(true);
  logEvent(`Starting job ${currentJobId}`);

  const response = await fetch(`/api/jobs/${currentJobId}/process`, {
    method: "POST",
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to start processing");
  }

  const job = await response.json();
  renderJob(job);
  logEvent(`Queued task ${job.task_id}`);
  pollJob();
}

async function pollJob() {
  if (!currentJobId) {
    return;
  }

  clearTimeout(pollTimer);

  try {
    const response = await fetch(`/api/jobs/${currentJobId}`);
    if (!response.ok) {
      throw new Error("Status request failed");
    }

    const job = await response.json();
    renderJob(job);

    if (terminalStatuses.has(job.status)) {
      await loadDetections();
      await loadExtractedText();
      await loadRedactionPlan();
      await loadRedactedText();
      setBusy(false);
      logEvent(`Job status: ${job.status}`);
      return;
    }
  } catch (error) {
    logEvent(error.message);
    setBusy(false);
    return;
  }

  pollTimer = setTimeout(pollJob, 1200);
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  fileName.textContent = file ? file.name : "Drop file or choose one";
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("is-dragover");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragover");
  const file = event.dataTransfer.files?.[0];
  if (!file) {
    return;
  }
  fileInput.files = event.dataTransfer.files;
  fileName.textContent = file.name;
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files?.[0];
  if (!file) {
    logEvent("No file selected");
    return;
  }

  try {
    await uploadFile(file);
  } catch (error) {
    logEvent(error.message);
    setBusy(false);
  }
});

processButton.addEventListener("click", async () => {
  try {
    await startProcessing();
  } catch (error) {
    logEvent(error.message);
    setBusy(false);
  }
});

checkHealth();
clearDetections();
clearRedactionPlan();
clearTextViews();
