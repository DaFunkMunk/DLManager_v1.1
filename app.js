document.addEventListener("DOMContentLoaded", () => {
  const demoGroupSelect = document.getElementById("demoGroupSelect");
  const demoAction = document.getElementById("demoAction");
  const demoRuleSelect = document.getElementById("demoRuleSelect");
  const demoValueSelect = document.getElementById("demoValueSelect");
  const demoProposeBtn = document.getElementById("demoProposeBtn");
  const demoApplyBtn = document.getElementById("demoApplyBtn");
  const demoStatus = document.getElementById("demoStatus");
  const demoSummaryBody = document.getElementById("demoSummaryBody");
  const demoResult = document.getElementById("demoProposeResult");
  const demoResultList = document.getElementById("demoResultList");
  const demoPolicyNotes = document.getElementById("demoPolicyNotes");
  const demoAuditBody = document.getElementById("demoAuditBody");
  const toggleLogsBtn = document.getElementById("toggleLogsBtn");
  const logPanel = document.getElementById("logPanel");
  const logContent = document.getElementById("logContent");

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

  function populateGroups() {
    apiFetch("/api/groups")
      .then(res => res.json())
      .then(groups => {
        demoGroupSelect.innerHTML = '<option value="" disabled selected>Select a group...</option>';
        if (!Array.isArray(groups)) {
          return;
        }
        groups.forEach(group => {
          const opt = document.createElement("option");
          opt.value = group.name || group.id;
          opt.textContent = group.name || group.id;
          demoGroupSelect.appendChild(opt);
        });
      })
      .catch(err => console.error("Failed to load groups", err));
  }

  function populateValues(rule) {
    const isLocation = rule === "Location";
    const endpoint = isLocation ? "/api/locations" : "/api/employees";

    apiFetch(endpoint)
      .then(res => res.json())
      .then(values => {
        demoValueSelect.innerHTML = '<option value="" disabled selected>Select a value...</option>';
        if (!Array.isArray(values)) {
          return;
        }
        if (isLocation) {
          values.forEach(loc => {
            const opt = document.createElement("option");
            opt.value = loc;
            opt.textContent = loc;
            demoValueSelect.appendChild(opt);
          });
        } else {
          values.forEach(emp => {
            const opt = document.createElement("option");
            opt.value = emp.name || emp.displayName || "";
            opt.textContent = emp.name || emp.displayName || emp.id;
            demoValueSelect.appendChild(opt);
          });
        }
      })
      .catch(err => console.error("Failed to load values", err))
      .finally(updateSummary);
  }

  function renderAudit(entries) {
    demoAuditBody.innerHTML = "";
    if (!Array.isArray(entries) || entries.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.className = "status-empty";
      cell.textContent = "No audit entries yet.";
      row.appendChild(cell);
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

  function getSelectLabel(select) {
    if (!select) return "";
    const option = select.options[select.selectedIndex];
    if (!option || option.disabled) return "";
    return option.textContent.trim();
  }

  function updateSummary() {
    if (!demoSummaryBody) return;
    demoSummaryBody.innerHTML = "";

    const groupLabel = getSelectLabel(demoGroupSelect);
    if (!groupLabel) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 3;
      cell.className = "status-empty";
      cell.textContent = "Select a group to see the pending change.";
      row.appendChild(cell);
      demoSummaryBody.appendChild(row);
      return;
    }

    const actionLabel = getSelectLabel(demoAction) || demoAction.value;
    const ruleLabel = getSelectLabel(demoRuleSelect) || demoRuleSelect.value;
    const valueLabel = getSelectLabel(demoValueSelect) || "(not selected)";

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
    diff.changes.forEach(change => {
      const li = document.createElement("li");
      const action = change.op === "REMOVE" ? "Remove" : "Add";
      const expires = change.expiresAt ? ` (expires ${new Date(change.expiresAt).toLocaleDateString()})` : "";
      li.textContent = `${action} ${change.userDisplayName || change.userId} in ${change.groupName || change.groupId}${expires}`;
      demoResultList.appendChild(li);
    });

    demoPolicyNotes.innerHTML = "";
    if (Array.isArray(diff.policyNotes) && diff.policyNotes.length > 0) {
      diff.policyNotes.forEach(note => {
        const li = document.createElement("li");
        li.textContent = note;
        demoPolicyNotes.appendChild(li);
      });
      demoPolicyNotes.parentElement.classList.remove("hidden");
    } else {
      demoPolicyNotes.parentElement.classList.add("hidden");
    }

    demoResult.classList.remove("hidden");
    demoApplyBtn.disabled = false;
  }

  function handlePropose() {
    const groupValue = demoGroupSelect.value;
    const value = demoValueSelect.value;

    if (!groupValue) {
      demoStatus.textContent = "Choose a group before proposing a change.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    if (!value) {
      demoStatus.textContent = "Select a value for the chosen rule.";
      demoStatus.className = "demo-status demo-status--error";
      return;
    }

    demoStatus.textContent = "Requesting preview…";
    demoStatus.className = "demo-status demo-status--info";

    const intent = {
      action: demoAction.value,
      user: value,
      group: groupValue
    };

    apiFetch("/api/propose", {
      method: "POST",
      body: JSON.stringify(intent)
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
        console.error("Failed to propose change", err);
        demoStatus.textContent = "Failed to request preview.";
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

    demoApplyBtn.disabled = true;
    demoStatus.textContent = "Applying change…";
    demoStatus.className = "demo-status demo-status--info";

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
        console.error("Failed to apply change", err);
        demoStatus.textContent = "Failed to apply change.";
        demoStatus.className = "demo-status demo-status--error";
        demoApplyBtn.disabled = false;
      });
  }

  populateGroups();
  populateValues(demoRuleSelect.value);
  loadAudit();
  updateSummary();

  demoGroupSelect.addEventListener("change", updateSummary);
  demoAction.addEventListener("change", updateSummary);
  demoRuleSelect.addEventListener("change", () => {
    populateValues(demoRuleSelect.value);
    updateSummary();
  });
  demoValueSelect.addEventListener("change", updateSummary);

  demoProposeBtn.addEventListener("click", handlePropose);
  demoApplyBtn.addEventListener("click", handleApply);
  toggleLogsBtn.addEventListener("click", toggleLogs);
});
