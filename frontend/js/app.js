const PREFERENCE_GROUP = "com.atakmap.app.civ_preferences";

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
  els.filename.addEventListener("change", normalizeFilename);
}

function normalizeFilename() {
  let value = els.filename.value.trim() || "tak-civ-config.pref";
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
  const items = [{ id: "connections", label: "Server Connections", group: "TAK-CIV" }];

  for (const category of state.schema.categories) {
    const label = category.title || category.id;
    if (lower && !label.toLowerCase().includes(lower) && !category.id.includes(lower)) continue;
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
    `TAK-CIV settings from ${category.file}. Leave fields unset to omit them from the generated .pref file.`;
  els.form.innerHTML = "";

  for (const section of category.sections) {
    els.form.appendChild(renderSection(section.title, section.fields));
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

function createLabel(text, id) {
  const label = document.createElement("label");
  label.textContent = text;
  if (id) label.htmlFor = id;
  return label;
}

function createSelect(options, currentValue, onChange, includeBlank = true) {
  const select = document.createElement("select");
  if (includeBlank) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "— Not set —";
    select.appendChild(blank);
  }
  for (const option of options) {
    const opt = document.createElement("option");
    opt.value = String(option.value);
    opt.textContent = option.label ?? option.value;
    select.appendChild(opt);
  }
  if (currentValue !== undefined && currentValue !== null && currentValue !== "") {
    select.value = String(currentValue);
  }
  select.addEventListener("change", () => onChange(select.value));
  return select;
}

function createMultiSelect(field, currentValue, onChange) {
  const box = document.createElement("div");
  box.className = "multiselect-box";
  const selected = new Set(Array.isArray(currentValue) ? currentValue : []);

  for (const option of field.options || []) {
    const row = document.createElement("label");
    row.className = "multiselect-option";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = String(option.value);
    checkbox.checked = selected.has(String(option.value));
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selected.add(String(option.value));
      else selected.delete(String(option.value));
      onChange(Array.from(selected));
    });
    row.appendChild(checkbox);
    row.append(" ", option.label ?? option.value);
    box.appendChild(row);
  }
  return box;
}

function renderSelectField(field, currentValue, onChange) {
  const wrapper = document.createElement("div");
  wrapper.className = "field";

  wrapper.appendChild(createLabel(field.title || field.key, `pref-${field.key}`));

  if (field.summary) {
    const summary = document.createElement("div");
    summary.className = "summary";
    summary.textContent = field.summary;
    wrapper.appendChild(summary);
  }

  const knownValues = new Set((field.options || []).map((o) => String(o.value)));
  const isCustom = currentValue !== undefined && currentValue !== null && !knownValues.has(String(currentValue));

  const select = createSelect(
    field.options || [],
    isCustom ? "__custom__" : currentValue,
    () => {}
  );
  select.id = `pref-${field.key}`;

  let customInput = null;
  if (field.allow_custom) {
    customInput = document.createElement("input");
    customInput.type = "text";
    customInput.className = "custom-option-input";
    customInput.placeholder = "Custom path or value";
    customInput.hidden = !isCustom && select.value !== "__custom__";
    if (isCustom) customInput.value = currentValue;
  }

  select.addEventListener("change", () => {
    const value = select.value;
    if (value === "") onChange(null);
    else if (value === "__custom__") onChange(customInput?.value || null);
    else onChange(value);
    if (customInput) customInput.hidden = value !== "__custom__";
  });

  if (customInput) {
    customInput.addEventListener("input", () => {
      if (select.value === "__custom__") onChange(customInput.value || null);
    });
  }

  wrapper.appendChild(select);
  if (customInput) wrapper.appendChild(customInput);

  return wrapper;
}

function storageMeta(field) {
  const storageType =
    field.storage_type ||
    (field.type === "multiselect" ? "set" : field.type === "select" ? "string" : field.type);
  return {
    type: storageType,
    java_class: field.java_class || null,
  };
}

function normalizeStoredValue(field, value) {
  if (value === null || value === undefined || value === "") return null;
  const meta = storageMeta(field);
  if (meta.type === "boolean") return value === true || value === "true";
  if (meta.type === "set") return Array.isArray(value) ? value.map(String) : [];
  if (meta.type === "string") return String(value);
  if (meta.type === "integer") return Number(value);
  if (meta.type === "float") return Number(value);
  return value;
}

function setPreferenceFromField(field, value) {
  const key = field.key;
  const normalized = normalizeStoredValue(field, value);
  if (normalized === null || normalized === "" || (Array.isArray(normalized) && !normalized.length)) {
    delete state.preferences[key];
    return;
  }
  const meta = storageMeta(field);
  state.preferences[key] = {
    type: meta.type,
    value: normalized,
    ...(meta.java_class ? { java_class: meta.java_class } : {}),
  };
}

function renderPreferenceField(field) {
  const current = state.preferences[field.key]?.value;

  if (field.type === "select" || (field.type === "boolean" && field.input === "select")) {
    return renderSelectField(field, current, (value) => setPreferenceFromField(field, value));
  }

  if (field.type === "multiselect") {
    const wrapper = document.createElement("div");
    wrapper.className = "field";
    wrapper.appendChild(createLabel(field.title || field.key));
    if (field.summary) {
      const summary = document.createElement("div");
      summary.className = "summary";
      summary.textContent = field.summary;
      wrapper.appendChild(summary);
    }
    wrapper.appendChild(
      createMultiSelect(field, current, (values) => setPreferenceFromField(field, values))
    );
    return wrapper;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "field";
  wrapper.appendChild(createLabel(field.title || field.key, `pref-${field.key}`));
  if (field.summary) {
    const summary = document.createElement("div");
    summary.className = "summary";
    summary.textContent = field.summary;
    wrapper.appendChild(summary);
  }

  const input = document.createElement("input");
  input.id = `pref-${field.key}`;
  input.type = field.type === "integer" ? "number" : "text";
  if (current !== undefined && current !== null) input.value = current;
  else if (field.default) input.value = field.default;
  input.placeholder = field.key;
  input.addEventListener("input", () => {
    const raw = field.type === "integer" ? input.value : input.value;
    setPreferenceFromField(field, raw === "" ? null : field.type === "integer" ? Number(raw) : raw);
  });
  wrapper.appendChild(input);
  return wrapper;
}

function parseConnectString(connectString = "") {
  const parts = connectString.split(":");
  return {
    proto: parts[0] || "ssl",
    host: parts[1] || "",
    port: parts[2] || "8089",
    iface: parts[3] || "stream",
  };
}

function buildConnectString(parts) {
  if (!parts.host) return "";
  return `${parts.proto}:${parts.host}:${parts.port}:${parts.iface}`;
}

function renderConnectionsPanel() {
  els.panelTitle.textContent = "TAK-CIV Server Connections";
  els.panelDescription.textContent =
    "Configure CoT inputs, outputs, and streaming connections for TAK-CIV (cot_inputs, cot_outputs, cot_streams).";
  els.form.innerHTML = "";

  for (const group of state.schema.connections.groups) {
    const card = document.createElement("section");
    card.className = "section-card";
    card.appendChild(Object.assign(document.createElement("h3"), { textContent: group.title }));
    card.appendChild(Object.assign(document.createElement("p"), { className: "summary", textContent: group.description }));

    const connections = state.connections[group.name] || [];
    const list = document.createElement("div");
    if (!connections.length) {
      list.appendChild(Object.assign(document.createElement("div"), {
        className: "empty-state",
        textContent: "No connections configured yet.",
      }));
    } else {
      connections.forEach((conn, index) => list.appendChild(renderConnectionCard(group.name, conn, index)));
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
    if (field.type === "connect_string") {
      conn.connectString = buildConnectString({
        proto: field.parts.proto.default,
        host: "",
        port: String(field.parts.port.default),
        iface: field.parts.iface.default,
      });
    } else if (field.default !== undefined) {
      conn[field.key] = field.default;
    }
  }
  return conn;
}

function renderConnectionCard(groupName, connection, index) {
  const card = document.createElement("div");
  card.className = "connection-card";
  const header = document.createElement("div");
  header.className = "connection-header";
  header.appendChild(Object.assign(document.createElement("h4"), {
    textContent: connection.description || connection.connectString || `Connection ${index + 1}`,
  }));
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
    grid.appendChild(renderConnectionField(groupName, index, field, connection));
  }
  card.appendChild(grid);
  return card;
}

function renderConnectionField(groupName, index, field, connection) {
  const currentValue = connection[field.key];

  if (field.type === "connect_string") {
    const wrapper = document.createElement("div");
    wrapper.className = "field field-wide";
    wrapper.appendChild(createLabel(field.title));
    if (field.help) {
      wrapper.appendChild(Object.assign(document.createElement("div"), { className: "help", textContent: field.help }));
    }

    const parts = parseConnectString(connection.connectString);
    const subgrid = document.createElement("div");
    subgrid.className = "field-grid";

    const updateConnect = () => {
      const next = buildConnectString(parts);
      if (next) updateConnection(groupName, index, "connectString", next);
      else delete state.connections[groupName][index].connectString;
      renderConnectionsPanel();
    };

    for (const [partKey, partField] of Object.entries(field.parts)) {
      const partWrap = document.createElement("div");
      partWrap.className = "field";
      partWrap.appendChild(createLabel(partField.label));

      if (partField.type === "select") {
        partWrap.appendChild(
          createSelect(partField.options, parts[partKey] ?? partField.default, (value) => {
            parts[partKey] = value;
            updateConnect();
          }, false)
        );
      } else {
        const input = document.createElement("input");
        input.type = partField.type === "integer" ? "number" : "text";
        input.value = parts[partKey] ?? partField.default ?? "";
        input.placeholder = partField.placeholder || "";
        input.addEventListener("change", () => {
          parts[partKey] = input.value;
          updateConnect();
        });
        partWrap.appendChild(input);
      }
      subgrid.appendChild(partWrap);
    }

    wrapper.appendChild(subgrid);
    const preview = document.createElement("div");
    preview.className = "summary";
    preview.textContent = `Connect string: ${connection.connectString || "(incomplete)"}`;
    wrapper.appendChild(preview);
    return wrapper;
  }

  if (field.type === "select" || (field.type === "boolean" && field.input === "select")) {
    return renderSelectField(field, currentValue, (value) => {
      if (value === null || value === "") delete state.connections[groupName][index][field.key];
      else if (field.type === "boolean") updateConnection(groupName, index, field.key, value === "true");
      else updateConnection(groupName, index, field.key, value);
    });
  }

  const wrapper = document.createElement("div");
  wrapper.className = "field";
  wrapper.appendChild(createLabel(field.title));
  if (field.help) wrapper.appendChild(Object.assign(document.createElement("div"), { className: "help", textContent: field.help }));

  const input = document.createElement("input");
  input.type = field.input === "password" || field.sensitive ? "password" : field.type === "integer" ? "number" : "text";
  if (currentValue !== undefined && currentValue !== null) input.value = currentValue;
  input.addEventListener("input", () => updateConnection(groupName, index, field.key, field.type === "integer" ? Number(input.value) : input.value));
  wrapper.appendChild(input);
  return wrapper;
}

function updateConnection(groupName, index, key, value) {
  if (value === "" || value === null || value === undefined) {
    delete state.connections[groupName][index][key];
    return;
  }
  state.connections[groupName][index][key] = value;
}

function buildPayload() {
  normalizeFilename();
  return {
    filename: els.filename.value,
    preference_name: PREFERENCE_GROUP,
    include_empty_connection_groups: true,
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
    renderPanel();
    showToast(`Imported ${file.name}`);
  } catch (error) {
    showToast(error.message, true);
  }
}

init();
