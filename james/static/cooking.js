'use strict';
(() => {
  const list = document.getElementById('recipe-ingredients');
  const button = document.getElementById('add-ingredient');
  const template = document.getElementById('ingredient-template');
  if (!list || !button || !template) return;
  const refresh = () => {
    list.querySelectorAll('[data-remove-ingredient]').forEach(b => { b.hidden = list.children.length <= 1; });
    button.disabled = list.children.length >= 100;
  };
  button.hidden = false;
  button.addEventListener('click', () => {
    if (list.children.length >= 100) return;
    list.append(template.content.cloneNode(true));
    refresh();
    list.lastElementChild.querySelector('input').focus();
  });
  list.addEventListener('click', event => {
    const remove = event.target.closest('[data-remove-ingredient]');
    if (!remove || list.children.length <= 1) return;
    remove.closest('fieldset').remove();
    refresh();
  });
  refresh();
})();
