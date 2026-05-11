const state = {
  selectedOptionId: "",
  options: [],
};

const $ = (id) => document.getElementById(id);

function log(line) {
  const node = $("log");
  const time = new Date().toLocaleTimeString();
  node.textContent += `[${time}] ${line}\n`;
  node.scrollTop = node.scrollHeight;
}

async function post(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function truncate(text, limit) {
  if (!text || text.length <= limit) return text || "";
  return `${text.slice(0, limit - 1)}...`;
}

function renderOptions(options) {
  state.options = options || [];
  const box = $("options");
  box.innerHTML = "";
  if (!state.options.length) {
    box.className = "options empty";
    box.textContent = "No replacement options yet.";
    state.selectedOptionId = "";
    return;
  }
  box.className = "options";
  if (!state.selectedOptionId) {
    state.selectedOptionId = state.options[0].option_id;
  }
  for (const option of state.options) {
    const item = document.createElement("div");
    item.className = `option ${option.option_id === state.selectedOptionId ? "selected" : ""}`;
    item.tabIndex = 0;
    item.innerHTML = `
      <strong>${option.reason_id} · ${truncate(option.reason, 92)}</strong>
      <p>${truncate(option.explanation, 160)}</p>
      ${option.replacement_text ? `<p class="replacement">${truncate(option.replacement_text, 220)}</p>` : ""}
    `;
    item.addEventListener("click", () => {
      state.selectedOptionId = option.option_id;
      renderOptions(state.options);
    });
    box.appendChild(item);
  }
}

function renderProfile(payload) {
  if (!payload || typeof payload !== "object") {
    $("profile").textContent = "No profile loaded.";
    return;
  }
  const global = payload.global_profile || [];
  const local = payload.local_profile || [];
  const observations = payload.observations || [];
  const lines = [
    "Global profile:",
    ...(global.length ? global.map((item) => `- ${item}`) : ["- None yet."]),
    "",
    "Local memory:",
    ...(local.length ? local.map((item) => `- ${item}`) : ["- None yet."]),
    "",
    "Counts:",
    ...(observations.length ? observations.map((item) => `- ${item.summary} (${item.count}x)`) : ["- None yet."]),
  ];
  $("profile").textContent = lines.join("\n");
}

function formatInterpreter(payload) {
  if (!payload || typeof payload !== "object") return "";
  const stop = payload.stop_point || {};
  const reasons = payload.reason_candidates || [];
  const lines = [];
  if (payload.likely_user_intent) lines.push(`Likely intent: ${payload.likely_user_intent}`);
  if (stop.current_sentence) lines.push(`Interrupted sentence: ${stop.current_sentence}`);
  if (stop.last_sentence) lines.push(`Previous sentence: ${stop.last_sentence}`);
  if (reasons.length) {
    lines.push("", "Reasons:");
    for (const reason of reasons) {
      lines.push(`${reason.id}: ${reason.reason}`);
    }
  }
  return lines.join("\n");
}

function connectEvents() {
  const events = new EventSource("/events");
  events.addEventListener("ready", () => log("Connected to local web UI."));
  events.addEventListener("guidance", (event) => log(JSON.parse(event.data)));
  events.addEventListener("credential_status", (event) => {
    $("credential").textContent = JSON.parse(event.data);
    log($("credential").textContent);
  });
  events.addEventListener("status", (event) => {
    $("status").textContent = JSON.parse(event.data);
    log($("status").textContent);
  });
  events.addEventListener("append_text", (event) => {
    $("document").value += JSON.parse(event.data);
    $("document").scrollTop = $("document").scrollHeight;
  });
  events.addEventListener("set_text", (event) => {
    $("document").value = JSON.parse(event.data);
  });
  events.addEventListener("interpreter_result", (event) => {
    $("interpreter").textContent = formatInterpreter(JSON.parse(event.data));
  });
  events.addEventListener("replacement_options", (event) => {
    state.selectedOptionId = "";
    renderOptions(JSON.parse(event.data));
  });
  events.addEventListener("profile_update", (event) => renderProfile(JSON.parse(event.data)));
  events.addEventListener("busy", (event) => {
    $("busy").textContent = JSON.parse(event.data) ? "Busy" : "Idle";
  });
  events.addEventListener("stream_mode", (event) => {
    $("mode").textContent = `Mode: ${JSON.parse(event.data)}`;
  });
  events.addEventListener("timing", (event) => {
    const payload = JSON.parse(event.data);
    $("latency").textContent = `${payload.label}: ${payload.elapsed_seconds}s`;
    log(`${payload.label} took ${payload.elapsed_seconds}s`);
  });
  events.addEventListener("revision_applied", (event) => {
    log(`Revision applied: ${JSON.stringify(JSON.parse(event.data))}`);
  });
  events.addEventListener("error", (event) => log(`Error: ${JSON.parse(event.data)}`));
}

function bindActions() {
  $("start").addEventListener("click", async () => {
    $("document").value = "";
    $("interpreter").textContent = "";
    renderOptions([]);
    await post("/api/start", { username: $("username").value, task: $("task").value });
  });
  $("stop").addEventListener("click", () => post("/api/stop").catch((error) => log(error.message)));
  $("accept").addEventListener("click", () => post("/api/accept").catch((error) => log(error.message)));
  $("continue").addEventListener("click", () => post("/api/continue").catch((error) => log(error.message)));
  $("apply").addEventListener("click", () => {
    const selectedMode = document.querySelector("input[name='otherMode']:checked").value;
    post("/api/apply", {
      option_id: state.selectedOptionId,
      other_mode: selectedMode,
      other_text: $("otherText").value,
    }).catch((error) => log(error.message));
  });
  $("export").addEventListener("click", async () => {
    try {
      const data = await post("/api/export");
      $("exportText").value = data.session;
      $("exportDialog").showModal();
    } catch (error) {
      log(error.message);
    }
  });
}

connectEvents();
bindActions();
