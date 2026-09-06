# Jeu de tests — cas principaux

Complète la suite automatisée (`pytest tests/`). Les cas ci-dessous portent sur
l'interaction visuelle et se rejouent manuellement dans un navigateur, capture
d'écran à l'appui, avant chaque livraison.

Captures attendues dans `docs/captures/`, une par cas, nommée `cas-<n>.png`.

| # | Cas | Étapes | Résultat attendu |
|---|---|---|---|
| 1 | Marche 15 min, toute la ville | Ouvrir `/exploration` avec les filtres par défaut | Score pondéré et score brut affichés côte à côte ; radar sans note d'approximation ; carte avec choroplèthe et points d'équipements |
| 2 | Changement de mode | Mode = Vélo, Durée = 30 | Score, radar et carte se mettent à jour ; note d'approximation affichée sous le radar |
| 3 | Rosace, les 6 secteurs | Cliquer chaque secteur, puis le centre | Chaque clic filtre les équipements sur la fonction, passe le secteur à `aria-pressed="true"`, et met à jour le score **et le compteur d'équipements** ; les six fonctions donnent six nombres différents ; le centre réinitialise |
| 4 | Isochrone marche 15 min | Mode = Marche, Durée = 15, cliquer un équipement | Contour d'isochrone tracé autour de l'équipement |
| 5 | Isochrone hors marche 15 min | Mode = Voiture, cliquer un équipement | Aucune requête d'isochrone : pas de géométrie pour cette combinaison |
| 6 | Changement de territoire | Sélectionner un conseil de quartier | Titre du panneau, score, radar et compteur mis à jour ; la carte se limite aux équipements du quartier |
| 7 | Fiche quartier | `/quartiers/<id>` pour chaque quartier | Page individuelle avec carte de localisation, radar et score ; 404 propre sur identifiant inconnu |
| 8 | Accordéon détails | Cliquer « Voir les données détaillées » | Tableau masqué par défaut, affiché après clic |
| 9 | Navigation clavier | Tabulation jusqu'à un secteur de rosace, puis Entrée | Secteur atteignable au clavier ; Entrée équivaut au clic |
| 10 | Contraste | Passer les pages au WebAIM Contrast Checker | Texte courant ≥ 4.5:1, texte large ≥ 3:1 |
| 11 | Compteur et carte d'accord | Pour chaque combinaison de filtres, comparer le nombre affiché au nombre de points servis par `/api/equipements` | Les deux nombres sont égaux : ils viennent de la même fonction de filtrage |
| 12 | Périmètre du compteur | Filtres par défaut | Le compteur annonce les équipements de Sète, pas ceux de l'agglomération, et signale ceux sans fonction renseignée ainsi que ceux hors commune |
| 13 | Radar, fonction mise en évidence | Cliquer un secteur de la rosace | Sur le radar, l'axe correspondant est épaissi, son point agrandi et cerclé, son libellé en gras — vérifier que la distinction reste lisible en niveaux de gris |
| 14 | Radar, lecteur d'écran | Inspecter l'`aria-label` du radar | Il nomme la fonction mise en évidence, pas seulement les six valeurs |
