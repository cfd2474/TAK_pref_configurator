const PREFERENCE_GROUP = "com.atakmap.app.civ_preferences";

const COT_PANELS = ["cot_inputs", "cot_outputs", "cot_streams"];

const CUSTOM_PREF_TYPES = [
  { value: "string", label: "String" },
  { value: "boolean", label: "Boolean" },
  { value: "integer", label: "Integer" },
  { value: "float", label: "Float" },
];

const JAVA_CLASSES = {
  boolean: "class java.lang.Boolean",
  integer: "class java.lang.Integer",
  string: "class java.lang.String",
  float: "class java.lang.Float",
};

const UNSET_OPTION_LABEL = "— Not set —";

function isUnsetOption(option) {
  const value = String(option.value ?? "");
  if (value !== "") return false;
  const label = String(option.label ?? "")
    .trim()
    .toLowerCase()
    .replace(/^[-—–\s]+|[-—–\s]+$/g, "");
  return !label || label === "not set" || label === "unset";
}

function optionLabel(option) {
  if (isUnsetOption(option)) return UNSET_OPTION_LABEL;
  return option.label ?? option.value;
}

const state = {
  schema: null,
  schemaFieldKeys: new Set(),
  activePanel: "cot_streams",
  preferences: {},
  pluginCategories: [],
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
  importPluginApk: document.getElementById("import-plugin-apk"),
  apkScanDialog: document.getElementById("apk-scan-dialog"),
  apkScanTitle: document.getElementById("apk-scan-title"),
  apkScanSpinner: document.getElementById("apk-scan-spinner"),
  apkScanMessage: document.getElementById("apk-scan-message"),
  apkScanDetails: document.getElementById("apk-scan-details"),
  apkScanWarnings: document.getElementById("apk-scan-warnings"),
  apkScanAck: document.getElementById("apk-scan-ack"),
  previewDialog: document.getElementById("preview-dialog"),
  previewContent: document.getElementById("preview-content"),
  closePreview: document.getElementById("close-preview"),
  toast: document.getElementById("toast"),
  content: document.querySelector(".content"),
};

async function init() {
  try {
    const response = await fetch("/api/schema");
    if (!response.ok) throw new Error("Failed to load schema");
    state.schema = await response.json();
    state.schemaFieldKeys = buildSchemaFieldKeys();
    buildNavigation();
    renderPanel();
    bindEvents();
  } catch (error) {
    showToast(error.message, true);
  }
}

function bindEvents() {
  els.search.addEventListener("input", () => {
    buildNavigation(getActiveSearchFilter());
    renderPanel();
  });
  els.downloadBtn.addEventListener("click", downloadPref);
  els.previewBtn.addEventListener("click", previewPref);
  els.importFile.addEventListener("change", importPref);
  els.importPluginApk.addEventListener("change", importPluginApk);
  els.apkScanAck.addEventListener("click", () => els.apkScanDialog.close());
  els.apkScanDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
  });
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

function scrollContentToTop() {
  if (!els.content) return;
  els.content.scrollTop = 0;
  requestAnimationFrame(() => {
    if (els.content) els.content.scrollTop = 0;
  });
}

function allCategories() {
  return [...(state.schema?.categories || []), ...state.pluginCategories];
}

function rebuildSchemaFieldKeys() {
  state.schemaFieldKeys = buildSchemaFieldKeys();
}

function buildSchemaFieldKeys() {
  const keys = new Set();
  for (const category of allCategories()) {
    for (const field of category.fields || []) keys.add(field.key);
    for (const section of category.sections || []) {
      for (const field of section.fields || []) keys.add(field.key);
    }
  }
  return keys;
}

function isCotPanel(panelId) {
  return COT_PANELS.includes(panelId);
}

function getConnectionGroup(panelId) {
  return state.schema.connections.groups.find((group) => group.name === panelId);
}

function getActiveSearchFilter() {
  return els.search?.value.trim() || "";
}

function fieldSearchHaystack(field) {
  const parts = [
    field.title,
    field.key,
    field.summary,
    field.reference_hint,
    field.placeholder,
  ];
  for (const option of field.options || []) {
    parts.push(option.label, option.value);
  }
  return parts.filter(Boolean).join(" ").toLowerCase();
}

function fieldMatchesSearch(field, lower) {
  if (!lower) return true;
  return fieldSearchHaystack(field).includes(lower);
}

function formatFieldMatchHint(matches) {
  if (!matches.length) return "";
  const titles = matches.map((match) => match.field.title || match.field.key);
  const first = titles[0];
  if (titles.length === 1) return `Matches: ${first}`;
  return `Matches: ${first} +${titles.length - 1} more`;
}

function formatKeyMatchHint(keys) {
  if (!keys.length) return "";
  if (keys.length === 1) return `Matches: ${keys[0]}`;
  return `Matches: ${keys[0]} +${keys.length - 1} more`;
}

function searchCategory(category, lower) {
  const label = category.title || category.id;
  const nameMatch =
    !lower ||
    label.toLowerCase().includes(lower) ||
    category.id.toLowerCase().includes(lower);

  const matchingFields = [];
  const collectFields = (fields, sectionTitle = null) => {
    for (const field of fields || []) {
      if (fieldMatchesSearch(field, lower)) {
        matchingFields.push({ field, sectionTitle });
      }
    }
  };

  if (lower) {
    for (const section of category.sections || []) {
      collectFields(section.fields, section.title || null);
    }
    collectFields(category.fields || []);
  }

  return {
    nameMatch,
    matchingFields,
    matches: nameMatch || matchingFields.length > 0,
  };
}

function connectionGroupMatchesSearch(group, lower) {
  if (!lower) return { matches: true, nameMatch: true, matchHint: "" };
  const nameMatch =
    group.title.toLowerCase().includes(lower) || group.name.toLowerCase().includes(lower);
  const descriptionMatch = (group.description || "").toLowerCase().includes(lower);
  return {
    matches: nameMatch || descriptionMatch,
    nameMatch,
    matchHint: descriptionMatch && !nameMatch ? "Matches: description" : "",
  };
}

function customPreferencesMatchesSearch(lower) {
  const label = "Custom Preferences";
  if (!lower) return { matches: true, nameMatch: true, matchHint: "", matchingKeys: [] };
  const nameMatch = label.toLowerCase().includes(lower);
  const matchingKeys = listCustomPreferenceKeys().filter((key) => key.toLowerCase().includes(lower));
  return {
    matches: nameMatch || matchingKeys.length > 0,
    nameMatch,
    matchingKeys,
    matchHint: matchingKeys.length && !nameMatch ? formatKeyMatchHint(matchingKeys) : "",
  };
}

function compareNavLabels(a, b) {
  return a.localeCompare(b, undefined, { sensitivity: "base" });
}

function buildNavigation(filter = "") {
  const lower = filter.toLowerCase();
  const items = [];

  for (const group of state.schema.connections.groups) {
    const groupMatch = connectionGroupMatchesSearch(group, lower);
    if (lower && !groupMatch.matches) continue;
    items.push({
      id: group.name,
      label: group.title,
      group: "CoT Settings",
      matchHint: groupMatch.matchHint,
      nameMatch: groupMatch.nameMatch,
    });
  }

  const customMatch = customPreferencesMatchesSearch(lower);
  if (customMatch.matches) {
    items.push({
      id: "custom_prefs",
      label: "Custom Preferences",
      group: "ATAK Settings",
      matchHint: customMatch.matchHint,
      nameMatch: customMatch.nameMatch,
      matchingKeys: customMatch.matchingKeys,
    });
  }

  const schemaItems = [];
  for (const category of state.schema.categories) {
    if (category.nav_hidden || !hasExportableFields(category)) continue;
    const label = category.title || category.id;
    const categoryMatch = searchCategory(category, lower);
    if (lower && !categoryMatch.matches) continue;
    schemaItems.push({
      id: category.id,
      label,
      group: "ATAK Settings",
      matchHint:
        categoryMatch.matchingFields.length && !categoryMatch.nameMatch
          ? formatFieldMatchHint(categoryMatch.matchingFields)
          : "",
      nameMatch: categoryMatch.nameMatch,
      matchingFields: categoryMatch.matchingFields,
    });
  }
  schemaItems.sort((a, b) => compareNavLabels(a.label, b.label));
  items.push(...schemaItems);

  const pluginItems = [];
  for (const category of state.pluginCategories) {
    const label = category.title || category.id;
    const categoryMatch = searchCategory(category, lower);
    if (lower && !categoryMatch.matches) continue;
    pluginItems.push({
      id: category.id,
      label,
      group: "ATAK Settings",
      plugin: true,
      deletable: true,
      matchHint:
        categoryMatch.matchingFields.length && !categoryMatch.nameMatch
          ? formatFieldMatchHint(categoryMatch.matchingFields)
          : "",
      nameMatch: categoryMatch.nameMatch,
      matchingFields: categoryMatch.matchingFields,
    });
  }
  pluginItems.sort((a, b) => compareNavLabels(a.label, b.label));
  items.push(...pluginItems);

  ensureActivePanelVisible(items);

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
    const row = document.createElement("div");
    row.className = "nav-item-row" + (state.activePanel === item.id ? " active" : "");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "nav-item" + (state.activePanel === item.id ? " active" : "");
    if (item.plugin) button.classList.add("plugin-nav-item");
    if (item.matchHint) button.classList.add("nav-item-has-match");

    const content = document.createElement("span");
    content.className = "nav-item-content";
    const labelEl = document.createElement("span");
    labelEl.className = "nav-item-label";
    labelEl.textContent = item.label;
    content.appendChild(labelEl);
    if (item.matchHint) {
      const hintEl = document.createElement("span");
      hintEl.className = "nav-item-match";
      hintEl.textContent = item.matchHint;
      content.appendChild(hintEl);
    }
    button.appendChild(content);

    button.addEventListener("click", () => {
      if (state.activePanel === item.id) return;
      state.activePanel = item.id;
      buildNavigation(filter);
      renderPanel();
      scrollContentToTop();
    });
    row.appendChild(button);

    if (item.deletable) {
      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "nav-delete-btn";
      deleteBtn.title = "Remove category";
      deleteBtn.setAttribute("aria-label", `Remove ${item.label}`);
      deleteBtn.textContent = "×";
      deleteBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        removePluginCategory(item.id);
      });
      row.appendChild(deleteBtn);
    }

    els.nav.appendChild(row);
  }
}

function renderPanel() {
  if (isCotPanel(state.activePanel)) {
    renderSingleConnectionGroup(state.activePanel);
    return;
  }

  if (state.activePanel === "custom_prefs") {
    renderCustomPreferencesPanel();
    return;
  }

  const category = allCategories().find((c) => c.id === state.activePanel);
  if (!category) return;

  els.panelTitle.textContent = category.title || category.id;
  if (category.source === "plugin_apk") {
    const group = category.preference_group || PREFERENCE_GROUP;
    const warnings = (category.warnings || []).join(" ");
    els.panelDescription.textContent =
      `Scanned from plugin APK (${category.plugin?.package || "unknown"}). Exports to ${group}. ${warnings}`;
  } else {
    els.panelDescription.textContent =
      "ATAK Shared Preferences (com.atakmap.app.civ_preferences). Leave fields unset or Off to omit them from the generated .pref file.";
  }
  els.form.innerHTML = "";

  const searchContext = getCategorySearchContext(category);
  if (searchContext.lower) {
    const categoryMatch = searchCategory(category, searchContext.lower);
    prependSearchFilterBanner(els.form, {
      lower: searchContext.lower,
      matchCount: categoryMatch.nameMatch ? null : categoryMatch.matchingFields.length,
      label: "field",
    });
  }

  if (category.source === "plugin_apk") {
    const meta = document.createElement("div");
    meta.className = "plugin-meta";
    meta.textContent = `Found ${countCategoryFields(category)} preference fields from ${category.file || "APK"}.`;
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "btn btn-danger plugin-remove-btn";
    removeBtn.textContent = "Delete Category";
    removeBtn.addEventListener("click", () => removePluginCategory(category.id));
    meta.appendChild(removeBtn);
    els.form.appendChild(meta);
  }

  for (const section of category.sections || []) {
    const card = renderSection(section.title, section.fields, getCategorySearchContext(category));
    if (card) els.form.appendChild(card);
  }
  if (category.fields?.length) {
    const card = renderSection("General", category.fields, getCategorySearchContext(category));
    if (card) els.form.appendChild(card);
  }
}

function getCategorySearchContext(category) {
  const lower = getActiveSearchFilter().toLowerCase();
  if (!lower) return { lower: "", nameMatch: true };
  const categoryMatch = searchCategory(category, lower);
  return {
    lower,
    nameMatch: categoryMatch.nameMatch,
  };
}

function categoryFieldKeys(category) {
  return categoryFields(category).map((field) => field.key);
}

function countCategoryFields(category) {
  return categoryFieldKeys(category).length;
}

function removePluginCategory(categoryId) {
  const category = state.pluginCategories.find((entry) => entry.id === categoryId);
  if (category) {
    for (const key of categoryFieldKeys(category)) {
      delete state.preferences[key];
    }
  }

  state.pluginCategories = state.pluginCategories.filter((entry) => entry.id !== categoryId);
  if (state.activePanel === categoryId) {
    state.activePanel = state.pluginCategories.length
      ? state.pluginCategories[state.pluginCategories.length - 1].id
      : "custom_prefs";
  }
  rebuildSchemaFieldKeys();
  buildNavigation(els.search.value.trim());
  renderPanel();
  scrollContentToTop();
  showToast("Plugin category removed");
}

function resetApkScanModal() {
  els.apkScanTitle.textContent = "Scan Plugin APK";
  els.apkScanSpinner.hidden = true;
  els.apkScanMessage.textContent = "";
  els.apkScanMessage.className = "apk-scan-message";
  els.apkScanDetails.hidden = true;
  els.apkScanDetails.innerHTML = "";
  els.apkScanWarnings.hidden = true;
  els.apkScanWarnings.innerHTML = "";
  els.apkScanAck.disabled = true;
}

function appendApkScanDetail(label, value) {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  els.apkScanDetails.appendChild(dt);
  els.apkScanDetails.appendChild(dd);
}

function setApkScanModalState(state, payload = {}) {
  resetApkScanModal();

  if (state === "scanning") {
    els.apkScanTitle.textContent = "Scanning Plugin APK";
    els.apkScanSpinner.hidden = false;
    els.apkScanMessage.textContent = `Reading and decoding ${payload.filename || "APK"}…`;
    els.apkScanMessage.classList.add("is-scanning");
    return;
  }

  els.apkScanAck.disabled = false;

  if (state === "success") {
    els.apkScanTitle.textContent = "Plugin Scan Complete";
    els.apkScanMessage.textContent = `Found ${payload.fieldCount} preference field${payload.fieldCount === 1 ? "" : "s"}. Category added to navigation.`;
    els.apkScanMessage.classList.add("is-success");
    els.apkScanDetails.hidden = false;
    appendApkScanDetail("File", payload.filename || "—");
    appendApkScanDetail("Plugin", payload.pluginName || "—");
    appendApkScanDetail("Package", payload.pluginPackage || "—");
    appendApkScanDetail("Category", payload.categoryTitle || "—");
    appendApkScanDetail("Preference fields", String(payload.fieldCount));
    if (payload.sourceFiles?.length) {
      appendApkScanDetail("Source XML", payload.sourceFiles.join(", "));
    }
  } else if (state === "empty") {
    els.apkScanTitle.textContent = "No Preferences Found";
    els.apkScanMessage.textContent =
      "The APK was scanned successfully, but no preference fields were extracted. No category was added.";
    els.apkScanMessage.classList.add("is-warning");
    els.apkScanDetails.hidden = false;
    appendApkScanDetail("File", payload.filename || "—");
    appendApkScanDetail("Plugin", payload.pluginName || "—");
    appendApkScanDetail("Package", payload.pluginPackage || "—");
    if (payload.sourceFiles?.length) {
      appendApkScanDetail("XML scanned", payload.sourceFiles.join(", "));
    }
  } else {
    els.apkScanTitle.textContent = "Plugin Scan Failed";
    els.apkScanMessage.textContent = payload.message || "Unable to scan this APK.";
    els.apkScanMessage.classList.add("is-error");
    els.apkScanDetails.hidden = false;
    appendApkScanDetail("File", payload.filename || "—");
  }

  const warnings = payload.warnings || [];
  if (warnings.length) {
    els.apkScanWarnings.hidden = false;
    for (const warning of warnings) {
      const item = document.createElement("li");
      item.textContent = warning;
      els.apkScanWarnings.appendChild(item);
    }
  }
}

function openApkScanModal(filename) {
  resetApkScanModal();
  setApkScanModalState("scanning", { filename });
  els.apkScanDialog.showModal();
}

async function importPluginApk(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;

  if (!file.name.toLowerCase().endsWith(".apk")) {
    showToast("Upload an .apk file", true);
    return;
  }

  openApkScanModal(file.name);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/plugins/scan", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Plugin scan failed");

    const fieldCount = data.stats?.field_count ?? 0;
    const modalPayload = {
      filename: file.name,
      pluginName: data.plugin?.name,
      pluginPackage: data.plugin?.package,
      categoryTitle: data.category?.title,
      fieldCount,
      sourceFiles: data.stats?.source_files || [],
      warnings: data.warnings || [],
    };

    if (fieldCount === 0) {
      setApkScanModalState("empty", modalPayload);
      return;
    }

    const category = {
      ...data.category,
      preference_group: data.preference_group,
      plugin: data.plugin,
      warnings: data.warnings || [],
    };

    state.pluginCategories = state.pluginCategories.filter((existing) => existing.id !== category.id);
    state.pluginCategories.push(category);
    rebuildSchemaFieldKeys();
    state.activePanel = category.id;
    buildNavigation(els.search.value.trim());
    renderPanel();
    scrollContentToTop();
    setApkScanModalState("success", modalPayload);
  } catch (error) {
    setApkScanModalState("error", {
      filename: file.name,
      message: error.message,
    });
  }
}

function categoryFields(category) {
  const fields = [];
  for (const field of category.fields || []) fields.push(field);
  for (const section of category.sections || []) {
    for (const field of section.fields || []) fields.push(field);
  }
  return fields;
}

function exportableFields(fields) {
  return (fields || []).filter((field) => shouldShowField(field));
}

function shouldShowField(field) {
  if (field.exportable === false) return false;
  if (field.key === "custom_color_selected" || field.key === "custom_outline_color_selected") {
    const mode = getGpsIconColorMode();
    if (mode && mode !== "custom") return false;
  }
  return true;
}

const GPS_ICON_COLOR_KEYS = {
  default: "default_gps_icon",
  team: "team_color_gps_icon",
  custom: "custom_color_gps_icon_pref",
};

function getGpsIconColorMode() {
  if (state.preferences[GPS_ICON_COLOR_KEYS.custom]?.value) return "custom";
  if (state.preferences[GPS_ICON_COLOR_KEYS.team]?.value) return "team";
  if (state.preferences[GPS_ICON_COLOR_KEYS.default]?.value) return "default";
  return "";
}

function setGpsIconColorMode(mode) {
  for (const key of Object.values(GPS_ICON_COLOR_KEYS)) {
    delete state.preferences[key];
  }
  if (!mode) return;
  const prefKey = GPS_ICON_COLOR_KEYS[mode];
  if (!prefKey) return;
  state.preferences[prefKey] = {
    type: "boolean",
    value: true,
    java_class: JAVA_CLASSES.boolean,
  };
}

function hasExportableFields(category) {
  return exportableFields(categoryFields(category)).length > 0;
}

function ensureActivePanelVisible(items) {
  if (items.some((item) => item.id === state.activePanel)) return;
  state.activePanel = items[0]?.id || "custom_prefs";
}

function renderSection(title, fields, searchContext = {}) {
  const { lower = "", nameMatch = true } = searchContext;
  const sectionTitleMatch = lower && title.toLowerCase().includes(lower);
  let visibleFields = exportableFields(fields);
  if (lower && !nameMatch && !sectionTitleMatch) {
    visibleFields = visibleFields.filter((field) => fieldMatchesSearch(field, lower));
  }
  if (!visibleFields.length) return null;

  const card = document.createElement("section");
  card.className = "section-card";
  if (lower && sectionTitleMatch) card.classList.add("search-section-match");
  const heading = document.createElement("h3");
  heading.textContent = title;
  card.appendChild(heading);

  const grid = document.createElement("div");
  grid.className = "field-grid";
  for (const field of visibleFields) {
    const fieldEl = renderPreferenceField(field);
    if (lower && fieldMatchesSearch(field, lower)) {
      fieldEl.classList.add("search-match");
    }
    grid.appendChild(fieldEl);
  }
  card.appendChild(grid);
  return card;
}

function createLabel(text, id, required = false) {
  const label = document.createElement("label");
  label.textContent = text;
  if (id) label.htmlFor = id;
  if (required) label.classList.add("required");
  return label;
}

function createSelect(options, currentValue, onChange, includeBlank = true) {
  const select = document.createElement("select");
  if (includeBlank) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = UNSET_OPTION_LABEL;
    select.appendChild(blank);
  }
  for (const option of options) {
    const opt = document.createElement("option");
    opt.value = String(option.value);
    opt.textContent = optionLabel(option);
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

function normalizeFieldDescription(text) {
  if (!text) return "";
  return text
    .replace(/\s*\.\.\.\s*Read More\s*$/i, "")
    .replace(/\s*Read More\s*$/i, "")
    .trim();
}

function getFieldDescription(field) {
  return normalizeFieldDescription(field.summary || field.reference_hint || "");
}

function appendFieldDescription(wrapper, field) {
  const description = getFieldDescription(field);
  if (!description) return;
  const summary = document.createElement("div");
  summary.className = "summary";
  summary.textContent = description;
  wrapper.appendChild(summary);
}

function renderSelectField(field, currentValue, onChange) {
  const wrapper = document.createElement("div");
  wrapper.className = "field";

  wrapper.appendChild(createLabel(field.title || field.key, `pref-${field.key}`));
  appendFieldDescription(wrapper, field);

  const knownValues = new Set((field.options || []).map((o) => String(o.value)));
  const isCustom = currentValue !== undefined && currentValue !== null && !knownValues.has(String(currentValue));

  const includeBlank = field.input !== "tristate";
  const select = createSelect(
    field.options || [],
    isCustom ? "__custom__" : currentValue,
    () => {},
    includeBlank
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
  if (meta.type === "boolean") {
    if (value === false || value === "false") return false;
    return value === true || value === "true";
  }
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

function isAndroidResourceRef(value) {
  return typeof value === "string" && value.startsWith("@");
}

function fieldPlaceholder(field) {
  if (field.placeholder) return field.placeholder;
  if (field.reference_hint) return field.reference_hint;
  const key = field.key.toLowerCase();
  if (key.includes("url")) return "https://your-server:8443/update";
  if (key.includes("path") || key.includes("directory")) return "/path/on/device";
  if (field.summary) return field.summary;
  return "";
}

function defaultFieldValue(field) {
  const value = field.default;
  if (value === null || value === undefined || value === "") return null;
  if (isAndroidResourceRef(value) || value === "(built-in)") return null;
  return value;
}

function isColorField(field) {
  return field.input === "color";
}

function colorFormat(field) {
  if (field.color_format) return field.color_format;
  if (field.reference_hint === "-1 through -16777216") return "android_int";
  return "hex";
}

function androidColorToHex(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "#ffffff";
  const u = n >>> 0;
  const r = (u >> 16) & 255;
  const g = (u >> 8) & 255;
  const b = u & 255;
  return `#${[r, g, b].map((part) => part.toString(16).padStart(2, "0")).join("")}`;
}

function hexToAndroidColorInt(hex) {
  const normalized = normalizeHexColor(hex);
  if (!normalized) return null;
  const raw = normalized.slice(1);
  const r = parseInt(raw.slice(0, 2), 16);
  const g = parseInt(raw.slice(2, 4), 16);
  const b = parseInt(raw.slice(4, 6), 16);
  const argb = (255 << 24) | (r << 16) | (g << 8) | b;
  return String(argb | 0);
}

function normalizeHexColor(value) {
  const raw = String(value ?? "").trim();
  if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toLowerCase();
  if (/^[0-9a-fA-F]{6}$/.test(raw)) return `#${raw.toLowerCase()}`;
  return null;
}

function colorValueToHex(field, value) {
  if (value === null || value === undefined || value === "") {
    return "#ffffff";
  }
  if (colorFormat(field) === "android_int") {
    return androidColorToHex(value);
  }
  return normalizeHexColor(value) || "#ffffff";
}

function storedColorValue(field, hex) {
  if (colorFormat(field) === "android_int") {
    return hexToAndroidColorInt(hex);
  }
  return normalizeHexColor(hex);
}

function renderColorField(field, current, onChange) {
  const wrapper = document.createElement("div");
  wrapper.className = "field color-field";
  wrapper.appendChild(createLabel(field.title || field.key, `pref-${field.key}-picker`));
  appendFieldDescription(wrapper, field);

  const row = document.createElement("div");
  row.className = "color-input-row";

  const picker = document.createElement("input");
  picker.type = "color";
  picker.id = `pref-${field.key}-picker`;
  picker.className = "color-picker";
  picker.value = colorValueToHex(field, current ?? defaultFieldValue(field));

  const valueInput = document.createElement("input");
  valueInput.type = "text";
  valueInput.id = `pref-${field.key}`;
  valueInput.className = "color-value-input";
  valueInput.placeholder =
    colorFormat(field) === "android_int" ? "Android color int (e.g. -256)" : "#RRGGBB";
  if (current !== undefined && current !== null && current !== "") {
    valueInput.value = String(current);
  } else {
    const defaultValue = defaultFieldValue(field);
    if (defaultValue !== null) valueInput.value = String(defaultValue);
  }

  const syncFromPicker = () => {
    const stored = storedColorValue(field, picker.value);
    valueInput.value = stored ?? "";
    onChange(stored);
  };

  const syncFromText = () => {
    const raw = valueInput.value.trim();
    if (raw === "") {
      onChange(null);
      return;
    }
    if (colorFormat(field) === "android_int") {
      if (!/^-?\d+$/.test(raw)) return;
      picker.value = androidColorToHex(raw);
      onChange(raw);
      return;
    }
    const hex = normalizeHexColor(raw);
    if (!hex) return;
    picker.value = hex;
    onChange(hex);
  };

  picker.addEventListener("input", syncFromPicker);
  valueInput.addEventListener("change", syncFromText);
  valueInput.addEventListener("input", () => {
    if (valueInput.value.trim() === "") onChange(null);
  });

  row.appendChild(picker);
  row.appendChild(valueInput);
  wrapper.appendChild(row);
  return wrapper;
}

function isHexColorValue(value) {
  return /^#[0-9a-fA-F]{6}$/.test(String(value ?? ""));
}

function paletteColorOptions(field) {
  return (field.options || []).filter((option) => isHexColorValue(option.value));
}

function otherSelectOptions(field) {
  return (field.options || []).filter((option) => !isHexColorValue(option.value));
}

function isPaletteColorField(field) {
  return field.input === "palette_color";
}

function renderPaletteColorField(field, current, onChange) {
  const wrapper = document.createElement("div");
  wrapper.className = "field palette-color-field";
  wrapper.appendChild(createLabel(field.title || field.key, `pref-${field.key}`));
  appendFieldDescription(wrapper, field);

  const row = document.createElement("div");
  row.className = "palette-color-row";

  const unset = document.createElement("button");
  unset.type = "button";
  unset.className = "palette-swatch palette-swatch-unset" + (current ? "" : " selected");
  unset.textContent = UNSET_OPTION_LABEL;
  unset.addEventListener("click", () => onChange(null));
  row.appendChild(unset);

  for (const option of paletteColorOptions(field)) {
    const swatch = document.createElement("button");
    swatch.type = "button";
    swatch.className = "palette-swatch";
    swatch.style.backgroundColor = option.value;
    swatch.title = option.label && option.label !== option.value ? option.label : option.value;
    swatch.setAttribute("aria-label", swatch.title);
    if (String(current ?? "").toLowerCase() === String(option.value).toLowerCase()) {
      swatch.classList.add("selected");
    }
    swatch.addEventListener("click", () => onChange(option.value));
    row.appendChild(swatch);
  }

  for (const option of otherSelectOptions(field)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "palette-option-btn" + (String(current) === String(option.value) ? " selected" : "");
    button.textContent = option.label || option.value;
    button.addEventListener("click", () => onChange(option.value));
    row.appendChild(button);
  }

  wrapper.appendChild(row);
  return wrapper;
}

function isDropdownField(field) {
  if (field.input === "palette_color") {
    return false;
  }
  if (
    field.input === "tristate" ||
    field.type === "select" ||
    (field.type === "boolean" && field.input === "select")
  ) {
    return true;
  }
  return Array.isArray(field.options) && field.options.length >= 2;
}

function renderPreferenceField(field) {
  const current = state.preferences[field.key]?.value;

  if (field.input === "gps_icon_color_mode") {
    return renderSelectField(field, getGpsIconColorMode(), (value) => {
      setGpsIconColorMode(value === "" ? null : value);
      renderPanel();
    });
  }

  if (isPaletteColorField(field)) {
    return renderPaletteColorField(field, current, (value) => setPreferenceFromField(field, value));
  }

  if (isColorField(field)) {
    return renderColorField(field, current, (value) => setPreferenceFromField(field, value));
  }

  if (isDropdownField(field)) {
    return renderSelectField(field, current, (value) => setPreferenceFromField(field, value));
  }

  if (field.type === "multiselect") {
    const wrapper = document.createElement("div");
    wrapper.className = "field";
    wrapper.appendChild(createLabel(field.title || field.key));
    appendFieldDescription(wrapper, field);
    wrapper.appendChild(
      createMultiSelect(field, current, (values) => setPreferenceFromField(field, values))
    );
    return wrapper;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "field";
  wrapper.appendChild(createLabel(field.title || field.key, `pref-${field.key}`));
  appendFieldDescription(wrapper, field);

  const input = document.createElement("input");
  input.id = `pref-${field.key}`;
  if (field.type === "integer" || field.type === "float") {
    input.type = "number";
    if (field.type === "float") input.step = "any";
  } else {
    input.type = "text";
  }
  if (current !== undefined && current !== null) input.value = current;
  else {
    const defaultValue = defaultFieldValue(field);
    if (defaultValue !== null) input.value = defaultValue;
  }
  input.placeholder = fieldPlaceholder(field);
  input.addEventListener("input", () => {
    const raw = input.value;
    if (raw === "") {
      setPreferenceFromField(field, null);
      return;
    }
    if (field.type === "integer" || field.type === "float") {
      setPreferenceFromField(field, Number(raw));
      return;
    }
    setPreferenceFromField(field, raw);
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

function renderSingleConnectionGroup(groupName) {
  const group = getConnectionGroup(groupName);
  if (!group) return;

  els.panelTitle.textContent = group.title;
  els.panelDescription.textContent =
    `${group.description} Description and Connect String are required for each entry.`;
  els.form.innerHTML = "";

  const card = document.createElement("section");
  card.className = "section-card";

  const connections = state.connections[groupName] || [];
  const list = document.createElement("div");
  if (!connections.length) {
    list.appendChild(
      Object.assign(document.createElement("div"), {
        className: "empty-state",
        textContent: "No connections configured yet.",
      })
    );
  } else {
    connections.forEach((conn, index) => list.appendChild(renderConnectionCard(groupName, conn, index)));
  }
  card.appendChild(list);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "btn btn-secondary";
  addBtn.textContent = "Add Connection";
  addBtn.addEventListener("click", () => {
    state.connections[groupName].push(defaultConnection());
    renderSingleConnectionGroup(groupName);
  });
  card.appendChild(addBtn);
  els.form.appendChild(card);
}

function listCustomPreferenceKeys() {
  return Object.keys(state.preferences)
    .filter((key) => !state.schemaFieldKeys.has(key))
    .sort();
}

function normalizeCustomValue(type, raw) {
  if (raw === null || raw === undefined || raw === "") return null;
  if (type === "boolean") return raw === true || raw === "true";
  if (type === "integer") return Number.parseInt(String(raw), 10);
  if (type === "float") return Number.parseFloat(String(raw));
  return String(raw);
}

function setCustomPreference(key, type, value) {
  const normalized = normalizeCustomValue(type, value);
  if (normalized === null || normalized === "" || Number.isNaN(normalized)) {
    delete state.preferences[key];
    return;
  }
  state.preferences[key] = {
    type,
    value: normalized,
    java_class: JAVA_CLASSES[type] || JAVA_CLASSES.string,
  };
}

function prependSearchFilterBanner(container, { lower, matchCount = null, label = "settings" } = {}) {
  if (!lower) return;
  const banner = document.createElement("div");
  banner.className = "search-filter-banner";
  const countText =
    matchCount === null ? "" : ` (${matchCount} matching ${label}${matchCount === 1 ? "" : "s"})`;
  banner.textContent = `Filtering for “${lower}”${countText}`;
  container.prepend(banner);
}

function renderCustomPreferencesPanel() {
  els.panelTitle.textContent = "Custom ATAK Preferences";
  els.panelDescription.textContent =
    "Add ATAK Shared Preferences not covered by the schema. Use this for plugin settings (including NWSharedPreferences Scope/Key/Value pairs). Unset values are omitted from export.";
  els.form.innerHTML = "";

  const lower = getActiveSearchFilter().toLowerCase();
  const customMatch = customPreferencesMatchesSearch(lower);
  if (lower) {
    prependSearchFilterBanner(els.form, {
      lower,
      matchCount: customMatch.nameMatch ? null : customMatch.matchingKeys.length,
      label: "key",
    });
  }

  const addCard = document.createElement("section");
  addCard.className = "section-card";
  addCard.appendChild(Object.assign(document.createElement("h3"), { textContent: "Add Preference" }));

  const grid = document.createElement("div");
  grid.className = "field-grid";

  const keyInput = document.createElement("input");
  keyInput.type = "text";
  keyInput.placeholder = "preference_key";
  grid.appendChild(wrapField(createLabel("Key"), keyInput));

  const typeSelect = createSelect(CUSTOM_PREF_TYPES, "string", () => {}, false);
  grid.appendChild(wrapField(createLabel("Type"), typeSelect));

  const valueInput = document.createElement("input");
  valueInput.type = "text";
  valueInput.placeholder = "Value";
  grid.appendChild(wrapField(createLabel("Value"), valueInput));

  addCard.appendChild(grid);

  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.className = "btn btn-secondary";
  addBtn.textContent = "Add Preference";
  addBtn.addEventListener("click", () => {
    const key = keyInput.value.trim();
    if (!key) {
      showToast("Preference key is required", true);
      return;
    }
    if (state.schemaFieldKeys.has(key)) {
      showToast("Key is already defined in ATAK Settings — use that category instead", true);
      return;
    }
    setCustomPreference(key, typeSelect.value, valueInput.value);
    renderCustomPreferencesPanel();
  });
  addCard.appendChild(addBtn);
  els.form.appendChild(addCard);

  const listCard = document.createElement("section");
  listCard.className = "section-card";
  listCard.appendChild(Object.assign(document.createElement("h3"), { textContent: "Custom Preferences" }));

  const keys = listCustomPreferenceKeys().filter(
    (key) => !lower || customMatch.nameMatch || key.toLowerCase().includes(lower)
  );
  if (!keys.length) {
    listCard.appendChild(
      Object.assign(document.createElement("div"), {
        className: "empty-state",
        textContent: lower ? "No custom preferences match this search." : "No custom preferences yet.",
      })
    );
  } else {
    for (const key of keys) {
      const row = renderCustomPreferenceRow(key);
      if (lower && key.toLowerCase().includes(lower)) row.classList.add("search-match");
      listCard.appendChild(row);
    }
  }
  els.form.appendChild(listCard);
}

function wrapField(label, control) {
  const wrapper = document.createElement("div");
  wrapper.className = "field";
  wrapper.appendChild(label);
  wrapper.appendChild(control);
  return wrapper;
}

function renderCustomPreferenceRow(key) {
  const pref = state.preferences[key] || { type: "string", value: "" };
  const row = document.createElement("div");
  row.className = "connection-card";

  const header = document.createElement("div");
  header.className = "connection-header";
  header.appendChild(Object.assign(document.createElement("h4"), { textContent: key }));
  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-danger";
  removeBtn.textContent = "Remove";
  removeBtn.addEventListener("click", () => {
    delete state.preferences[key];
    renderCustomPreferencesPanel();
  });
  header.appendChild(removeBtn);
  row.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "field-grid";

  const typeSelect = createSelect(
    CUSTOM_PREF_TYPES,
    pref.type || "string",
    (value) => setCustomPreference(key, value, pref.value),
    false
  );
  grid.appendChild(wrapField(createLabel("Type"), typeSelect));

  const valueInput = document.createElement("input");
  valueInput.type = pref.type === "integer" || pref.type === "float" ? "number" : "text";
  if (pref.type === "float") valueInput.step = "any";
  if (pref.type === "boolean") {
    valueInput.type = "text";
    valueInput.placeholder = "true or false";
  }
  valueInput.value = pref.value ?? "";
  valueInput.addEventListener("input", () => setCustomPreference(key, typeSelect.value, valueInput.value));
  typeSelect.addEventListener("change", () => {
    setCustomPreference(key, typeSelect.value, valueInput.value);
    renderCustomPreferencesPanel();
  });
  grid.appendChild(wrapField(createLabel("Value"), valueInput));
  row.appendChild(grid);
  return row;
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
    renderSingleConnectionGroup(groupName);
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
    wrapper.appendChild(createLabel(field.title, null, field.required));
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
      renderSingleConnectionGroup(groupName);
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
  wrapper.appendChild(createLabel(field.title, null, field.required));
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

function validateConnectionsClient() {
  const labels = {
    cot_inputs: "CoT Input",
    cot_outputs: "CoT Output",
    cot_streams: "CoT Stream",
  };
  const errors = [];
  for (const group of COT_PANELS) {
    for (let index = 0; index < (state.connections[group] || []).length; index += 1) {
      const conn = state.connections[group][index];
      const name = conn.description || conn.connectString || `#${index + 1}`;
      if (!String(conn.description || "").trim()) {
        errors.push(`${labels[group]} (${name}): Description is required`);
      }
      if (!String(conn.connectString || "").trim()) {
        errors.push(`${labels[group]} (${name}): Connect string is required`);
      }
    }
  }
  return errors;
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
    const validationErrors = validateConnectionsClient();
    if (validationErrors.length) {
      throw new Error(validationErrors.join("; "));
    }
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
    const validationErrors = validateConnectionsClient();
    if (validationErrors.length) {
      throw new Error(validationErrors.join("; "));
    }
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
