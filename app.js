  document.addEventListener("DOMContentLoaded", () => {
  const demoGroupSelect = document.getElementById("demoGroupSelect");
  const demoAction = document.getElementById("demoAction");
  const demoRuleSelect = document.getElementById("demoRuleSelect");
  const demoValueSelect = document.getElementById("demoValueSelect");
  const valueFieldContainer = document.getElementById("valueFieldContainer");
  const expressionDrawer = document.getElementById("expressionDrawer");
  const expressionInput = document.getElementById("expressionInput");
  const expressionValidateBtn = document.getElementById("expressionValidateBtn");
  const employeeRecordDrawer = document.getElementById("employeeRecordDrawer");
  const employeeRecordHint = document.getElementById("employeeRecordHint");
  const employeeRecordFields = document.getElementById("employeeRecordFields");
  const employeeRecordClearBtn = document.getElementById("employeeRecordClearBtn");
  const demoProposeBtn = document.getElementById("demoProposeBtn");
  const demoApplyBtn = document.getElementById("demoApplyBtn");
  const demoStatus = document.getElementById("demoStatus");
  const demoSummaryBody = document.getElementById("demoSummaryBody");
  const demoResult = document.getElementById("demoProposeResult");
  const demoPreviewCards = document.getElementById("demoPreviewCards");
  const runPromptBtn = document.getElementById("runPromptBtn");
  const dlcPromptInput = document.getElementById("dlcPromptInput");
  const promptStatus = document.getElementById("promptStatus");
  const currentUserEl = document.getElementById("currentUser");
  const currentUserNameEl = currentUserEl ? currentUserEl.querySelector(".meta-user__name") : null;
  const logoutBtn = document.getElementById("logoutBtn");
  const toggleAuditBtn = document.getElementById("toggleAuditBtn");
  const toggleLogsBtn = document.getElementById("toggleLogsBtn");
  const demoClearBtn = document.getElementById("demoClearBtn");
  const hideLogsBtn = document.getElementById("hideLogsBtn");
  const hideAuditBtn = document.getElementById("hideAuditBtn");
  const logPanel = document.getElementById("logPanel");
  const auditPanel = document.getElementById("auditPanel");
  const logContent = document.getElementById("logContent");
  const auditContent = document.getElementById("auditContent");
  let promptSpinnerInterval = null;

  let RULE_LABELS = {};
  let RULE_METADATA = {};
  const POLICY_NOTES_BY_RULE = {
    user: "Upserts that specific person into the group. If their membership row already exists, it just refreshes the stored details; otherwise it creates the row so the user is now in the group.",
    manager: "Rebuilds the manager-based row. All direct reports of the selected manager get a membership row (added if missing, refreshed if present); non-reporting employees are untouched.",
    tree: "Makes sure the group has a row that covers everyone in the chosen org unit. Any employee assigned to that unit gains or keeps a membership entry tied to this rule.",
    location: "Guarantees the group contains a row that enrolls everyone stationed at the selected location. Matching employees are added or refreshed under that location rule.",
    role: "Ensures the group includes all employees with the chosen job title, creating or updating the membership row that tracks that title.",
    "employment-type": "Adds or refreshes the rule row for the specified employment type (for example, all contractors), so everyone with that status appears in the group.",
    "directory-group": "Upserts the link to another directory group. Anyone belonging to the referenced directory group gets a membership row here, but the source group itself is unchanged.",
    "tenure-window": "Re-applies the hire-duration filter. Employees whose tenure falls within the window receive or refresh a membership row under that rule.",
    tag: "Adds or updates the row for the selected tag, placing every tagged employee on the group roster.",
    "saved-filter": "Runs the saved filter and ensures each matching employee now has an entry in the group tied to that filter rule.",
    "employee-record": "Keeps the user’s membership but applies the drawer’s edits to their stored employee fields (set/unset values) within the group context."
  };

  const API_BASE = (() => {
    if (typeof window === "undefined") {
      return "";
    }
    if (window.DL_API_BASE) {
      return window.DL_API_BASE;
    }
    if (window.location.protocol === "file:") {
      return "http://127.0.0.1:5000";
    }
    return "";
  })();

  let cachedEmployees = null;
  let currentDiffId = null;
  let previewDeck = [];
  let selectedPreviewId = null;
  let currentGroupMembers = [];
  let pendingSummary = null;
  let loadingGroupMembers = false;
  let membershipError = null;
  let hasGroupSelected = false;
  let employeeRecordMeta = {};

  const apiFetch = (url, options = {}) => {
    const config = { ...options };
    const headers = new Headers(options.headers || {});
    if (config.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    headers.set("X-Mode", "demo");
    config.headers = headers;
    config.credentials = "include";
    const isAbsolute = /^https?:\/\//i.test(url);
    const target = isAbsolute || !API_BASE ? url : `${API_BASE}${url}`;
    return fetch(target, config);
  };

  function setSelectOptions(selectEl, values) {
    selectEl.innerHTML = '<option value="" disabled selected>Select a value...</option>';
    values.forEach(value => {
      const opt = document.createElement("option");
      if (typeof value === "string") {
        opt.value = value;
        opt.textContent = value;
      } else {
        opt.value = value.value;
        opt.textContent = value.label;
      }
      selectEl.appendChild(opt);
    });
  }

  function resetSelectToPlaceholder(selectEl) {
    if (!selectEl || selectEl.options.length === 0) {
      return;
    }
    const option = selectEl.options[0];
    const wasDisabled = option.disabled;
    option.disabled = false;
    option.selected = true;
    selectEl.value = option.value;
    option.disabled = wasDisabled;
  }

  function applyActionOptions(options) {
    if (!demoAction) return;
    demoAction.innerHTML = "";

    if (!Array.isArray(options) || options.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No actions available";
      opt.disabled = true;
      opt.selected = true;
      demoAction.appendChild(opt);
      demoAction.disabled = true;
      return;
    }

    demoAction.disabled = false;
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select an action...";
    placeholder.disabled = true;
    placeholder.selected = true;
    demoAction.appendChild(placeholder);

    options.forEach(option => {
      const value = option && (option.value || option.id || option._id);
      const label = option && (option.label || value);
      if (!value || !label) {
        return;
      }
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      demoAction.appendChild(opt);
    });
  }

  function applyGroupOptions(options) {
    if (!demoGroupSelect) return;
    demoGroupSelect.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.disabled = true;
    placeholder.selected = true;
    placeholder.textContent = Array.isArray(options) && options.length > 0
      ? "Select a group..."
      : "No groups available";
    demoGroupSelect.appendChild(placeholder);

    if (!Array.isArray(options) || options.length === 0) {
      demoGroupSelect.disabled = true;
      return;
    }

    demoGroupSelect.disabled = false;
    options.forEach(option => {
      const value = option && (option.value || option.groupId || option.id || option._id);
      const label = option && (option.label || value);
      if (!value || !label) {
        return;
      }
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      demoGroupSelect.appendChild(opt);
    });
  }

  function applyRuleOptions(options) {
    if (!demoRuleSelect) return;
    demoRuleSelect.innerHTML = "";

    RULE_LABELS = {};
    RULE_METADATA = {};

    if (!Array.isArray(options) || options.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No rules available";
      opt.disabled = true;
      opt.selected = true;
      demoRuleSelect.appendChild(opt);
      demoRuleSelect.disabled = true;
      toggleExpressionDrawer(false);
      setSelectOptions(demoValueSelect, []);
      return;
    }

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select a rule...";
    placeholder.disabled = true;
    placeholder.selected = true;
    demoRuleSelect.appendChild(placeholder);

    demoRuleSelect.disabled = false;
    options.forEach((rule, index) => {
      const value = rule && (rule.value || rule.id || rule._id);
      const label = rule && (rule.label || value);
      if (!value || !label) {
        return;
      }
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      demoRuleSelect.appendChild(opt);

      const staticValues = Array.isArray(rule?.staticValues)
        ? rule.staticValues.map(option => {
            if (typeof option === "string") {
              return { value: option, label: option };
            }
            return {
              value: option.value ?? option.label ?? "",
              label: option.label ?? option.value ?? "",
            };
          })
        : [];

      RULE_LABELS[value] = label;
      RULE_METADATA[value] = {
        valueSource: rule?.valueSource || "static",
        staticValues,
        recordFields: Array.isArray(rule?.recordFields) ? rule.recordFields : [],
      };
    });

    populateValues(demoRuleSelect.value);
  }

  function initializeDemoOptions() {
    const actionsPromise = apiFetch("/api/demo/actions").then(res => res.json());
    const groupsPromise = apiFetch("/api/demo/groups").then(res => res.json());
    const rulesPromise = apiFetch("/api/demo/rules").then(res => res.json());

    return Promise.all([actionsPromise, groupsPromise, rulesPromise])
      .then(([actions, groups, rules]) => {
        applyActionOptions(Array.isArray(actions) ? actions : []);
        applyGroupOptions(Array.isArray(groups) ? groups : []);
        applyRuleOptions(Array.isArray(rules) ? rules : []);
      })
      .catch(err => {
        console.error("Failed to load demo options", err);
        if (demoStatus) {
          demoStatus.textContent = `Failed to load demo options: ${err.message}`;
          demoStatus.className = "demo-status demo-status--error";
        }
        throw err;
      });
  }

  function toggleExpressionDrawer(visible) {
    expressionDrawer.classList.toggle("hidden", !visible);
    valueFieldContainer.classList.toggle("hidden", visible);
    demoValueSelect.disabled = visible;
    if (visible) {
      demoValueSelect.value = "";
    }
  }

  function toggleEmployeeRecordDrawer(visible) {
    if (!employeeRecordDrawer) {
      return;
    }
    employeeRecordDrawer.classList.toggle("hidden", !visible);
    if (demoClearBtn) {
      demoClearBtn.disabled = visible;
    }
    if (employeeRecordClearBtn) {
      employeeRecordClearBtn.disabled = !visible;
    }
    if (!visible) {
      employeeRecordDrawer.classList.remove("employee-record-drawer--remove");
      if (employeeRecordHint) {
        employeeRecordHint.textContent = "Update the employee record fields below.";
      }
      if (employeeRecordFields) {
        employeeRecordFields.innerHTML = "";
      }
    }
  }

  function renderEmployeeRecordEditor(action) {
    if (!employeeRecordDrawer || !employeeRecordFields) {
      return;
    }

    const ruleKey = (demoRuleSelect.value || "").toLowerCase();
    const metadata = RULE_METADATA[ruleKey] || {};
    const fields = Array.isArray(metadata.recordFields) ? metadata.recordFields : [];
    employeeRecordMeta = metadata;

    const normalizedAction = (action || "").toLowerCase();
    employeeRecordDrawer.classList.toggle("employee-record-drawer--remove", normalizedAction === "remove");

    employeeRecordFields.innerHTML = "";

    if (employeeRecordClearBtn) {
      employeeRecordClearBtn.disabled = !fields.length;
    }

    if (!fields.length) {
      const empty = document.createElement("p");
      empty.className = "employee-record-empty";
      empty.textContent = "No editable fields are available for this rule.";
      employeeRecordFields.appendChild(empty);
      return;
    }

    if (normalizedAction === "remove") {
      if (employeeRecordHint) {
        employeeRecordHint.textContent = "Select the record fields you want to clear.";
      }
      fields.forEach(field => {
        const wrapper = document.createElement("label");
        wrapper.className = "employee-record-option";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.dataset.fieldName = field.name;
        checkbox.addEventListener("change", updateSummary);
        wrapper.appendChild(checkbox);
        const text = document.createElement("span");
        text.textContent = field.label;
        wrapper.appendChild(text);
        employeeRecordFields.appendChild(wrapper);
      });
      return;
    }

    if (employeeRecordHint) {
      employeeRecordHint.textContent = "Provide new values for the selected employee record fields.";
    }

    fields.forEach(field => {
      const wrapper = document.createElement("div");
      wrapper.className = "employee-record-field";

      const label = document.createElement("label");
      label.textContent = field.label;
      label.setAttribute("for", `employee-record-${field.name}`);
      wrapper.appendChild(label);

      const fieldType = (field.type || "").toLowerCase();
      if (fieldType === "select" || Array.isArray(field.options)) {
        const select = document.createElement("select");
        select.id = `employee-record-${field.name}`;
        select.dataset.fieldName = field.name;

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.disabled = true;
        placeholder.selected = true;
        placeholder.textContent = `Select ${field.label.toLowerCase()}...`;
        select.appendChild(placeholder);

        (field.options || []).forEach(option => {
          const opt = document.createElement("option");
         const rawValue = Object.prototype.hasOwnProperty.call(option, "value") ? option.value : option.label;
          const serialized = typeof rawValue === "string" ? rawValue : JSON.stringify(rawValue);
          opt.value = serialized;
          opt.dataset.rawValue = serialized;
          opt.textContent = option.label ?? option.value ?? "";
          select.appendChild(opt);
        });

        select.addEventListener("change", updateSummary);
        wrapper.appendChild(select);
      } else {
        const input = document.createElement("input");
        input.id = `employee-record-${field.name}`;
        input.dataset.fieldName = field.name;
        if (fieldType === "number") {
          input.type = "number";
          input.placeholder = "Enter a number";
        } else {
          input.type = "text";
          input.placeholder = "Enter a value";
        }
        input.addEventListener("input", updateSummary);
        wrapper.appendChild(input);
      }

      employeeRecordFields.appendChild(wrapper);
    });
  }

  function getPolicyNotesForRule(ruleType) {
    const note = POLICY_NOTES_BY_RULE[(ruleType || "").toLowerCase()];
    return note ? [note] : [];
  }

  function clearEmployeeRecordInputs() {
    if (!employeeRecordFields) {
      return;
    }
    const inputs = Array.from(employeeRecordFields.querySelectorAll("[data-field-name]"));
    inputs.forEach(input => {
      if (input.type === "checkbox") {
        input.checked = false;
      } else if (input.tagName === "SELECT") {
        input.selectedIndex = 0;
      } else {
        input.value = "";
      }
    });
    updateSummary();
    if (employeeRecordClearBtn) {
      employeeRecordClearBtn.disabled = true;
    }
  }

  function collectEmployeeRecordChanges(action) {
    if (!employeeRecordFields) {
      return { set: {}, unset: [] };
    }
    const normalizedAction = (action || "").toLowerCase();
    if (normalizedAction === "remove") {
      const unset = Array.from(employeeRecordFields.querySelectorAll('input[type="checkbox"][data-field-name]:checked'))
        .map(input => input.dataset.fieldName)
        .filter(Boolean);
      return { set: {}, unset };
    }

    const inputs = Array.from(employeeRecordFields.querySelectorAll("[data-field-name]"));
    const set = {};
    inputs.forEach(input => {
      const fieldName = input.dataset.fieldName;
      if (!fieldName) {
        return;
      }
     if (input.tagName === "SELECT") {
       const selectedOption = input.options[input.selectedIndex];
       if (!selectedOption || selectedOption.value === "") {
         return;
       }
       const raw = selectedOption.dataset.rawValue;
       try {
          set[fieldName] = raw ? JSON.parse(raw) : selectedOption.value;
        } catch (err) {
          set[fieldName] = selectedOption.value;
        }
        return;
      }
      if (typeof input.value === "string" && input.value.trim()) {
        set[fieldName] = input.value.trim();
      }
    });
    return { set, unset: [] };
  }

  function getEmployeeRecordChangeCounts(action) {
    if (!employeeRecordFields) {
      return { set: 0, unset: 0 };
    }
    const normalizedAction = (action || "").toLowerCase();
    if (normalizedAction === "remove") {
      const count = employeeRecordFields.querySelectorAll('input[type="checkbox"][data-field-name]:checked').length;
      return { set: 0, unset: count };
    }
    const inputs = Array.from(employeeRecordFields.querySelectorAll("[data-field-name]"));
    let setCount = 0;
    inputs.forEach(input => {
      if (input.tagName === "SELECT") {
        const option = input.options[input.selectedIndex];
        if (option && option.value !== "") {
          setCount += 1;
        }
      } else if (typeof input.value === "string" && input.value.trim()) {
        setCount += 1;
      }
    });
    return { set: setCount, unset: 0 };
  }
  function setPromptStatus(message, type = "info") {
    if (!promptStatus) {
      return;
    }

    promptStatus.className = "demo-prompt__status";
    if (type === "error") {
      promptStatus.classList.add("demo-prompt__status--error");
    } else if (type === "success") {
      promptStatus.classList.add("demo-prompt__status--success");
    }
    promptStatus.textContent = message;
  }

  function startPromptSpinner() {
    if (!promptStatus) {
      return;
    }
    setPromptStatus("", "info");
    promptStatus.classList.add("demo-prompt__spinner");

    const frames = ["/", "|", "\\", "-"];
    let frameIndex = 0;

    if (promptSpinnerInterval) {
      clearInterval(promptSpinnerInterval);
    }
    promptStatus.textContent = frames[frameIndex];
    promptSpinnerInterval = setInterval(() => {
      frameIndex = (frameIndex + 1) % frames.length;
      promptStatus.textContent = frames[frameIndex];
    }, 150);
  }

  function stopPromptSpinner(message = "", type = "info") {
    if (!promptStatus) {
      return;
    }
    promptStatus.classList.remove("demo-prompt__spinner");
    if (promptSpinnerInterval) {
      clearInterval(promptSpinnerInterval);
      promptSpinnerInterval = null;
    }
    setPromptStatus(message, type);
  }

  function highlightExpressionDrawer(enabled) {
    if (!expressionDrawer) {
      return;
    }
    expressionDrawer.classList.toggle("expression-drawer--highlight", enabled);
  }

  function handleRunPrompt() {
    const prompt = (dlcPromptInput?.value || "").trim();
    if (!prompt) {
      highlightExpressionDrawer(false);
      setPromptStatus("Enter a prompt before running.", "error");
      return;
    }

    startPromptSpinner();
    highlightExpressionDrawer(true);
    demoRuleSelect.value = "expression";
    populateValues("expression");

    setTimeout(() => {
      highlightExpressionDrawer(false);
      stopPromptSpinner("Prompt ready. Review the expression, then propose.", "success");
    }, 800);
  }

  function populateValues(ruleKey) {
    const normalizedKey = (ruleKey || "").toLowerCase();
    const metadata = RULE_METADATA[ruleKey];
    if (!metadata) {
      toggleExpressionDrawer(false);
      toggleEmployeeRecordDrawer(false);
      setSelectOptions(demoValueSelect, []);
      if (employeeRecordClearBtn) {
        employeeRecordClearBtn.disabled = true;
      }
      updateSummary();
      return;
    }
    const source = (metadata.valueSource || "static").toLowerCase();
    const isEmployeeRecord = normalizedKey === "employee-record" || source === "employee-record";

    if (source === "expression") {
      toggleExpressionDrawer(true);
      toggleEmployeeRecordDrawer(false);
      updateSummary();
      return;
    }

    toggleExpressionDrawer(false);

    if (isEmployeeRecord) {
      toggleEmployeeRecordDrawer(true);
    } else {
      toggleEmployeeRecordDrawer(false);
      if (employeeRecordClearBtn) {
        employeeRecordClearBtn.disabled = true;
      }
    }

    if (source === "employees" || isEmployeeRecord) {
      if (cachedEmployees) {
        setSelectOptions(
          demoValueSelect,
          cachedEmployees.map(emp => ({ value: emp.name, label: emp.name }))
        );
        if (isEmployeeRecord) {
          renderEmployeeRecordEditor(demoAction.value);
        }
        updateSummary();
        return;
      }

      apiFetch("/api/employees")
        .then(res => res.json())
        .then(values => {
          cachedEmployees = Array.isArray(values) ? values : [];
          setSelectOptions(
            demoValueSelect,
            cachedEmployees.map(emp => ({ value: emp.name, label: emp.name }))
          );
          if (isEmployeeRecord) {
            renderEmployeeRecordEditor(demoAction.value);
          }
        })
        .catch(err => console.error("Failed to load users", err))
        .finally(updateSummary);
      return;
    }

    const staticValues = Array.isArray(metadata.staticValues)
      ? metadata.staticValues.map(option => {
          if (typeof option === "string") {
            return { value: option, label: option };
          }
          return {
            value: option.value ?? option.label ?? "",
            label: option.label ?? option.value ?? "",
          };
        })
      : [];

    setSelectOptions(demoValueSelect, staticValues);
    if (isEmployeeRecord) {
      renderEmployeeRecordEditor(demoAction.value);
    }
    updateSummary();
  }

  function renderAudit(entries) {
    if (!auditContent) {
      return;
    }

    if (!Array.isArray(entries) || entries.length === 0) {
      auditContent.innerHTML = '<p class="status-empty">No audit entries yet.</p>';
      return;
    }

    const markup = entries.map(entry => {
      const timestamp = entry.ts ? new Date(entry.ts).toLocaleString() : '-';
      const actor = entry.actor || 'system';
      const operation = (entry.op || '-').toUpperCase();
      const status = (entry.status || '-').toString().toUpperCase();
      const group = entry.groupName || entry.groupId || '(unknown group)';
      const rule = entry.rule || {};
      const ruleLabel = rule.label || rule.type || 'Rule';
      const ruleValue = rule.expression || rule.value || '(none)';
      const summary = entry.summary || {};
      const after = summary.after || {};
      const before = summary.before || {};
      const matchCount = entry.matchCount ?? after.count ?? 0;
      const matchNames = (entry.matchNames && entry.matchNames.length ? entry.matchNames : after.names || []).slice(0, 5);
      const affectedNames = matchNames.join(', ');
      const affectedLine = matchCount
        ? `${matchCount} member${matchCount === 1 ? '' : 's'}${affectedNames ? ` (${affectedNames})` : ''}`
        : 'No members affected.';
      const beforeNames = (before.names || []).slice(0, 5).join(', ');
      const beforeLine = before.count
        ? `${before.count} previously${beforeNames ? ` (${beforeNames})` : ''}`
        : 'No previous memberships.';
      const beforeRules = (before.rules || []).join('; ');
      const afterRules = (after.rules || []).join('; ') || ruleValue;
      const policyNotes = Array.isArray(entry.policyNotes) && entry.policyNotes.length
        ? `<ul class="audit-entry__notes">${entry.policyNotes.map(note => `<li>${note}</li>`).join('')}</ul>`
        : '';

      const isRecordChange = (rule.type || "").toLowerCase() === "employee-record";
      const employeeRecord = entry.employeeRecord || {};
      const recordFields = Array.isArray(employeeRecord.changes) ? employeeRecord.changes : [];
      const recordList = recordFields.length
        ? `<ul class="audit-entry__record-fields">${recordFields.map(field => {
            const beforeDisplay = field.beforeDisplay ?? field.before ?? "(empty)";
            const afterDisplay = field.afterDisplay ?? field.after ?? "(empty)";
            return `<li>${field.label}: ${beforeDisplay} → ${afterDisplay}</li>`;
          }).join("")}</ul>`
        : "<p class=\"audit-entry__summary\">No field changes recorded.</p>";

      const bodyMarkup = isRecordChange
        ? `
            <p class="audit-entry__group">${group}</p>
            <p class="audit-entry__rule"><strong>${ruleLabel}:</strong> ${employeeRecord.userDisplayName || employeeRecord.userEmail || ruleValue}</p>
            ${recordList}
            ${policyNotes}
          `
        : `
            <p class="audit-entry__group">${group}</p>
            <p class="audit-entry__rule"><strong>${ruleLabel}:</strong> ${ruleValue}</p>
            ${beforeRules ? `<p class="audit-entry__rule audit-entry__rule--before"><strong>Previously:</strong> ${beforeRules}</p>` : ''}
            ${afterRules ? `<p class="audit-entry__rule audit-entry__rule--after"><strong>Result:</strong> ${afterRules}</p>` : ''}
            <p class="audit-entry__summary"><strong>Affected:</strong> ${affectedLine}</p>
            <p class="audit-entry__summary"><strong>Prior:</strong> ${beforeLine}</p>
            ${policyNotes}
          `;

      return `
        <article class="audit-entry">
          <header class="audit-entry__meta">
            <div class="audit-entry__meta-left">
              <span class="audit-entry__actor">${actor}</span>
              <span class="audit-entry__operation">${operation}</span>
            </div>
            <div class="audit-entry__timestamp">
              <span>${timestamp}</span>
              <span class="audit-entry__status">${status}</span>
            </div>
          </header>
          <div class="audit-entry__body">
            ${bodyMarkup}
          </div>
        </article>
      `;
    }).join("");

    auditContent.innerHTML = markup;
  }
  function loadAudit() {
    apiFetch("/api/audit")
      .then(res => res.json())
      .then(renderAudit)
      .catch(err => {
        console.error("Failed to load audit log", err);
        if (auditContent) {
          auditContent.innerHTML = '<p class="status-empty">Failed to load audit log.</p>';
        }
      });
  }
  function loadLogs() {
    apiFetch("/api/logs")
      .then(res => res.text())
      .then(text => {
        logContent.textContent = text || "(empty)";
        logContent.scrollTop = logContent.scrollHeight;
      })
      .catch(err => {
        logContent.textContent = `Failed to load logs: ${err.message}`;
      });
  }

  function handleClearSelections() {
    if (demoGroupSelect) {
      resetSelectToPlaceholder(demoGroupSelect);
    }
    if (demoAction) {
      resetSelectToPlaceholder(demoAction);
    }
    if (demoRuleSelect) {
      resetSelectToPlaceholder(demoRuleSelect);
    }
    const normalizedRule = (demoRuleSelect?.value || "").toLowerCase();
    if (normalizedRule === "expression") {
      if (expressionInput) {
        expressionInput.value = "";
      }
      toggleEmployeeRecordDrawer(false);
    } else {
      if (demoValueSelect) {
        resetSelectToPlaceholder(demoValueSelect);
      }
      if (normalizedRule === "employee-record") {
        toggleEmployeeRecordDrawer(true);
        clearEmployeeRecordInputs();
      } else {
        toggleEmployeeRecordDrawer(false);
      }
    }
    if (demoRuleSelect) {
      populateValues(demoRuleSelect.value);
    }
    pendingSummary = null;
    if (demoGroupSelect) {
      demoGroupSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (demoStatus) {
      demoStatus.textContent = "Selections cleared.";
      demoStatus.className = "demo-status demo-status--info";
    }
    if (demoApplyBtn) {
      demoApplyBtn.disabled = !selectedPreviewId;
    }
    if (demoClearBtn) {
      demoClearBtn.disabled = false;
    }
  }

  function loadCurrentUser() {
    if (!currentUserEl) {
      return;
    }

    apiFetch("/api/me")
      .then(res => {
        if (res.status === 401) {
          window.location.href = "/login";
          return null;
        }
        return res.json();
      })
      .then(data => {
        if (!data || !data.authenticated) {
          return;
        }
        if (currentUserNameEl && data.user) {
          currentUserNameEl.textContent = data.user;
        }
        currentUserEl.classList.add("meta-user--visible");
      })
      .catch(() => {
        currentUserEl.classList.remove("meta-user--visible");
      });
  }
  function formatMembershipValue(member) {
    if (!member) {
      return "-";
    }
    const ruleType = (member.ruleType || "").toString().toLowerCase();
    const baseLabel = member.valueLabel || "-";
    if (ruleType === "user" || member.isRecentRecordEvent || member.suppressUserValue) {
      return baseLabel;
    }
    const associatedUser = member.userDisplayName || member.userId || "";
    if (!associatedUser) {
      return baseLabel;
    }
    if (!baseLabel || baseLabel === "-") {
      return associatedUser;
    }
    return `${baseLabel} : ${associatedUser}`;
  }

  function renderGroupStatus() {
    if (!demoSummaryBody) return;
    demoSummaryBody.innerHTML = "";

    if (!hasGroupSelected) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="3" class="status-empty">Select a group to see membership details.</td>';
      demoSummaryBody.appendChild(row);
      return;
    }

    if (loadingGroupMembers) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="3" class="status-empty">Loading membership...</td>';
      demoSummaryBody.appendChild(row);
      return;
    }

    if (membershipError) {
      const row = document.createElement("tr");
      row.innerHTML = `<td colspan="3" class="status-empty">${membershipError}</td>`;
      demoSummaryBody.appendChild(row);
      return;
    }

    let rowsRendered = 0;

    if (Array.isArray(currentGroupMembers) && currentGroupMembers.length > 0) {
      currentGroupMembers.forEach(member => {
        const actionText = member.statusLabel || "Included";
        const ruleLabel = member.ruleLabel || "-";
        const valueLabel = formatMembershipValue(member);
        const badgeClass = member.badgeClass || "group-status__tag--current";
        const rowClasses = [];
        if (Array.isArray(member.rowClasses)) {
          member.rowClasses.forEach(cls => {
            if (cls) {
              rowClasses.push(cls);
            }
          });
        }
        if (typeof member.rowClass === "string" && member.rowClass) {
          rowClasses.push(member.rowClass);
        }
        const tr = document.createElement("tr");
        tr.classList.add("group-status__row", ...rowClasses);
        tr.innerHTML = `
          <td class="group-status__cell"><span class="group-status__tag ${badgeClass}">${actionText}</span></td>
          <td class="group-status__cell">${ruleLabel}</td>
          <td class="group-status__cell">${valueLabel}</td>
        `;
        demoSummaryBody.appendChild(tr);
        rowsRendered += 1;
      });
    }

    const selectedGroupValue = demoGroupSelect.value;
    const selectedGroupLabel = getSelectLabel(demoGroupSelect);

    const matchingPreviews = previewDeck.filter(card => {
      const cardValue = card.groupId || card.groupName;
      const cardName = card.groupName;
      return (
        (selectedGroupValue && (cardValue === selectedGroupValue || cardName === selectedGroupValue)) ||
        (selectedGroupLabel && cardName === selectedGroupLabel)
      );
    });

    matchingPreviews.forEach(card => {
      const pendingValue = card.summary.valueLabel || "(not selected)";
      const tr = document.createElement("tr");
      tr.classList.add("group-status__row", "group-status__pending");
      tr.innerHTML = `
        <td class="group-status__cell"><span class="group-status__tag group-status__tag--pending">${card.summary.action}</span></td>
        <td class="group-status__cell">${card.summary.ruleLabel}</td>
        <td class="group-status__cell">${pendingValue}</td>
      `;
      demoSummaryBody.appendChild(tr);
      rowsRendered += 1;
    });

    if (!rowsRendered) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="3" class="status-empty">No current memberships for this group.</td>';
      demoSummaryBody.appendChild(row);
    }
  }

  function loadGroupMemberships(groupValue) {
    if (!groupValue) {
      hasGroupSelected = false;
      currentGroupMembers = [];
      membershipError = null;
      loadingGroupMembers = false;
      renderGroupStatus();
      return;
    }

    hasGroupSelected = true;
    loadingGroupMembers = true;
    membershipError = null;
    renderGroupStatus();

    apiFetch(`/api/group-members?group=${encodeURIComponent(groupValue)}`)
      .then(res => {
        if (res.status === 401) {
          window.location.href = "/login";
          return null;
        }
        if (!res.ok) {
          return res.json().then(body => {
            throw new Error(body && body.error ? body.error : "Failed to load membership.");
          });
        }
        return res.json();
      })
      .then(data => {
        if (!data) {
          return;
        }
        currentGroupMembers = Array.isArray(data) ? data : [];
        membershipError = null;
      })
      .catch(err => {
        currentGroupMembers = [];
        const message = err && err.message ? err.message : "Failed to load membership.";
        membershipError = `Failed to load membership: ${message}`;
      })
      .finally(() => {
        loadingGroupMembers = false;
        renderGroupStatus();
      });
  }
  function toggleLogs() {
    if (!logPanel) {
      return;
    }

    const showing = logPanel.classList.toggle("show");
    if (toggleLogsBtn) {
      toggleLogsBtn.textContent = showing ? "Hide Logs" : "Show Logs";
    }
    if (showing) {
      loadLogs();
      if (auditPanel && auditPanel.classList.contains("show")) {
        auditPanel.classList.remove("show");
        if (toggleAuditBtn) {
          toggleAuditBtn.textContent = "Audit Trail";
        }
      }
    }
  }

  function toggleAudit() {
    if (!auditPanel) {
      return;
    }

    const showing = auditPanel.classList.toggle("show");
    if (toggleAuditBtn) {
      toggleAuditBtn.textContent = showing ? "Hide Audit" : "Audit Trail";
    }
    if (showing) {
      loadAudit();
      if (logPanel && logPanel.classList.contains("show")) {
        logPanel.classList.remove("show");
        if (toggleLogsBtn) {
          toggleLogsBtn.textContent = "Show Logs";
        }
      }
    }
  }
  function getSelectLabel(selectEl) {
    if (!selectEl) return "";
    const option = selectEl.options[selectEl.selectedIndex];
    if (!option || option.disabled) return "";
    return option.textContent.trim();
  }

  function updateSummary() {
    const groupValue = demoGroupSelect.value;
    const groupLabel = getSelectLabel(demoGroupSelect);
    hasGroupSelected = Boolean(groupLabel);

    if (!hasGroupSelected) {
      pendingSummary = null;
      renderGroupStatus();
      return;
    }

    const ruleKey = demoRuleSelect.value;
    const normalizedRule = (ruleKey || "").toLowerCase();
    const actionLabel = getSelectLabel(demoAction) || formatActionLabel(demoAction.value);
    const ruleLabel = RULE_LABELS[normalizedRule] || getSelectLabel(demoRuleSelect) || normalizedRule;
    let valueLabel;
    if (normalizedRule === "expression") {
      valueLabel = expressionInput.value.trim() || "(not set)";
    } else if (normalizedRule === "employee-record") {
      const baseLabel = getSelectLabel(demoValueSelect) || demoValueSelect.value || "(not selected)";
      const counts = getEmployeeRecordChangeCounts(demoAction.value);
      const total = (counts.set || 0) + (counts.unset || 0);
      if (employeeRecordClearBtn) {
        employeeRecordClearBtn.disabled = total === 0;
      }
      valueLabel = total > 0
        ? `${baseLabel} (${total} field${total === 1 ? "" : "s"})`
        : baseLabel;
    } else {
      valueLabel = getSelectLabel(demoValueSelect) || demoValueSelect.value || "(not selected)";
    }

    pendingSummary = {
      action: actionLabel,
      ruleLabel,
      valueLabel,
      ruleType: normalizedRule,
      groupLabel,
      groupValue
    };

    renderGroupStatus();
  }


  function formatActionLabel(action) {
    const normalized = (action || "").toString().toLowerCase();
    if (!normalized) {
      return "Action";
    }
    return normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }

  function ensureSelectedPreview() {
    if (!previewDeck.length) {
      selectedPreviewId = null;
      currentDiffId = null;
      return;
    }
    if (!selectedPreviewId || !previewDeck.some(card => card.id === selectedPreviewId)) {
      const latest = previewDeck[previewDeck.length - 1];
      selectedPreviewId = latest.id;
    }
    currentDiffId = selectedPreviewId;
  }

  function refreshPreviewDeck() {
    if (!demoPreviewCards || !demoResult) {
      return;
    }

    ensureSelectedPreview();

    demoPreviewCards.innerHTML = "";
    previewDeck.forEach(card => {
      demoPreviewCards.appendChild(buildPreviewCard(card));
    });

    const hasCards = previewDeck.length > 0;
    demoResult.classList.toggle("hidden", !hasCards);
    demoApplyBtn.disabled = !selectedPreviewId;
    demoPreviewCards.classList.toggle("demo-preview__cards--scroll", previewDeck.length >= 3);
  }

  function buildPreviewCard(card) {
    const cardEl = document.createElement("article");
    cardEl.className = "preview-card";
    if (card.id === selectedPreviewId) {
      cardEl.classList.add("preview-card--selected");
    }
    cardEl.dataset.diffId = card.id;

    cardEl.addEventListener("click", () => {
      selectPreview(card.id);
    });

    const header = document.createElement("div");
    header.className = "preview-card__header";

    const title = document.createElement("div");
    title.className = "preview-card__title";
    const groupEl = document.createElement("span");
    groupEl.className = "preview-card__group";
    groupEl.textContent = card.groupName || card.summary.groupLabel || "(group)";
    const actionEl = document.createElement("span");
    actionEl.className = "preview-card__action";
    actionEl.textContent = card.summary.action || formatActionLabel(card.action);
    title.appendChild(groupEl);
    title.appendChild(actionEl);

    const dismissBtn = document.createElement("button");
    dismissBtn.type = "button";
    dismissBtn.className = "preview-card__dismiss";
    dismissBtn.setAttribute("aria-label", "Remove proposal");
    dismissBtn.textContent = "X";
    dismissBtn.addEventListener("click", evt => {
      evt.stopPropagation();
      removePreviewCard(card.id);
    });

    header.appendChild(title);
    header.appendChild(dismissBtn);
    cardEl.appendChild(header);

    const meta = document.createElement("div");
    meta.className = "preview-card__meta";
    const ruleLabel = document.createElement("strong");
    ruleLabel.textContent = card.summary.ruleLabel;
    const valueLabel = document.createElement("span");
    valueLabel.textContent = card.summary.valueLabel;
    meta.appendChild(ruleLabel);
    meta.appendChild(valueLabel);
    cardEl.appendChild(meta);

    const recordChange = Array.isArray(card.changes)
      ? card.changes.find(change => change.changeType === "employee-record")
      : null;
    const recordFieldCount = recordChange && Array.isArray(recordChange.fields)
      ? recordChange.fields.length
      : 0;
    const matchCount = typeof card.matchCount === "number"
      ? card.matchCount
      : (recordChange ? recordFieldCount : (Array.isArray(card.changes) ? card.changes.length : 0));
    const matchesLine = document.createElement("p");
    matchesLine.className = "preview-card__matches";
    if (recordChange) {
      const user = recordChange.userDisplayName || recordChange.userEmail || card.summary.valueLabel || "(employee)";
      matchesLine.textContent = recordFieldCount
        ? `${recordFieldCount} field${recordFieldCount === 1 ? "" : "s"} for ${user}`
        : `No field changes recorded for ${user}.`;
    } else {
      matchesLine.textContent = matchCount
        ? `${matchCount} match${matchCount === 1 ? "" : "es"}`
        : "No matching members.";
    }
    cardEl.appendChild(matchesLine);

    const changeList = document.createElement("ul");
    changeList.className = "preview-card__changes";
    const maxChanges = 10;
    const changesToRender = Array.isArray(card.changes) ? card.changes.slice(0, maxChanges) : [];

    changesToRender.forEach(change => {
      if (change.changeType === "employee-record") {
        const li = document.createElement("li");
        li.className = "preview-card__record-change";
        const heading = document.createElement("div");
        heading.className = "preview-card__record-heading";
        const target = change.userDisplayName || change.userEmail || card.summary.valueLabel || "(employee)";
        heading.textContent = `${formatActionLabel(change.action || card.action)} employee record for ${target}`;
        li.appendChild(heading);

        if (Array.isArray(change.fields) && change.fields.length) {
          const fieldList = document.createElement("ul");
          fieldList.className = "preview-card__record-fields";
          change.fields.forEach(field => {
            const item = document.createElement("li");
            const beforeDisplay = field.beforeDisplay ?? field.before ?? "(empty)";
            const afterDisplay = field.afterDisplay ?? field.after ?? "(empty)";
            item.textContent = `${field.label}: ${beforeDisplay} → ${afterDisplay}`;
            fieldList.appendChild(item);
          });
          li.appendChild(fieldList);
        }

        changeList.appendChild(li);
        return;
      }
      const li = document.createElement("li");
      const action = change.action || change.op || "?";
      const rule = change.ruleLabel || RULE_LABELS[change.ruleType] || change.ruleType;
      const user = change.userDisplayName || change.userEmail || "(group)";
      const valuePart = change.ruleValueLabel ? ` - ${change.ruleValueLabel}` : "";
      li.textContent = `${action} ${user} (${rule}${valuePart})`;
      changeList.appendChild(li);
    });

    if (!recordChange && matchCount > changesToRender.length) {
      const more = document.createElement("li");
      more.textContent = `... and ${matchCount - changesToRender.length} more matches.`;
      changeList.appendChild(more);
    }

    cardEl.appendChild(changeList);

    if (Array.isArray(card.policyNotes) && card.policyNotes.length) {
      const policy = document.createElement("div");
      policy.className = "preview-card__policy";
      const titleEl = document.createElement("p");
      titleEl.className = "preview-card__policy-title";
      titleEl.textContent = "Policy Notes";
      policy.appendChild(titleEl);

      const policyList = document.createElement("ul");
      card.policyNotes.forEach(note => {
        const item = document.createElement("li");
        item.textContent = note;
        policyList.appendChild(item);
      });
      policy.appendChild(policyList);
      cardEl.appendChild(policy);
    }

    return cardEl;
  }

  function selectPreview(diffId) {
    if (!diffId) {
      return;
    }
    const card = previewDeck.find(entry => entry.id === diffId);
    if (!card) {
      return;
    }
    const alreadySelected = diffId === selectedPreviewId;
    selectedPreviewId = diffId;
    currentDiffId = diffId;

    if (demoGroupSelect && card.groupName) {
      const desiredValue = card.groupName;
      const fallbackValue = card.groupId || desiredValue;
      if (demoGroupSelect.value !== desiredValue) {
        const option = Array.from(demoGroupSelect.options || []).find(opt =>
          opt.value === desiredValue ||
          opt.textContent === desiredValue ||
          (fallbackValue && (opt.value === fallbackValue || opt.textContent === fallbackValue))
        );
        if (option) {
          demoGroupSelect.value = option.value;
          loadGroupMemberships(option.value);
        } else {
          loadGroupMemberships(fallbackValue);
        }
      } else if (!alreadySelected) {
        loadGroupMemberships(demoGroupSelect.value);
      }
    }

    demoApplyBtn.disabled = false;
    refreshPreviewDeck();
    renderGroupStatus();
  }

  function removePreviewCard(diffId) {
    if (!diffId) {
      return null;
    }
    const index = previewDeck.findIndex(card => card.id === diffId);
    if (index === -1) {
      return null;
    }
    const [removed] = previewDeck.splice(index, 1);
    if (selectedPreviewId === diffId) {
      selectedPreviewId = null;
    }
    refreshPreviewDeck();
    if (previewDeck.length && selectedPreviewId) {
      selectPreview(selectedPreviewId);
    } else {
      renderGroupStatus();
    }
    return removed;
  }

  function clearPreview(targetDiffId) {
    if (targetDiffId) {
      removePreviewCard(targetDiffId);
      return;
    }
    previewDeck = [];
    selectedPreviewId = null;
    currentDiffId = null;
    refreshPreviewDeck();
    renderGroupStatus();
  }

  function renderPreview(diff, summary) {
    if (!diff || !diff.id) {
      return;
    }

    const firstChange = Array.isArray(diff.changes) && diff.changes.length ? diff.changes[0] : null;
    const summarySnapshot = {
      action: summary && summary.action ? summary.action : formatActionLabel(diff.action),
      ruleLabel: summary && summary.ruleLabel
        ? summary.ruleLabel
        : (diff.ruleLabel || RULE_LABELS[diff.ruleType] || diff.ruleType),
      valueLabel: summary && summary.valueLabel
        ? summary.valueLabel
        : (() => {
            if (diff.ruleType === "expression") {
              return diff.ruleValue || "(not set)";
            }
            if (diff.ruleType === "employee-record") {
              const base = diff.ruleValue || (firstChange && firstChange.ruleValueLabel) || "(employee)";
              const change = Array.isArray(diff.changes) ? diff.changes.find(entry => entry.changeType === "employee-record") : null;
              const count = change && Array.isArray(change.fields) ? change.fields.length : diff.matchCount || 0;
              return count > 0 ? `${base} (${count} field${count === 1 ? "" : "s"})` : base;
            }
            return (firstChange && firstChange.ruleValueLabel) || diff.ruleValue || "(not selected)";
          })(),
      ruleType: (summary && summary.ruleType) || diff.ruleType,
      groupLabel: summary && summary.groupLabel
        ? summary.groupLabel
        : (diff.groupName || (summary && summary.groupValue) || "(group)"),
      groupValue: (summary && summary.groupValue) || diff.groupId || diff.groupName
    };

    const card = {
      id: diff.id,
      groupId: diff.groupId || summarySnapshot.groupValue,
      groupName: diff.groupName || summarySnapshot.groupLabel,
      action: diff.action,
      ruleType: diff.ruleType,
      summary: summarySnapshot,
      matchCount: typeof diff.matchCount === "number"
        ? diff.matchCount
        : (Array.isArray(diff.changes) ? diff.changes.length : 0),
      changes: Array.isArray(diff.changes) ? diff.changes.slice() : [],
      policyNotes: Array.isArray(diff.policyNotes) ? diff.policyNotes.slice() : []
    };

    previewDeck = previewDeck.filter(entry => entry.id !== card.id);
    previewDeck.push(card);

    selectedPreviewId = card.id;
    currentDiffId = card.id;
    pendingSummary = null;
    refreshPreviewDeck();
    renderGroupStatus();
  }

  function handleValidateExpression() {
    const expression = expressionInput.value.trim();
    if (!expression) {
      demoStatus.textContent = "Enter an expression to validate.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    demoStatus.textContent = "Validating expression.";
    demoStatus.className = "demo-status demo-status--info";

    apiFetch("/api/expression/validate", {
      method: "POST",
      body: JSON.stringify({ expression })
    })
      .then(res => res.json())
      .then(result => {
        if (result.error) {
          demoStatus.textContent = result.error;
          demoStatus.className = "demo-status demo-status--error";
          return;
        }
        demoStatus.textContent = `Expression valid. Matches ${result.matches} user${result.matches === 1 ? "" : "s"}.`;
        demoStatus.className = "demo-status demo-status--success";
      })
      .catch(err => {
        demoStatus.textContent = `Validation failed: ${err.message}`;
        demoStatus.className = "demo-status demo-status--error";
      });
  }

  function handlePropose() {
    const groupValue = demoGroupSelect.value;
    const groupLabel = getSelectLabel(demoGroupSelect);
    if (!groupValue) {
      demoStatus.textContent = "Choose a group before proposing a change.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    const action = (demoAction.value || "").toLowerCase();
    const ruleType = (demoRuleSelect.value || "user").toLowerCase();
    const value = demoValueSelect.value;
    const expression = expressionInput.value.trim();

    let recordChanges = null;
    if (ruleType === "expression") {
      if (!expression) {
        demoStatus.textContent = "Enter an expression before proposing.";
        demoStatus.className = "demo-status demo-status--error";
        return;
      }
    } else if (!value) {
      demoStatus.textContent = "Select a value for the chosen rule.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    if (ruleType === "employee-record") {
      recordChanges = collectEmployeeRecordChanges(action);
      const totalChanges = recordChanges
        ? Object.keys(recordChanges.set || {}).length + (recordChanges.unset || []).length
        : 0;
      if (!totalChanges) {
        const message = action === "remove"
          ? "Choose at least one record field to clear."
          : "Provide at least one record field to update.";
        demoStatus.textContent = message;
        demoStatus.className = "demo-status demo-status--error";
        return;
      }
    }

    demoStatus.textContent = "Requesting preview.";
    demoStatus.className = "demo-status demo-status--info";

    const payload = {
      action,
      ruleType,
      group: groupValue
    };

    const summarySnapshot = pendingSummary
      ? { ...pendingSummary }
      : {
          action: formatActionLabel(action),
          ruleLabel: RULE_LABELS[ruleType] || getSelectLabel(demoRuleSelect) || ruleType,
          valueLabel: (() => {
            if (ruleType === "expression") {
              return expression || "(not set)";
            }
            if (ruleType === "employee-record") {
              const base = getSelectLabel(demoValueSelect) || value || "(not selected)";
              const counts = getEmployeeRecordChangeCounts(action);
              const total = (counts.set || 0) + (counts.unset || 0);
              return total > 0 ? `${base} (${total} field${total === 1 ? "" : "s"})` : base;
            }
            return getSelectLabel(demoValueSelect) || value || "(not selected)";
          })(),
          ruleType,
          groupLabel: groupLabel || groupValue,
          groupValue
        };

    if (ruleType === "expression") {
      payload.expression = expression;
    } else {
      payload.value = value;
    }

    if (ruleType === "user") {
      payload.user = value;
    }

    if (ruleType === "employee-record") {
      payload.user = value;
      payload.recordChanges = recordChanges;
    }

    apiFetch("/api/propose", {
      method: "POST",
      body: JSON.stringify(payload)
    })
      .then(res => {
        if (res.status === 401) {
          window.location.href = "/login";
          return null;
        }
        return res.json();
      })
      .then(diff => {
        if (!diff) {
          return;
        }
        if (diff.error) {
          demoStatus.textContent = diff.error;
          demoStatus.className = "demo-status demo-status--error";
          demoApplyBtn.disabled = !selectedPreviewId;
          return;
        }
        const normalizedRule = (diff.ruleType || ruleType || "").toLowerCase();
        const customNotes = getPolicyNotesForRule(normalizedRule);
        if (customNotes.length) {
          diff.policyNotes = customNotes;
        }
        renderPreview(diff, summarySnapshot);
        demoStatus.textContent = "Preview ready. Review the change, then confirm.";
        demoStatus.className = "demo-status demo-status--success";
      })
      .catch(err => {
        demoStatus.textContent = `Failed to request preview: ${err.message}`;
        demoStatus.className = "demo-status demo-status--error";
        demoApplyBtn.disabled = !selectedPreviewId;
      });
  }

  function handleApply() {
    if (!currentDiffId) {
      demoStatus.textContent = "Generate a preview before confirming.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    demoStatus.textContent = "Applying change.";
    demoStatus.className = "demo-status demo-status--info";
    demoApplyBtn.disabled = true;
    const diffId = currentDiffId;

    apiFetch("/api/apply", {
      method: "POST",
      body: JSON.stringify({ diffId })
    })
      .then(res => {
        if (res.status === 401) {
          window.location.href = "/login";
          return null;
        }
        return res.json();
      })
      .then(result => {
        if (!result) {
          return;
        }
        if (result.error) {
          demoStatus.textContent = result.error;
          demoStatus.className = "demo-status demo-status--error";
          demoApplyBtn.disabled = !selectedPreviewId;
          return;
        }
        demoStatus.textContent = "Change applied.";
        demoStatus.className = "demo-status demo-status--success";
        removePreviewCard(diffId);
        loadAudit();
        loadGroupMemberships(demoGroupSelect.value);
      })
      .catch(err => {
        demoStatus.textContent = `Failed to apply change: ${err.message}`;
        demoStatus.className = "demo-status demo-status--error";
        demoApplyBtn.disabled = !selectedPreviewId;
      });
  }

  initializeDemoOptions()
    .then(() => {
      updateSummary();
      loadGroupMemberships(demoGroupSelect ? demoGroupSelect.value : "");
    })
    .catch(() => {
      renderGroupStatus();
    });

  loadAudit();
  loadCurrentUser();

  demoGroupSelect.addEventListener("change", () => {
    updateSummary();
    loadGroupMemberships(demoGroupSelect.value);
  });
  demoAction.addEventListener("change", () => {
    if ((demoRuleSelect.value || "").toLowerCase() === "employee-record") {
      renderEmployeeRecordEditor(demoAction.value);
    }
    updateSummary();
  });
  demoRuleSelect.addEventListener("change", () => {
    populateValues(demoRuleSelect.value);
    updateSummary();
  });
  demoValueSelect.addEventListener("change", updateSummary);
  expressionInput.addEventListener("input", updateSummary);

  demoProposeBtn.addEventListener("click", handlePropose);
  demoApplyBtn.addEventListener("click", handleApply);

  if (toggleAuditBtn) {
    toggleAuditBtn.addEventListener("click", toggleAudit);
  }

  if (toggleLogsBtn) {
    toggleLogsBtn.addEventListener("click", toggleLogs);
  }

  if (hideAuditBtn) {
    hideAuditBtn.addEventListener("click", () => {
      if (auditPanel && auditPanel.classList.contains("show")) {
        toggleAudit();
      }
    });
  }

  if (hideLogsBtn) {
    hideLogsBtn.addEventListener("click", () => {
      if (logPanel && logPanel.classList.contains("show")) {
        toggleLogs();
      }
    });
  }
  if (demoClearBtn) {
    demoClearBtn.addEventListener("click", handleClearSelections);
  }
  if (employeeRecordClearBtn) {
    employeeRecordClearBtn.addEventListener("click", () => {
      clearEmployeeRecordInputs();
    });
  }
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      logoutBtn.disabled = true;
      apiFetch("/api/logout", { method: "POST" })
        .catch(() => {})
        .finally(() => {
          window.location.href = "/login";
        });
    });
  }
  if (runPromptBtn) {
    runPromptBtn.addEventListener("click", handleRunPrompt);
  }
  if (dlcPromptInput) {
    dlcPromptInput.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleRunPrompt();
      }
    });
  }
  expressionValidateBtn.addEventListener("click", handleValidateExpression);
});










