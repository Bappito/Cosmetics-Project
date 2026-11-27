// Shared table look for the whole ERP, following the reference screens.
// Every table in a .table-wrap gets: a card with its section title and row count, a search box,
// an "export to Excel" button (CSV that Excel opens), status pills, and for read-only tables
// click-to-sort headers and 25 rows per page.
// Editable tables (class "editor") keep every row in the page so the form still saves them;
// search only hides rows. Matrix and PRR grids are left alone.
(function () {
  'use strict';

  var PAGE_SIZE = 25;
  var SKIP = /\b(matrix-table|prr-table)\b/;
  var STATUS_HEAD = /סטטוס|status/i;
  var isHe = (document.documentElement.lang || 'he') === 'he';
  var T = isHe
    ? { search: 'חיפוש...', rows: 'שורות', of: 'מתוך', shown: 'מוצגות', prev: 'הקודם', next: 'הבא', page: 'עמוד', exportBtn: 'ייצא לאקסל' }
    : { search: 'Search...', rows: 'rows', of: 'of', shown: 'Showing', prev: 'Prev', next: 'Next', page: 'Page', exportBtn: 'Export to Excel' };
  var EXPORT_ICON = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' +
    '<path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>';

  // The text a user sees in a cell. Form fields report their current value, not empty text.
  function cellText(td) {
    var field = td.querySelector('input, select, textarea');
    if (field) {
      if (field.tagName === 'SELECT') {
        var opt = field.options[field.selectedIndex];
        return opt ? opt.text.trim() : '';
      }
      if (field.type === 'checkbox') return field.checked ? '✓' : '';
      return (field.value || '').trim();
    }
    return (td.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function rowText(tr) {
    return Array.prototype.map.call(tr.cells, cellText).join(' ');
  }

  function asNumber(s) {
    var cleaned = s.replace(/[,\s]/g, '').replace(/[^0-9.\-]/g, '');
    if (cleaned === '' || cleaned === '-' || cleaned === '.') return null;
    var n = parseFloat(cleaned);
    return isNaN(n) ? null : n;
  }

  function csvCell(value) {
    var s = String(value).replace(/"/g, '""');
    return /[",\n]/.test(s) ? '"' + s + '"' : s;
  }

  function headerRow(table) {
    return table.tHead && table.tHead.rows.length ? table.tHead.rows[table.tHead.rows.length - 1] : null;
  }

  function exportCsv(table, rows, name) {
    var head = headerRow(table);
    var lines = [];
    if (head) {
      lines.push(Array.prototype.map.call(head.cells, function (c) { return csvCell((c.textContent || '').trim()); }).join(','));
    }
    rows.forEach(function (tr) {
      lines.push(Array.prototype.map.call(tr.cells, function (c) { return csvCell(cellText(c)); }).join(','));
    });
    // A byte-order mark makes Excel read Hebrew text correctly.
    var blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = (name || 'table') + '-' + new Date().toISOString().slice(0, 10) + '.csv';
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 0);
  }

  // Status column: plain text becomes a coloured pill, as in the reference screens.
  function pillStatus(table) {
    var head = headerRow(table);
    if (!head || !table.tBodies[0]) return;
    Array.prototype.forEach.call(head.cells, function (th, index) {
      if (!STATUS_HEAD.test(th.textContent || '')) return;
      Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
        var td = tr.cells[index];
        if (!td || td.querySelector('input, select, textarea') || td.querySelector('.status-pill')) return;
        var text = (td.textContent || '').trim();
        if (!text) return;
        var pill = document.createElement('span');
        pill.className = 'status-pill ' + pillClass(text);
        pill.textContent = text;
        td.textContent = '';
        td.appendChild(pill);
      });
    });
  }

  function pillClass(text) {
    var t = text.toLowerCase();
    if (/received|delivered|done|הושלם|נמסר|התקבל|ok|פעיל|active|confirmed/.test(t)) return 'pill-closed';
    if (/cancel|בוטל|expired|שפג|חסר|bad/.test(t)) return 'pill-bad';
    return 'pill-open';
  }

  function enhance(table) {
    if (table.dataset.enhanced || SKIP.test(table.className)) return;
    var tbody = table.tBodies[0];
    var wrap = table.parentElement;
    if (!tbody || !wrap || !wrap.classList.contains('table-wrap')) return;
    // A page that already built its own toolbar (for example the product trees page) is left as it is.
    var card = wrap.closest('.table-card');
    if (card && card.querySelector(':scope > .grid-bar')) return;
    table.dataset.enhanced = '1';

    var editable = table.classList.contains('editor');
    var allRows = Array.prototype.slice.call(tbody.rows);
    var state = { page: 0, sortCol: -1, dir: 1, query: '', filtered: allRows };
    var head = headerRow(table);
    var headCells = head ? head.cells : [];

    var section = wrap.closest('.block');
    var heading = section ? section.querySelector(':scope > h2') : null;
    var title = heading ? heading.textContent.trim() : '';
    if (heading) heading.style.display = 'none';
    if (section) section.classList.add('table-section');

    pillStatus(table);

    var bar = document.createElement('div');
    bar.className = 'grid-bar';
    bar.innerHTML =
      '<div class="grid-head">' +
        '<h3 class="grid-title"></h3>' +
        '<span class="grid-count muted small"></span>' +
      '</div>' +
      '<div class="grid-tools">' +
        '<label class="grid-searchbox"><input type="search" class="grid-search" placeholder="' + T.search + '" aria-label="' + T.search + '"></label>' +
        '<button type="button" class="grid-export">' + EXPORT_ICON + '<span>' + T.exportBtn + '</span></button>' +
      '</div>';
    bar.querySelector('.grid-title').textContent = title ? title + ' (' + allRows.length + ')' : '';
    wrap.parentNode.insertBefore(bar, wrap);

    var pager = null, pageLabel = null, prev = null, next = null;
    if (!editable) {
      pager = document.createElement('div');
      pager.className = 'grid-pager';
      pager.innerHTML =
        '<button type="button" class="grid-prev">' + T.prev + '</button>' +
        '<span class="grid-page muted small"></span>' +
        '<button type="button" class="grid-next">' + T.next + '</button>';
      wrap.parentNode.insertBefore(pager, wrap.nextSibling);
      pageLabel = pager.querySelector('.grid-page');
      prev = pager.querySelector('.grid-prev');
      next = pager.querySelector('.grid-next');
    }

    var search = bar.querySelector('.grid-search');
    var count = bar.querySelector('.grid-count');

    // The title already carries the total, so the count appears only when some rows are hidden.
    function showCount(shown) {
      count.textContent = title && shown === allRows.length
        ? ''
        : T.shown + ' ' + shown + ' ' + T.of + ' ' + allRows.length + ' ' + T.rows;
    }

    // Read-only tables: move only the visible page into the table.
    // Editable tables: keep every row in the page and just show or hide them.
    function render() {
      var total = state.filtered.length;
      if (editable) {
        allRows.forEach(function (tr) { tr.style.display = 'none'; });
        state.filtered.forEach(function (tr) { tr.style.display = ''; });
        showCount(total);
        return;
      }
      var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
      if (state.page >= pages) state.page = pages - 1;
      var start = state.page * PAGE_SIZE;
      var visible = state.filtered.slice(start, start + PAGE_SIZE);
      tbody.innerHTML = '';
      visible.forEach(function (tr) { tbody.appendChild(tr); });
      showCount(visible.length);
      pageLabel.textContent = T.page + ' ' + (state.page + 1) + ' / ' + pages;
      prev.disabled = state.page === 0;
      next.disabled = state.page >= pages - 1;
      pager.style.display = total > PAGE_SIZE ? '' : 'none';
    }

    function applySort() {
      if (state.sortCol >= 0) {
        var col = state.sortCol, dir = state.dir;
        state.filtered = state.filtered.slice().sort(function (a, b) {
          var x = cellText(a.cells[col] || { textContent: '' });
          var y = cellText(b.cells[col] || { textContent: '' });
          var nx = asNumber(x), ny = asNumber(y);
          if (nx !== null && ny !== null) return (nx - ny) * dir;
          return x.localeCompare(y, undefined, { numeric: true }) * dir;
        });
      }
      state.page = 0;
      render();
    }

    function applyFilter() {
      var q = state.query.toLowerCase();
      state.filtered = allRows.filter(function (tr) {
        return !q || rowText(tr).toLowerCase().indexOf(q) !== -1;
      });
      applySort();
    }

    // Enter in the search box must not submit an enclosing form.
    search.addEventListener('keydown', function (e) { if (e.key === 'Enter') e.preventDefault(); });
    search.addEventListener('input', function () {
      state.query = search.value.trim();
      applyFilter();
    });

    bar.querySelector('.grid-export').addEventListener('click', function () {
      exportCsv(table, state.filtered, (title || 'table').replace(/[^\w֐-׿-]+/g, '_'));
    });

    if (!editable) {
      prev.addEventListener('click', function () { state.page -= 1; render(); });
      next.addEventListener('click', function () { state.page += 1; render(); });

      Array.prototype.forEach.call(headCells, function (th, index) {
        if (th.colSpan > 1) return;
        th.classList.add('sortable');
        th.addEventListener('click', function () {
          if (state.sortCol === index) {
            state.dir = -state.dir;
          } else {
            state.sortCol = index;
            state.dir = 1;
          }
          Array.prototype.forEach.call(headCells, function (h) { h.removeAttribute('data-sort'); });
          th.setAttribute('data-sort', state.dir > 0 ? 'asc' : 'desc');
          applySort();
        });
      });
    }

    applyFilter();
  }

  function init() {
    Array.prototype.forEach.call(document.querySelectorAll('.table-wrap > table'), enhance);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
