'use strict';
(() => {
  const select = document.querySelector('#settings-section');
  if (select) {
    document.body.classList.add('settings-enhanced');
    select.closest('label').hidden = false;
    select.addEventListener('change', () => { window.location.assign(select.value); });
  }
  const list = document.querySelector('[data-aisle-order]');
  if (!list) return;
  const feedback = document.querySelector('#aisle-feedback');
  let dragged;
  function announce(row) {
    feedback.textContent = `${row.querySelector('label span').textContent}: Position ${[...list.children].indexOf(row) + 1} von ${list.children.length}.`;
  }
  list.addEventListener('click', event => {
    const button = event.target.closest('[data-move]');
    if (!button) return;
    const row = button.closest('li');
    const neighbour = button.dataset.move === 'up' ? row.previousElementSibling : row.nextElementSibling;
    if (!neighbour) return;
    if (button.dataset.move === 'up') list.insertBefore(row, neighbour);
    else list.insertBefore(neighbour, row);
    button.focus({preventScroll: true}); announce(row);
    row.dispatchEvent(new Event('change', {bubbles: true}));
  });
  list.addEventListener('dragstart', event => {
    // Dragging text inside a field must not start a row move.
    if (event.target.closest('input,button,select')) { event.preventDefault(); return; }
    dragged = event.target.closest('li');
    if (dragged && event.dataTransfer) { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', dragged.dataset.categoryId); }
  });
  list.addEventListener('dragover', event => {
    const target = event.target.closest('li');
    if (!dragged || !target || target === dragged) return;
    event.preventDefault();
    const box = target.getBoundingClientRect();
    list.insertBefore(dragged, event.clientY < box.top + box.height / 2 ? target : target.nextSibling);
  });
  list.addEventListener('drop', event => { if (dragged) { event.preventDefault(); announce(dragged); dragged.dispatchEvent(new Event('change', {bubbles:true})); } dragged = null; });
  list.addEventListener('dragend', () => { dragged = null; });
})();
