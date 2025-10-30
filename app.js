document.addEventListener("DOMContentLoaded", () => {
  const listSelect = document.getElementById("listSelect");
  const rulesTable = document.getElementById("rulesTable");
  const flagSelect = document.getElementById("flagSelect");
  const ruleTypeSelect = document.getElementById("ruleTypeSelect");
  const valueSelect = document.getElementById("valeSelect");

  function showSpinner() {
    document.getElementById("spinner").style.display = "block";
    const status = document.getElementById("spinnerStatus");
    status.classList.add("hidden");
    status.classList.remove("success", "error", "fade-out");
  }

  function showSpinnerSuccess() {
    const spinner = document.getElementById("spinner");
    const status = document.getElementById("spinnerStatus");

    spinner.style.display = "none";
    status.textContent = "�o\"";
    status.classList.remove("hidden", "error", "fade-out");
    status.classList.add("success");

    setTimeout(() => {
      status.classList.add("fade-out");
      setTimeout(() => {
        status.classList.add("hidden");
        status.classList.remove("fade-out", "success", "error");
      }, 1000);
    }, 15000);
  }

  function showSpinnerError() {
    const spinner = document.getElementById("spinner");
    const status = document.getElementById("spinnerStatus");

    spinner.style.display = "none";
    status.textContent = "�o";
    status.classList.remove("hidden", "success", "fade-out");
    status.classList.add("error");

    setTimeout(() => {
      status.classList.add("fade-out");
      setTimeout(() => {
        status.classList.add("hidden");
        status.classList.remove("fade-out", "success", "error");
      }, 1000);
    }, 15000);
  }

  function hideSpinner() {
    document.getElementById("spinner").style.display = "none";
    const status = document.getElementById("spinnerStatus");
    status.classList.add("hidden");
    status.classList.remove("success", "error", "fade-out");
  }

  fetch('/api/lists')
    .then(res => res.json())
    .then(data => {
      listSelect.innerHTML = "";
      data.forEach(name => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        listSelect.appendChild(opt);
      });

      if (data.length > 0) {
        listSelect.value = data[0];
        loadRules(data[0]);
        loadPreview(data[0]);
      }
    });

  fetch('/api/employees')
    .then(res => res.json())
    .then(data => {
      valueSelect.innerHTML = "";

      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Select an employee...";
      placeholder.disabled = true;
      placeholder.selected = true;
      valueSelect.appendChild(placeholder);

      data.forEach(emp => {
        const opt = document.createElement("option");
        opt.textContent = emp.name;
        opt.value = emp.name;
        valueSelect.appendChild(opt);
      });

      if (!valueSelect.tomselect) {
        new TomSelect("#valeSelect", {
          create: false,
          placeholder: "Name",
          sortField: {
            field: "text",
            direction: "asc"
          },
          dropdownDirection: 'down'
        });
      }
    });

  ruleTypeSelect.addEventListener("change", () => {
    if (valueSelect.tomselect) {
      valueSelect.tomselect.destroy();
    }
    const selectedType = ruleTypeSelect.value;
    valueSelect.innerHTML = "";

    if (selectedType === "Location") {
      fetch("/api/locations")
        .then(res => res.json())
        .then(data => {
          const placeholder = document.createElement("option");
          placeholder.textContent = "Select a location...";
          placeholder.disabled = true;
          placeholder.selected = true;
          valueSelect.appendChild(placeholder);

          data.forEach(loc => {
            const opt = document.createElement("option");
            opt.textContent = loc;
            opt.value = loc;
            valueSelect.appendChild(opt);
          });
        });
    } else {
      fetch("/api/employees")
        .then(res => res.json())
        .then(data => {
          const placeholder = document.createElement("option");
          placeholder.textContent = "Select an employee...";
          placeholder.disabled = true;
          placeholder.selected = true;
          valueSelect.appendChild(placeholder);

          data.forEach(emp => {
            const opt = document.createElement("option");
            opt.textContent = emp.name;
            opt.value = emp.name;
            valueSelect.appendChild(opt);
          });

          if (!valueSelect.tomselect) {
            new TomSelect("#valeSelect", {
              create: false,
              placeholder: "Name",
              sortField: {
                field: "text",
                direction: "asc"
              },
              dropdownDirection: 'down'
            });
          }
        });
    }
  });

  listSelect.addEventListener("change", () => {
    const selectedName = listSelect.value;
    loadRules(selectedName);
    loadPreview(selectedName);
  });

  function loadRules(dlName) {
    fetch(`/api/rules/${encodeURIComponent(dlName)}`)
      .then(res => res.json())
      .then(data => {
        rulesTable.innerHTML = "";
        data.forEach(rule => {
          addRuleToTable(rule.Flag, rule.RuleType, rule.Value, dlName);
        });
      });
  }

  function loadPreview(dlName) {
    fetch(`/api/preview/${encodeURIComponent(dlName)}`)
      .then(res => res.json())
      .then(data => {
        document.getElementById("previewLabel").textContent = "Full List Preview:";
        const previewList = document.getElementById("previewList");
        previewList.innerHTML = "";
        data.forEach(name => {
          const row = document.createElement("tr");
          row.innerHTML = `<td>${name}</td>`;
          previewList.appendChild(row);
        });
      });
  }

  function addRuleToTable(flag, type, value, dlName = null) {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${flag}</td><td>${type}</td><td>${value}</td>`;

    const isTree = type === 'Tree';
    if (isTree) {
      row.classList.add("tree-row");
    }

    row.addEventListener("click", () => {
      const isSelected = row.classList.contains("selected");
      rulesTable.querySelectorAll("tr").forEach(r => r.classList.remove("selected", "non-tree-row"));

      if (!isSelected) {
        if (isTree) {
          row.classList.add("selected", "tree-row");
          if (dlName) {
            fetch(`/api/treepreview/${encodeURIComponent(dlName)}/${encodeURIComponent(value)}`)
              .then(res => res.json())
              .then(data => {
                document.getElementById("previewLabel").textContent = "Tree Preview:";
                const previewList = document.getElementById("previewList");
                previewList.innerHTML = "";
                data.forEach(name => {
                  const treeRow = document.createElement("tr");
                  treeRow.innerHTML = `<td>${name}</td>`;
                  previewList.appendChild(treeRow);
                });
              });
          }
        } else {
          row.classList.add("selected", "non-tree-row");
        }
      }
    });

    rulesTable.appendChild(row);
  }

  window.addRule = function () {
    const flag = flagSelect.value;
    const type = ruleTypeSelect.value;
    const value = valueSelect.value;
    const dlName = listSelect.value;

    if (!flag || !type || !value) {
      alert("Please select a Flag, Rule Type, and Value before adding a rule.");
      return;
    }

    addRuleToTable(flag, type, value);

    fetch('/api/addrule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flag, type, value, dlName })
    })
    .then(res => res.json())
    .then(data => {
      const logDetails = { flag, type, value, dlName };
      if (data.success) {
        logMessage("/api/addrule", "POST", 200, logDetails);
      } else {
        logMessage("/api/addrule", "POST", 500, logDetails);
        alert('Failed to add rule to database.');
      }
    });
  };

  window.deleteRule = function () {
    const selectedRow = rulesTable.querySelector("tr.selected");

    if (!selectedRow) {
      alert("Please select a row to delete.");
      return;
    }

    const flag = selectedRow.children[0].textContent;
    const type = selectedRow.children[1].textContent;
    const value = selectedRow.children[2].textContent;
    const dlName = listSelect.value;

    selectedRow.remove();

    fetch('/api/deleterule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flag, type, value, dlName })
    })
    .then(res => res.json())
    .then(data => {
      const logDetails = { flag, type, value, dlName };
      if (data.success) {
        logMessage("/api/deleterule", "POST", 200, logDetails);
      } else {
        logMessage("/api/deleterule", "POST", 500, logDetails);
        alert('Failed to delete rule from database.');
      }
    });
  };

  window.toggleLogs = function () {
    const panel = document.getElementById("logPanel");
    const isOpen = panel.classList.contains("show");
    panel.classList.toggle("show");
    document.getElementById("toggleLogsBtn").textContent = isOpen ? "Show Logs" : "Hide Logs";

    if (!isOpen) {
      loadPersistentLogs();
    }
  };

  function loadPersistentLogs() {
    fetch("/api/logs")
      .then(res => res.text())
      .then(text => {
        const logEl = document.getElementById("logContent");
        logEl.textContent = text;
        logEl.scrollTop = logEl.scrollHeight;
      });
  }

  function logMessage(endpoint, method = "GET", status = 200, details = null) {
    const logEl = document.getElementById("logContent");
    const now = new Date();

    const ip = "127.0.0.1";
    const date = now.toLocaleDateString("en-GB", {
      day: "2-digit", month: "short", year: "numeric"
    }).replace(/ /g, '/');

    const time = now.toLocaleTimeString("en-GB", { hour12: false });
    let message = `${ip} - - [${date} ${time}] "${method} ${endpoint} HTTP/1.1" ${status} -`;

    if (details) {
      const detailStr = JSON.stringify(details, null, 2).replace(/\n/g, ' ').replace(/\s+/g, ' ');
      message += `\n  �+' Details: ${detailStr}`;
    }

    logEl.textContent += message + "\n";
    logEl.scrollTop = logEl.scrollHeight;
  }

  window.previewList = function () {
    const dlName = document.getElementById("listSelect").value;
    loadPreview(dlName);
  };

  // �o. APPLY RULES button logic with spinner
  window.applyRules = function () {
    showSpinner();
    fetch('/api/applyrules', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        const details = { triggeredBy: sessionStorage.getItem("user") || "unknown" };
        if (data.success) {
          logMessage("/api/applyrules", "POST", 200, details);
          alert("Rules applied successfully.");
          showSpinnerSuccess();
        } else {
          logMessage("/api/applyrules", "POST", 500, details);
          alert("Failed to apply rules: " + data.error);
          showSpinnerError();
        }
      })
      .catch(err => {
        alert("Unexpected error: " + err.message);
        showSpinnerError();
      });
  };
  // �o. REFRESH AD button logic with spinner
  window.refreshAD = function () {
    showSpinner();
    fetch('/api/refreshad', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        const details = { triggeredBy: sessionStorage.getItem("user") || "unknown" };
        if (data.success) {
          logMessage("/api/refreshad", "POST", 200, details);
          alert("Active Directory refreshed successfully.");
          showSpinnerSuccess();
        } else {
          logMessage("/api/refreshad", "POST", 500, details);
          alert("Failed to refresh from AD: " + data.error);
          showSpinnerError();
        }
      })
      .catch(err => {
        alert("Unexpected error: " + err.message);
        showSpinnerError();
      });
  };
});
