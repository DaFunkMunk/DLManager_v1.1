document.addEventListener("DOMContentLoaded", () => {
  const demoGroupSelect = document.getElementById("demoGroupSelect");
  const demoAction = document.getElementById("demoAction");
  const demoRuleSelect = document.getElementById("demoRuleSelect");
  const demoValueSelect = document.getElementById("demoValueSelect");
  const valueFieldContainer = document.getElementById("valueFieldContainer");
  const expressionDrawer = document.getElementById("expressionDrawer");
  const expressionInput = document.getElementById("expressionInput");
  const expressionValidateBtn = document.getElementById("expressionValidateBtn");
  const demoProposeBtn = document.getElementById("demoProposeBtn");
  const demoApplyBtn = document.getElementById("demoApplyBtn");
  const demoStatus = document.getElementById("demoStatus");
  const demoSummaryBody = document.getElementById("demoSummaryBody");
  const demoResult = document.getElementById("demoProposeResult");
  const demoResultList = document.getElementById("demoResultList");
  const demoPolicyNotes = document.getElementById("demoPolicyNotes");
  const demoAuditBody = document.getElementById("demoAuditBody");
  const toggleLogsBtn = document.getElementById("toggleLogsBtn");
  const hideLogsBtn = document.getElementById("hideLogsBtn");
  const logPanel = document.getElementById("logPanel");
  const logContent = document.getElementById("logContent");

  const RULE_LABELS = {
    user: "User",
    tree: "Org Unit",
    location: "Location",
    role: "Role / Job Title",
    "employment-type": "Employment Type",
    tag: "Tag / Attribute",
    "directory-group": "Directory Group",
    "tenure-window": "Tenure Window",
    manager: "Manager / Team Lead",
    "saved-filter": "Saved Filter",
    expression: "Dynamic Expression"
  };

  const STATIC_RULE_VALUES = {
    tree: ["Permian Operations", "Corporate IT", "HSE Response", "Analytics Guild"],
    location: ["Permian Field Office", "Midland Regional HQ", "Houston HQ", "Remote"],
    role: ["Production Engineer", "Pipeline Coordinator", "Contract Technician", "Operations Manager", "HSE Specialist", "Drilling Supervisor", "IT Systems Analyst", "Data Scientist"],
    "employment-type": ["Full-time", "Contractor", "Intern"],
    tag: ["Responder", "Operations", "HSE", "AI", "Analytics", "Leadership"],
    "directory-group": ["DL_Permian_Operators", "DL_Permian_Engineers", "DL_HSE_Responders", "DL_Corporate_IT", "DL_Data_Analytics"],
    "tenure-window": ["0-90", "91-180", "181-365", "365+"],
    manager: ["Casey Lee", "Alex Rivera", "Maria Gonzales", "Erika Howard"],
    "saved-filter": ["HSE Responders", "Permian Engineers", "Contractors Ending Soon"]
  };

  let cachedEmployees = null;
  let cachedLocations = null;
  let currentDiffId = null;

  const apiFetch = (url, options = {}) => {
    const config = { ...options };
    const headers = new Headers(options.headers || {});
    if (config.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    headers.set("X-Mode", "demo");
    config.headers = headers;
    return fetch(url, config);
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

  function toggleExpressionDrawer(visible) {
    expressionDrawer.classList.toggle("hidden", !visible);
    valueFieldContainer.classList.toggle("hidden", visible);
    demoValueSelect.disabled = visible;
    if (visible) {
      demoValueSelect.value = "";
    }
  }

  function populateGroups() {
    apiFetch("/api/groups")
      .then(res => res.json())
      .then(groups => {
        demoGroupSelect.innerHTML = '<option value="" disabled selected>Select a group...</option>';
        if (Array.isArray(groups)) {
          groups.forEach(group => {
            const opt = document.createElement("option");
            opt.value = group.name || group.id;
            opt.textContent = group.name || group.id;
            demoGroupSelect.appendChild(opt);
          });
        }
      })
      .catch(err => console.error("Failed to load groups", err));
  }

  function populateValues(ruleKey) {
    if (ruleKey === "expression") {
      toggleExpressionDrawer(true);
      updateSummary();
      return;
    }

    toggleExpressionDrawer(false);

    if (ruleKey === "user") {
      if (cachedEmployees) {
        setSelectOptions(
          demoValueSelect,
          cachedEmployees.map(emp => ({ value: emp.name, label: emp.name }))
        );
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
        })
        .catch(err => console.error("Failed to load users", err))
        .finally(updateSummary);
      return;
    }

    if (ruleKey === "location") {
      if (cachedLocations) {
        setSelectOptions(demoValueSelect, cachedLocations);
        updateSummary();
        return;
      }
      apiFetch("/api/locations")
        .then(res => res.json())
        .then(values => {
          cachedLocations = Array.isArray(values) ? values : [];
          setSelectOptions(demoValueSelect, cachedLocations);
        })
        .catch(err => console.error("Failed to load locations", err))
        .finally(updateSummary);
      return;
    }

    const staticValues = STATIC_RULE_VALUES[ruleKey] || [];
    setSelectOptions(demoValueSelect, staticValues);
    updateSummary();
  }

  function renderAudit(entries) {
    demoAuditBody.innerHTML = "";
    if (!Array.isArray(entries) || entries.length === 0) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="4" class="status-empty">No audit entries yet.</td>';
      demoAuditBody.appendChild(row);
      return;
    }

    entries.forEach(entry => {
      const row = document.createElement("tr");
      const ts = entry.ts ? new Date(entry.ts).toLocaleString() : "—";
      row.innerHTML = `
        <td>${ts}</td>
        <td>${entry.actor || "system"}</td>
        <td>${entry.op || "-"}</td>
        <td>${entry.status || "-"}</td>
      `;
      demoAuditBody.appendChild(row);
    });
  }

  function loadAudit() {
    apiFetch("/api/audit")
      .then(res => res.json())
      .then(renderAudit)
      .catch(err => console.error("Failed to load audit log", err));
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

  function toggleLogs() {
    const showing = logPanel.classList.toggle("show");
    toggleLogsBtn.textContent = showing ? "Hide Logs" : "Show Logs";
    if (showing) {
      loadLogs();
    }
  }

  function getSelectLabel(selectEl) {
    if (!selectEl) return "";
    const option = selectEl.options[selectEl.selectedIndex];
    if (!option || option.disabled) return "";
    return option.textContent.trim();
  }

  function updateSummary() {
    if (!demoSummaryBody) return;
    demoSummaryBody.innerHTML = "";

    const groupLabel = getSelectLabel(demoGroupSelect);
    if (!groupLabel) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="3" class="status-empty">Select a group to see the pending change.</td>';
      demoSummaryBody.appendChild(row);
      return;
    }

    const actionLabel = getSelectLabel(demoAction) || demoAction.value;
    const ruleKey = demoRuleSelect.value;
    const ruleLabel = RULE_LABELS[ruleKey] || getSelectLabel(demoRuleSelect) || ruleKey;

    const valueLabel = ruleKey === "expression"
      ? (expressionInput.value.trim() || "(not set)")
      : (getSelectLabel(demoValueSelect) || demoValueSelect.value || "(not selected)");

    const row = document.createElement("tr");
    row.innerHTML = `<td>${actionLabel}</td><td>${ruleLabel}</td><td>${valueLabel}</td>`;
    demoSummaryBody.appendChild(row);
  }

  function clearPreview() {
    currentDiffId = null;
    demoApplyBtn.disabled = true;
    demoResult.classList.add("hidden");
    demoResultList.innerHTML = "";
    demoPolicyNotes.innerHTML = "";
    demoPolicyNotes.parentElement.classList.add("hidden");
  }

  function renderPreview(diff) {
    if (!diff || !Array.isArray(diff.changes) || diff.changes.length === 0) {
      clearPreview();
      return;
    }

    demoResultList.innerHTML = "";

    diff.changes.slice(0, 10).forEach(change => {
      const li = document.createElement("li");
      const action = change.action || change.op || "?";
      const ruleLabel = RULE_LABELS[change.ruleType] || change.ruleType;
      const valueLabel = change.ruleType === "expression"
        ? change.expression
        : (change.ruleValueLabel || change.ruleValue || "");
      const userLabel = change.userDisplayName || change.userEmail || "(group)";
      const valuePart = valueLabel ? ` · ${valueLabel}` : "";
      li.textContent = `${action} ${userLabel} (${ruleLabel}${valuePart})`;
      demoResultList.appendChild(li);
    });

    if (diff.matchCount && diff.changes.length > diff.matchCount) {
      const li = document.createElement("li");
      li.textContent = `… and ${diff.matchCount - diff.changes.length} more matches.`;
      demoResultList.appendChild(li);
    }

    demoPolicyNotes.innerHTML = "";
    if (Array.isArray(diff.policyNotes) && diff.policyNotes.length > 0) {
      diff.policyNotes.forEach(note => {
        const item = document.createElement("li");
        item.textContent = note;
        demoPolicyNotes.appendChild(item);
      });
      demoPolicyNotes.parentElement.classList.remove("hidden");
    } else {
      demoPolicyNotes.parentElement.classList.add("hidden");
    }

    demoResult.classList.remove("hidden");
    demoApplyBtn.disabled = false;
  }

  function handleValidateExpression() {
    const expression = expressionInput.value.trim();
    if (!expression) {
      demoStatus.textContent = "Enter an expression to validate.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    demoStatus.textContent = "Validating expression…";
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
        demoStatus.textContent = `Expression valid · Matches ${result.matches} user${result.matches === 1 ? "" : "s"}.`;
        demoStatus.className = "demo-status demo-status--success";
      })
      .catch(err => {
        demoStatus.textContent = `Validation failed: ${err.message}`;
        demoStatus.className = "demo-status demo-status--error";
      });
  }

  function handlePropose() {
    const groupValue = demoGroupSelect.value;
    if (!groupValue) {
      demoStatus.textContent = "Choose a group before proposing a change.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    const action = (demoAction.value || "").toLowerCase();
    const ruleType = (demoRuleSelect.value || "user").toLowerCase();
    const value = demoValueSelect.value;
    const expression = expressionInput.value.trim();

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

    demoStatus.textContent = "Requesting preview…";
    demoStatus.className = "demo-status demo-status--info";

    const payload = {
      action,
      ruleType,
      group: groupValue
    };

    if (ruleType === "expression") {
      payload.expression = expression;
    } else {
      payload.value = value;
    }

    if (ruleType === "user") {
      payload.user = value;
    }

    apiFetch("/api/propose", {
      method: "POST",
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(diff => {
        if (diff.error) {
          demoStatus.textContent = diff.error;
          demoStatus.className = "demo-status demo-status--error";
          clearPreview();
          return;
        }
        currentDiffId = diff.id;
        renderPreview(diff);
        demoStatus.textContent = "Preview ready. Review the change, then confirm.";
        demoStatus.className = "demo-status demo-status--success";
      })
      .catch(err => {
        demoStatus.textContent = `Failed to request preview: ${err.message}`;
        demoStatus.className = "demo-status demo-status--error";
        clearPreview();
      });
  }

  function handleApply() {
    if (!currentDiffId) {
      demoStatus.textContent = "Generate a preview before confirming.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    demoStatus.textContent = "Applying change…";
    demoStatus.className = "demo-status demo-status--info";
    demoApplyBtn.disabled = true;

    apiFetch("/api/apply", {
      method: "POST",
      body: JSON.stringify({ diffId: currentDiffId })
    })
      .then(res => res.json())
      .then(result => {
        if (result.error) {
          demoStatus.textContent = result.error;
          demoStatus.className = "demo-status demo-status--error";
          demoApplyBtn.disabled = false;
          return;
        }
        demoStatus.textContent = "Change applied.";
        demoStatus.className = "demo-status demo-status--success";
        clearPreview();
        loadAudit();
      })
      .catch(err => {
        demoStatus.textContent = `Failed to apply change: ${err.message}`;
        demoStatus.className = "demo-status demo-status--error";
        demoApplyBtn.disabled = false;
      });
  }

  populateGroups();
  populateValues(demoRuleSelect.value || "user");
  loadAudit();
  updateSummary();

  demoGroupSelect.addEventListener("change", updateSummary);
  demoAction.addEventListener("change", updateSummary);
  demoRuleSelect.addEventListener("change", () => {
    populateValues(demoRuleSelect.value);
    updateSummary();
  });
  demoValueSelect.addEventListener("change", updateSummary);
  expressionInput.addEventListener("input", updateSummary);

  demoProposeBtn.addEventListener("click", handlePropose);
  demoApplyBtn.addEventListener("click", handleApply);
  toggleLogsBtn.addEventListener("click", toggleLogs);
  if (hideLogsBtn) {
    hideLogsBtn.addEventListener("click", () => {
      if (logPanel.classList.contains("show")) {
        toggleLogs();
      }
    });
  }
  expressionValidateBtn.addEventListener("click", handleValidateExpression);
});
