// Week-cell breakdowns (<details class="cell-details">) open as a floating window beside the cell,
// so the table does not move. One window is open at a time. It closes with the X button, Escape,
// a click outside, or when its cell is scrolled out of view.
// Without this script the breakdown still opens inside the cell.
(function () {
  'use strict';

  var GAP = 8; // space between the window, its cell and the screen edges
  var CLOSE_LABEL = (document.documentElement.lang || 'he') === 'he' ? 'סגור' : 'Close';
  var current = null; // the open <details>
  var instant = false; // open the next window without animation

  if (!document.querySelector('.cell-details')) return;
  document.documentElement.classList.add('has-popover');

  function panelOf(details) {
    return details.querySelector('.cell-breakdown');
  }

  function close(details, returnFocus) {
    details.open = false;
    panelOf(details).classList.remove('is-placed');
    if (current === details) current = null;
    if (returnFocus) details.querySelector('summary').focus();
  }

  // The part of the screen where a cell can be seen: the viewport, cut to the table's scroll box.
  function cellIsVisible(cell) {
    var c = cell.getBoundingClientRect();
    var wrap = cell.closest('.table-wrap');
    var w = wrap ? wrap.getBoundingClientRect() : { top: 0, left: 0, right: Infinity, bottom: Infinity };
    return c.bottom > Math.max(w.top, 0) && c.top < Math.min(w.bottom, window.innerHeight) &&
           c.right > Math.max(w.left, 0) && c.left < Math.min(w.right, window.innerWidth);
  }

  // Below the cell when it fits, otherwise on the side with more room; always inside the screen.
  function place(details) {
    var panel = panelOf(details);
    var cell = (details.closest('td') || details).getBoundingClientRect();
    var screenW = document.documentElement.clientWidth;
    var screenH = document.documentElement.clientHeight;

    panel.style.maxHeight = '';
    var width = panel.offsetWidth;
    var height = panel.offsetHeight;
    var below = screenH - cell.bottom - GAP * 2;
    var above = cell.top - GAP * 2;
    var openUp = height > below && above > below;
    var room = Math.max(openUp ? above : below, 120);
    height = Math.min(height, room);

    var centre = cell.left + cell.width / 2;
    var left = Math.max(GAP, Math.min(centre - width / 2, screenW - width - GAP));
    var top = openUp ? cell.top - GAP - height : cell.bottom + GAP;
    top = Math.max(GAP, Math.min(top, screenH - height - GAP));

    panel.style.maxHeight = room + 'px';
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
    // Grow from the cell, not from the middle of the window.
    panel.style.transformOrigin = (centre - left) + 'px ' + (openUp ? '100%' : '0');
  }

  function addCloseButton(panel) {
    if (panel.querySelector('.pop-close')) return;
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'pop-close';
    button.setAttribute('aria-label', CLOSE_LABEL);
    button.title = CLOSE_LABEL;
    button.textContent = '×';
    panel.insertBefore(button, panel.firstChild);
  }

  // Keyboard openings, and moving from one open window to another, appear at once.
  document.addEventListener('click', function (e) {
    var closer = e.target.closest('.pop-close');
    if (closer) {
      close(closer.closest('.cell-details'), e.detail === 0);
      return;
    }
    // Enter or Space reports no mouse clicks.
    if (e.target.closest('.cell-details > summary') && e.detail === 0) instant = true;
  });

  // "toggle" does not bubble, so listen while it travels down.
  document.addEventListener('toggle', function (e) {
    var details = e.target;
    if (!details.classList || !details.classList.contains('cell-details')) return;
    var panel = panelOf(details);
    if (!details.open) {
      panel.classList.remove('is-placed');
      if (current === details) current = null;
      return;
    }
    if (current && current !== details) close(current);
    current = details;
    addCloseButton(panel);
    panel.classList.toggle('no-motion', instant);
    instant = false;
    place(details);
    panel.classList.add('is-placed');
  }, true);

  document.addEventListener('pointerdown', function (e) {
    instant = false;
    if (!current || current.contains(e.target)) return;
    instant = Boolean(e.target.closest('.cell-details > summary'));
    close(current);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && current) close(current, true);
  });

  function follow(e) {
    if (!current) return;
    if (e && e.target.nodeType === 1 && panelOf(current).contains(e.target)) return;
    if (cellIsVisible(current.closest('td') || current)) place(current);
    else close(current);
  }
  window.addEventListener('scroll', follow, true);
  window.addEventListener('resize', function () { follow(); });
})();
