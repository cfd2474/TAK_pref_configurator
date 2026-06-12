const state = {
  schema: null,
  activePanel: "connections",
  preferences: {},
  connections: {
    cot_inputs: [],
    cot_outputs: [],
    cot_streams: [],
  },
};

const els = {
  nav: document.getElementById("category-nav"),
  form: document.getElementById("settings-form"),
  panelTitle: document.getElementById("panel-title"),
  panelDescription: document.getElementById("panel-description"),
  search: document.getElementById("category-search"),
  filename: document.getElementById("filename"),
  preferenceName: document.getElementById("preference-name"),
  downloadBtn: document.getElementById("download-btn"),
  previewBtn: document.getElementById("preview-btn"),
  importFile: document.getElementById("import-file"),
  previewDialog: document.getElementById("preview-dialog"),
  previewContent: document.getElementById("preview-content"),
  closePreview: document.getElementById("close-preview"),
  toast: document.getElementById("toast"),
};

async function init() {
  try {
    const response = await fetch("/api/schema");
    if (!response.ok) throw new Error("Failed to load schema");
    state.schema = await response.json();
    buildNavigation();
    renderPanel();
    bindEvents();
  } catch (error) {
    showToast(error.message, true);
  }
}

function bindEvents() {
  els.search.addEventListener("input", () => buildNavigation(els.search.value.trim()));
  els.downloadBtn.addEventListener("click", downloadPref);
  els.previewBtn.addEventListener("click", previewPref);
  els.importFile.addEventListener("change", importPref);
  els.closePreview.addEventListener("click", () => els.previewDialog.close());
  els.filename.addEventListener("change", () => normalizeFilename());
}

function normalizeFilename() {
  let value = els.filename.value.trim() || "atak-config.pref";
  if (!value.endsWith(".pref")) value += ".pref";
  els.filename.value = value;
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.add("show");
  setTimeout(() => els.toast.classList.remove("show"), 3200);
}

function buildNavigation(filter = "") {
  const lower = filter.toLowerCase();
  const items = [];

  items.push({ id: "connections", label: "Server Connections", group: "Core" });

  for (const category of state.schema.categories) {
    const label = category.title || category.id;
    if (lower && !label.toLowerCase().includes(lower) && !category.id.includes(lower)) {
      continue;
    }
    items.push({ id: category.id, label, group: "Preferences" });
  }

  els.nav.innerHTML = "";
  let currentGroup = "";
  for (const item of items) {
    if (item.group !== currentGroup) {
      currentGroup = item.group;
      const groupLabel = document.createElement("div");
      groupLabel.className = "nav-group-label";
      groupLabel.textContent = currentGroup;
      els.nav.appendChild(groupLabel);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "nav-item" + (state.activePanel === item.id ? " active" : "");
    button.textContent = item.label;
    button.addEventListener("click", () => {
      state.activePanel = item.id;
      buildNavigation(filter);
      renderPanel();
    });
    els.nav.appendChild(button);
  }
}

function renderPanel() {
  if (state.activePanel === "connections") {
    renderConnectionsPanel();
    return;
  }

  const category = state.schema.categories.find((c) => c.id === state.activePanel);
  if (!category) return;

  els.panelTitle.textContent = category.title || category.id;
  els.panelDescription.textContent =
    "Configure preference keys from ATAK " + category.file + ". Leave fields blank to omit them from the generated file.";
  els.form.innerHTML = "";

  if (category.sections.length) {
    for (const section of category.sections) {
      els.form.appendChild(renderSection(section.title, section.fields));
    }
  }
  if (category.fields.length) {
    els.form.appendChild(renderSection("General", category.fields));
  }
}

function renderSection(title, fields) {
  const card = document.createElement("section");
  card.className = "section-card";
  const heading = document.createElement("h3");
  heading.textContent = title;
  card.appendChild(heading);

  const grid = document.createElement("div");
  grid.className = "field-grid";

  for (const field of fields) {
    grid.appendChild(renderPreferenceField(field));
  }

  card.appendChild(grid);
  return card;
}

function renderPreferenceField(field) {
  const wrapper = document.createElement("div");
  wrapper.className = "field";

  const label = document.createElement("label");
  label.textContent = field.title || field.key;
  label.htmlFor = `pref-${field.key}`;
  wrapper.appendChild(label);

  if (field.summary) {
    const summary = document.createElement("div");
    summary.className = "summary";
    summary.textContent = field.summary;
    wrapper.appendChild(summary);
  }

  const current = state.preferences[field.key]?.value;
  let input;

  if (field.type === "boolean") {
    wrapper.classList.add("checkbox-row");
    input = document.createElement("input");
    input.type = "checkbox";
    input.id = `pref-${field.key}`;
    input.checked = current !== undefined ? Boolean(current) : field.default === "true";
    input.addEventListener("change", () => setPreference(field.key, "boolean", input.checked));
    wrapper.insertBefore(input, wrapper.firstChild.nextSibling);
    return wrapper;
  }

  input = document.createElement("input");
  input.id = `pref-${field.key}`;
  input.type = field.type === "integer" ? "number" : "text";
  if (current !== undefined && current !== null) input.value = current;
  else if (field.default) input.value = field.default;
  input.placeholder = field.key;
  input.addEventListener("input", () => {
    const value = field.type === "integer" ? Number(input.value) : input.value;
    setPreference(field.key, field.type || "string", value);
  });
  wrapper.appendChild(input);
  return wrapper;
}

function setPreference(key, type, value) {
  if (value === "" || value === null || value === undefined) {
    delete state.preferences[key];
    return;
  }
  state.preferences[key] = { type, value };
}

function renderConnectionsPanel() {
  els.panelTitle.textContent = "Server Connections";
  els.panelDescription.textContent =
    "Configure CoT inputs, outputs, and streaming connections. These map to the cot_inputs, cot_outputs, and cot_streams preference groups in ATAK.";
  els.form.innerHTML = "";

  for (const group of state.schema.connections.groups) {
    const card = document.createElement("section");
    card.className = "section-card";
    const heading = document.createElement("h3");
    heading.textContent = group.title;
    card.appendChild(heading);

    const description = document.createElement("p");
    description.className = "summary";
    description.textContent = group.description;
    card.appendChild(description);

    const connections = state.connections[group.name] || [];
    const list = document.createElement("div");
    list.dataset.group = group.name;

    if (!connections.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No connections configured yet.";
      list.appendChild(empty);
    } else {
      connections.forEach((conn, index) => {
        list.appendChild(renderConnectionCard(group.name, conn, index));
      });
    }

    card.appendChild(list);

    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "btn btn-secondary";
    addBtn.textContent = "Add Connection";
    addBtn.addEventListener("click", () => {
      state.connections[group.name].push(defaultConnection());
      renderConnectionsPanel();
    });
    card.appendChild(addBtn);

    els.form.appendChild(card);
  }
}

function defaultConnection() {
  const conn = {};
  for (const field of state.schema.connections.connection_fields) {
    if (field.default !== undefined) conn[field.key] = field.default;
  }
  return conn;
}

function renderConnectionCard(groupName, connection, index) {
  const card = document.createElement("div");
  card.className = "connection-card";

  const header = document.createElement("div");
  header.className = "connection-header";
  const title = document.createElement("h4");
  title.textContent = connection.description || connection.connectString || `Connection ${index + 1}`;
  header.appendChild(title);

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-danger";
  removeBtn.textContent = "Remove";
  removeBtn.addEventListener("click", () => {
    state.connections[groupName].splice(index, 1);
    renderConnectionsPanel();
  });
  header.appendChild(removeBtn);
  card.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "field-grid";

  for (const field of state.schema.connections.connection_fields) {
    grid.appendChild(renderConnectionField(groupName, index, field, connection[field.key]));
  }

  card.appendChild(grid);
  return card;
}

function renderConnectionField(groupName, index, field, currentValue) {
  const wrapper = document.createElement("div");
  wrapper.className = "field";

  const label = document.createElement("label");
  label.textContent = field.title;
  wrapper.appendChild(label);

  if (field.help) {
    const help = document.createElement("div");
    help.className = "help";
    help.textContent = field.help;
    wrapper.appendChild(help);
  }

  let input;
  if (field.type === "boolean") {
    wrapper.classList.add("checkbox-row");
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = currentValue !== undefined ? Boolean(currentValue) : Boolean(field.default);
    input.addEventListener("change", () => updateConnection(groupName, index, field.key, input.checked));
    wrapper.insertBefore(input, wrapper.firstChild.nextSibling);
    return wrapper;
  }

  if (field.options) {
    input = document.createElement("select");
    for (const option of field.options) {
      const opt = document.createElement("option");
      opt.value = option;
      opt.textContent = option;
      input.appendChild(opt);
    }
    if (currentValue) input.value = currentValue;
    input.addEventListener("change", () => updateConnection(groupName, index, field.key, input.value));
    wrapper.appendChild(input);
    return wrapper;
  }

  input = document.createElement("input");
  input.type = field.sensitive ? "password" : field.type === "long" ? "number" : "text";
  if (currentValue !== undefined && currentValue !== null) input.value = currentValue;
  input.addEventListener("input", () => {
    let value = input.value;
    if (field.type === "long") value = Number(value);
    updateConnection(groupName, index, field.key, value);
  });
  wrapper.appendChild(input);
  return wrapper;
}

function updateConnection(groupName, index, key, value) {
  if (value === "") {
    delete state.connections[groupName][index][key];
    return;
  }
  state.connections[groupName][index][key] = value;
  if (key === "description" || key === "connectString") {
    renderConnectionsPanel();
  }
}

function buildPayload() {
  normalizeFilename();
  return {
    filename: els.filename.value,
    preference_name: els.preferenceName.value.trim() || "com.atakmap.civ_preferences",
    connections: state.connections,
    preferences: state.preferences,
  };
}

async function downloadPref() {
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Failed to generate .pref file");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = els.filename.value;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast("Download started");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function previewPref() {
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    if (!response.ok) throw new Error("Failed to generate preview");
    els.previewContent.textContent = await response.text();
    els.previewDialog.showModal();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function importPref(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/parse", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Import failed");

    state.preferences = data.preferences || {};
    state.connections = {
      cot_inputs: data.connections?.cot_inputs || [],
      cot_outputs: data.connections?.cot_outputs || [],
      cot_streams: data.connections?.cot_streams || [],
    };
    if (data.preference_name) els.preferenceName.value = data.preference_name;
    renderPanel();
    showToast(`Imported ${file.name}`);
  } catch (error) {
    showToast(error.message, true);
  }
}

init();
