'use strict';
const planText = document.querySelector('#plan-copy');
const planStatus = document.querySelector('#plan-copy-status');
document.querySelector('#copy-plan')?.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(planText.value);
    planStatus.textContent = 'Liste kopiert.';
  } catch {
    planText.select();
    planStatus.textContent = 'Bitte die markierte Liste manuell kopieren.';
  }
});
const sharePlan = document.querySelector('#share-plan');
if (sharePlan && navigator.share) {
  sharePlan.hidden = false;
  sharePlan.addEventListener('click', async () => {
    try { await navigator.share({title: 'Einkauf mit James', text: planText.value}); }
    catch (error) { if (error.name !== 'AbortError') planStatus.textContent = 'Teilen nicht moeglich. Du kannst die Liste kopieren.'; }
  });
}
