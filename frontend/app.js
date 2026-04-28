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
const timelineItems = [...document.querySelectorAll("#timeline li")];

const terminalStatuses = new Set(["detecting", "ready", "failed", "failed_verification", "cancelled"]);
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

function renderJob(job) {
  currentJobId = job.job_id;
  jobIdNode.textContent = job.job_id;
  currentStatus.textContent = job.status;
  updatedAt.textContent = new Date(job.updated_at).toLocaleTimeString();
  processButton.disabled = job.status !== "uploaded";

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
