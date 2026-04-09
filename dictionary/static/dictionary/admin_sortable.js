(function () {
  "use strict";

  const HANDLE_CLS = "sortable-handle";
  const BTN_CLS = "sortable-btn";
  const DRAGGING_CLS = "sortable-dragging";
  const OVER_CLS = "sortable-dragover";

  function getInlineGroups() {
    return document.querySelectorAll(".inline-group");
  }

  function isTabular(group) {
    return !!group.querySelector(".tabular");
  }

  function getRows(group) {
    if (isTabular(group)) {
      return Array.from(
        group.querySelectorAll("tbody tr.form-row:not(.empty-form)")
      ).filter((r) => {
        const del = r.querySelector('input[id$="-DELETE"]');
        return !del || !del.checked;
      });
    }
    return Array.from(
      group.querySelectorAll(".inline-related:not(.empty-form)")
    ).filter((r) => {
      const del = r.querySelector('input[id$="-DELETE"]');
      return !del || !del.checked;
    });
  }

  function findOrderField(row) {
    return row.querySelector('input[name$="-order_index"]');
  }

  function hasExistingPk(row) {
    const idField = row.querySelector('input[name$="-id"][type="hidden"]');
    return idField && idField.value !== "";
  }

  function renumber(group) {
    const rows = getRows(group);
    rows.forEach((row, i) => {
      const field = findOrderField(row);
      if (field && hasExistingPk(row)) {
        field.value = (i + 1) * 10;
      }
      const badge = row.querySelector(".sortable-pos-num");
      if (badge) badge.textContent = "#" + (i + 1);
    });
  }

  function swapRows(group, rowA, rowB) {
    if (!rowA || !rowB) return;
    const parent = rowA.parentNode;
    if (rowA.nextSibling === rowB) {
      parent.insertBefore(rowB, rowA);
    } else {
      const refNode = rowB.nextSibling;
      parent.insertBefore(rowA, rowB);
      parent.insertBefore(rowB, refNode);
    }
    renumber(group);
  }

  function buildControls(group, row) {
    const wrapper = document.createElement("div");
    wrapper.className = "sortable-controls";

    const handle = document.createElement("span");
    handle.className = HANDLE_CLS;
    handle.title = "Sürükle";
    handle.textContent = "⠿";

    const num = document.createElement("span");
    num.className = "sortable-pos-num";

    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.className = BTN_CLS;
    upBtn.title = "Yukarı taşı";
    upBtn.innerHTML = "▲";
    upBtn.addEventListener("click", function () {
      const rows = getRows(group);
      const idx = rows.indexOf(row);
      if (idx > 0) {
        swapRows(group, rows[idx - 1], row);
        row.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });

    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.className = BTN_CLS;
    downBtn.title = "Aşağı taşı";
    downBtn.innerHTML = "▼";
    downBtn.addEventListener("click", function () {
      const rows = getRows(group);
      const idx = rows.indexOf(row);
      if (idx < rows.length - 1) {
        swapRows(group, row, rows[idx + 1]);
        row.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });

    wrapper.appendChild(handle);
    wrapper.appendChild(num);
    wrapper.appendChild(upBtn);
    wrapper.appendChild(downBtn);
    return wrapper;
  }

  /* ── Drag & Drop (works for both <tr> and <div> rows) ── */

  function initDrag(group) {
    let dragRow = null;
    const rowSelector = isTabular(group)
      ? "tr.form-row"
      : ".inline-related";

    group.addEventListener("dragstart", function (e) {
      const row = e.target.closest(rowSelector);
      if (!row || row.classList.contains("empty-form")) return;
      dragRow = row;
      row.classList.add(DRAGGING_CLS);
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", "");
    });

    group.addEventListener("dragover", function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const row = e.target.closest(rowSelector);
      if (!row || row === dragRow || row.classList.contains("empty-form"))
        return;
      group
        .querySelectorAll("." + OVER_CLS)
        .forEach((r) => r.classList.remove(OVER_CLS));
      row.classList.add(OVER_CLS);
    });

    group.addEventListener("dragleave", function (e) {
      const row = e.target.closest(rowSelector);
      if (row) row.classList.remove(OVER_CLS);
    });

    group.addEventListener("drop", function (e) {
      e.preventDefault();
      group
        .querySelectorAll("." + OVER_CLS)
        .forEach((r) => r.classList.remove(OVER_CLS));
      const targetRow = e.target.closest(rowSelector);
      if (
        !targetRow ||
        !dragRow ||
        targetRow === dragRow ||
        targetRow.classList.contains("empty-form")
      )
        return;
      targetRow.parentNode.insertBefore(dragRow, targetRow);
      renumber(group);
    });

    group.addEventListener("dragend", function () {
      if (dragRow) dragRow.classList.remove(DRAGGING_CLS);
      group
        .querySelectorAll("." + OVER_CLS)
        .forEach((r) => r.classList.remove(OVER_CLS));
      dragRow = null;
    });
  }

  /* ── Hide the raw order_index fields ── */

  function hideOrderFields(group) {
    if (isTabular(group)) {
      const table = group.querySelector("table");
      if (!table) return;
      const headers = table.querySelectorAll("thead th");
      headers.forEach((th, i) => {
        if (th.textContent.trim().toLowerCase().includes("order")) {
          th.style.display = "none";
          table.querySelectorAll("tbody tr").forEach((tr) => {
            const cells = tr.querySelectorAll("td");
            if (cells[i]) cells[i].style.display = "none";
          });
        }
      });
      return;
    }
    group.querySelectorAll(".inline-related").forEach((row) => {
      const field = findOrderField(row);
      if (!field) return;
      const fieldRow = field.closest(".form-row");
      if (fieldRow) fieldRow.style.display = "none";
    });
  }

  /* ── Summary bar for stacked inlines ── */

  function buildSummaryBar(row) {
    const bar = document.createElement("div");
    bar.className = "sortable-summary";

    const posSelect = row.querySelector('select[name$="-part_of_speech"]');
    const transInput = row.querySelector('input[name$="-translation"]');

    function update() {
      const posText = posSelect
        ? posSelect.options[posSelect.selectedIndex]?.text || ""
        : "";
      const transText = transInput ? transInput.value : "";
      bar.textContent = [posText, transText].filter(Boolean).join(" — ");
    }

    if (posSelect) posSelect.addEventListener("change", update);
    if (transInput) transInput.addEventListener("input", update);
    update();
    return bar;
  }

  /* ── Tabular inline: inject controls into the first <td> ── */

  function setupTabularRow(group, row) {
    row.setAttribute("draggable", "true");
    const firstTd = row.querySelector("td");
    if (!firstTd) return;
    const controls = buildControls(group, row);
    controls.style.display = "inline-flex";
    controls.style.marginRight = "6px";
    firstTd.prepend(controls);
  }

  /* ── Stacked inline: inject controls into h3 header ── */

  function setupStackedRow(group, row) {
    row.setAttribute("draggable", "true");
    const h3 = row.querySelector("h3");
    if (!h3) return;
    const controls = buildControls(group, row);
    h3.prepend(controls);
    const summary = buildSummaryBar(row);
    h3.appendChild(summary);
  }

  /* ── Main setup ── */

  function setup() {
    getInlineGroups().forEach(function (group) {
      const hasOrderField = group.querySelector('input[name$="-order_index"]');
      if (!hasOrderField) return;

      group.classList.add("sortable-group");
      initDrag(group);
      hideOrderFields(group);

      const tabular = isTabular(group);
      const rows = tabular
        ? group.querySelectorAll("tbody tr.form-row:not(.empty-form)")
        : group.querySelectorAll(".inline-related:not(.empty-form)");

      rows.forEach(function (row) {
        if (tabular) {
          setupTabularRow(group, row);
        } else {
          setupStackedRow(group, row);
        }
      });

      renumber(group);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup);
  } else {
    setup();
  }
})();
