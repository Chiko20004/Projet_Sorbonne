/* Carte Leaflet : choroplèthe (grille/quartier), équipements filtrables par
 * la rosace/le niveau de proximité, isochrone marche-15 à la demande.
 * Écoute les mêmes événements 'change' du formulaire de filtres que htmx,
 * sans dupliquer l'état des filtres (lu directement depuis le DOM à chaque
 * rafraîchissement).
 */
(function () {
  // Doit rester synchronisé avec gosp/static/css/tokens.css et
  // gosp/services/presentation.py (échelle proposée, non normée).
  var SCORE_COLORS = {
    nodata: "#6b5866",
    0: "#c0392b",
    3: "#e07b39",
    5: "#e6c229",
    7: "#8bb84a",
    9: "#2f8f4e",
  };

  // Écriture française des nombres, comme le filtre `nombre` côté serveur :
  // les libellés de la carte doivent se lire comme le reste du site.
  function nombreFr(valeur, decimales) {
    if (valeur === null || valeur === undefined) return "—";
    return Number(valeur).toLocaleString("fr-FR", {
      minimumFractionDigits: decimales,
      maximumFractionDigits: decimales,
    });
  }

  function colorFor(score) {
    if (score === null || score === undefined) return SCORE_COLORS.nodata;
    if (score < 3) return SCORE_COLORS[0];
    if (score < 5) return SCORE_COLORS[3];
    if (score < 7) return SCORE_COLORS[5];
    if (score < 9) return SCORE_COLORS[7];
    return SCORE_COLORS[9];
  }

  var mapEl = document.getElementById("map");
  if (!mapEl || typeof L === "undefined") return;

  var map = L.map(mapEl, { scrollWheelZoom: true }).setView([43.405, 3.693], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  var choroplethLayer = L.geoJSON(null, {
    style: function (feature) {
      var p = feature.properties;
      return {
        color: "rgba(36,18,32,0.35)",
        weight: 1,
        fillColor: p.peuplee === false ? SCORE_COLORS.nodata : colorFor(p.score),
        fillOpacity: p.peuplee === false ? 0.25 : 0.65,
      };
    },
    onEachFeature: function (feature, layer) {
      var p = feature.properties;
      var label = p.nom || ("Cellule " + p.id);
      var scoreTxt = p.score !== null && p.score !== undefined
        ? nombreFr(p.score, 2) + " / 10"
        : "donnée indisponible";
      var habTxt = p.population ? " · " + nombreFr(p.population, 0) + " hab." : "";
      layer.bindTooltip(label + " — " + scoreTxt + habTxt);
    },
  }).addTo(map);

  var equipementsLayer = L.geoJSON(null, {
    pointToLayer: function (feature, latlng) {
      var p = feature.properties;
      return L.circleMarker(latlng, {
        radius: 5,
        color: "#0d0b1a",
        weight: 1,
        fillColor: "#c9a0f2",
        fillOpacity: 0.9,
      });
    },
    onEachFeature: function (feature, layer) {
      var p = feature.properties;
      var html = "<strong>" + (p.nom || p.libelle_typequ) + "</strong><br>" + p.libelle_typequ;
      layer.bindPopup(html);
      layer.on("click", function () {
        loadIsochroneIfAvailable(p.uid, p.source);
      });
    },
  }).addTo(map);

  var isochroneLayer = L.geoJSON(null, {
    style: function (feature) {
      // Un contour issu d'un identifiant ambigu fusionne deux équipements sans
      // rapport. On le trace en gris et sans remplissage, pour qu'il ne se lise
      // pas comme une isochrone fiable.
      if (feature.properties.geometrie_fusionnee) {
        return { color: "#8c8494", weight: 2, fill: false, dashArray: "2 5" };
      }
      return { color: "#6f8bff", weight: 2, fillColor: "#6f8bff", fillOpacity: 0.12, dashArray: "4 3" };
    },
    onEachFeature: function (feature, layer) {
      if (feature.properties.geometrie_fusionnee) {
        layer.bindTooltip(
          "Contour non fiable : les données sources ont fusionné cet équipement " +
          "avec un autre portant le même identifiant."
        );
      }
    },
  }).addTo(map);

  function currentFilters() {
    var form = document.getElementById("filters-form");
    var data = new FormData(form);
    return {
      mode: data.get("mode"),
      duree: data.get("duree"),
      unite: data.get("unite"),
      niveau: data.get("niveau"),
      fonction: data.get("fonction"),
      territoire: data.get("territoire"),
    };
  }

  function refreshChoropleth() {
    var f = currentFilters();
    var qs = new URLSearchParams({ unite: f.unite, mode: f.mode, duree: f.duree });
    fetch("/api/map-layer?" + qs.toString())
      .then(function (r) { return r.json(); })
      .then(function (geojson) {
        choroplethLayer.clearLayers();
        choroplethLayer.addData(geojson);
      });
  }

  function refreshEquipements() {
    var f = currentFilters();
    // Le territoire part avec les autres filtres : la carte et le compteur du
    // panneau interrogent ainsi le même jeu, et ne peuvent pas diverger.
    var qs = new URLSearchParams();
    if (f.fonction) qs.set("fonction", f.fonction);
    if (f.niveau) qs.set("niveau", f.niveau);
    if (f.territoire) qs.set("territoire", f.territoire);
    fetch("/api/equipements?" + qs.toString())
      .then(function (r) { return r.json(); })
      .then(function (geojson) {
        equipementsLayer.clearLayers();
        equipementsLayer.addData(geojson);
        isochroneLayer.clearLayers();
      });
  }

  function loadIsochroneIfAvailable(equipementUid, source) {
    var f = currentFilters();
    isochroneLayer.clearLayers();
    if (f.mode !== "walking" || f.duree !== "15") return; // seule combinaison avec géométrie réelle
    // Le fichier d'isochrones couvre les 16 724 équipements BPE et aucun des 662
    // équipements OSM : inutile de demander une géométrie qui n'existe pas.
    if (source !== "bpe") return;
    // L'uid part tel quel : c'est lui qui identifie l'équipement dans le
    // GeoPackage. Retirer son préfixe ramènerait l'ambiguïté qu'il corrige.
    fetch("/api/isochrone/" + encodeURIComponent(equipementUid))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (feature) {
        if (feature) isochroneLayer.addData(feature);
      })
      .catch(function () {});
  }

  var form = document.getElementById("filters-form");
  form.addEventListener("change", function () {
    refreshChoropleth();
    refreshEquipements();
  });

  refreshChoropleth();
  refreshEquipements();
})();
