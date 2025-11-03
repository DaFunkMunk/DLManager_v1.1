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
  let previewDeck = [];
  let selectedPreviewId = null;
  let currentGroupMembers = [];
  let pendingSummary = null;
  let loadingGroupMembers = false;
  let membershipError = null;
  let hasGroupSelected = false;

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

  function toggleExpressionDrawer(visible) {
    expressionDrawer.classList.toggle("hidden", !visible);
    valueFieldContainer.classList.toggle("hidden", visible);
    demoValueSelect.disabled = visible;
    if (visible) {
      demoValueSelect.value = "";
    }
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
            <p class="audit-entry__group">${group}</p>
            <p class="audit-entry__rule"><strong>${ruleLabel}:</strong> ${ruleValue}</p>
            ${beforeRules ? `<p class="audit-entry__rule audit-entry__rule--before"><strong>Previously:</strong> ${beforeRules}</p>` : ''}
            ${afterRules ? `<p class="audit-entry__rule audit-entry__rule--after"><strong>Result:</strong> ${afterRules}</p>` : ''}
            <p class="audit-entry__summary"><strong>Affected:</strong> ${affectedLine}</p>
            <p class="audit-entry__summary"><strong>Prior:</strong> ${beforeLine}</p>
            ${policyNotes}
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
    if (demoRuleSelect && demoRuleSelect.value === "expression") {
      if (expressionInput) {
        expressionInput.value = "";
      }
    } else if (demoValueSelect) {
      resetSelectToPlaceholder(demoValueSelect);
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
        const valueLabel = member.valueLabel || "-";
        const tr = document.createElement("tr");
        tr.classList.add("group-status__row");
        tr.innerHTML = `
          <td class="group-status__cell"><span class="group-status__tag group-status__tag--current">${actionText}</span></td>
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

    if (pendingSummary && pendingSummary.groupValue === selectedGroupValue) {
      const pendingValue = pendingSummary.valueLabel || "(not selected)";
      const tr = document.createElement("tr");
      tr.classList.add("group-status__row", "group-status__pending");
      tr.innerHTML = `
        <td class="group-status__cell"><span class="group-status__tag group-status__tag--pending">${pendingSummary.action}</span></td>
        <td class="group-status__cell">${pendingSummary.ruleLabel}</td>
        <td class="group-status__cell">${pendingValue}</td>
      `;
      demoSummaryBody.appendChild(tr);
      rowsRendered += 1;
    }

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
    const actionLabel = getSelectLabel(demoAction) || formatActionLabel(demoAction.value);
    const ruleLabel = RULE_LABELS[ruleKey] || getSelectLabel(demoRuleSelect) || ruleKey;
    const valueLabel = ruleKey === "expression"
      ? (expressionInput.value.trim() || "(not set)")
      : (getSelectLabel(demoValueSelect) || demoValueSelect.value || "(not selected)");

    pendingSummary = {
      action: actionLabel,
      ruleLabel,
      valueLabel,
      ruleType: ruleKey,
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
    demoPreviewCards.classList.toggle("demo-preview__cards--scroll", previewDeck.length >= 4);
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

    const matchCount = typeof card.matchCount === "number"
      ? card.matchCount
      : (Array.isArray(card.changes) ? card.changes.length : 0);
    const matchesLine = document.createElement("p");
    matchesLine.className = "preview-card__matches";
    matchesLine.textContent = matchCount
      ? `${matchCount} match${matchCount === 1 ? "" : "es"}`
      : "No matching members.";
    cardEl.appendChild(matchesLine);

    const changeList = document.createElement("ul");
    changeList.className = "preview-card__changes";
    const maxChanges = 10;
    const changesToRender = Array.isArray(card.changes) ? card.changes.slice(0, maxChanges) : [];

    changesToRender.forEach(change => {
      const li = document.createElement("li");
      const action = change.action || change.op || "?";
      const rule = change.ruleLabel || RULE_LABELS[change.ruleType] || change.ruleType;
      const user = change.userDisplayName || change.userEmail || "(group)";
      const valuePart = change.ruleValueLabel ? ` - ${change.ruleValueLabel}` : "";
      li.textContent = `${action} ${user} (${rule}${valuePart})`;
      changeList.appendChild(li);
    });

    if (matchCount > changesToRender.length) {
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
        : (diff.ruleType === "expression"
          ? (diff.ruleValue || "(not set)")
          : ((firstChange && firstChange.ruleValueLabel) || diff.ruleValue || "(not selected)")),
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
          valueLabel: ruleType === "expression"
            ? (expression || "(not set)")
            : (getSelectLabel(demoValueSelect) || value || "(not selected)"),
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

  populateGroups();
  populateValues(demoRuleSelect.value || "user");
  loadAudit();
  updateSummary();
  loadCurrentUser();

  demoGroupSelect.addEventListener("change", () => {
    updateSummary();
    loadGroupMemberships(demoGroupSelect.value);
  });
  demoAction.addEventListener("change", updateSummary);
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
