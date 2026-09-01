/* Rosace des proximités : délégation d'événements sur document.body pour
 * fonctionner même après un remplacement du panneau par htmx (hx-swap
 * outerHTML sur #score-panel). Clic ou clavier (Entrée/Espace) sur un
 * secteur ou le centre met à jour le champ caché #f-fonction et déclenche
 * un événement 'change' natif : htmx (rafraîchit le panneau) et map.js
 * (rafraîchit les équipements affichés) écoutent tous les deux ce même
 * événement, sans état dupliqué.
 */
(function () {
  function setFonction(value) {
    var input = document.getElementById("f-fonction");
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function handleActivate(target) {
    var sector = target.closest(".rosace-sector, .rosace-center");
    if (!sector) return;
    var current = document.getElementById("f-fonction").value;
    var next = sector.classList.contains("rosace-center") ? "" : sector.dataset.fonction;
    setFonction(current === next ? "" : next);
  }

  document.body.addEventListener("click", function (e) {
    handleActivate(e.target);
  });

  document.body.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var sector = e.target.closest(".rosace-sector, .rosace-center");
    if (!sector) return;
    e.preventDefault();
    handleActivate(e.target);
  });
})();
