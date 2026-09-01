# Guide utilisateur — GOSP Sète

## 1. Prise en main

Le site comporte 5 pages, accessibles depuis le menu en haut de chaque page :

- **Accueil** — présentation du GOSP, de la Chaire ETI et du contexte de Sète.
- **Exploration interactive** — l'outil cartographique : rosace, radar, score
  et carte.
- **Méthodologie** — la formule du score HQVS, les choix de conception et
  leurs limites.
- **Fiches quartier** — une page par conseil de quartier (7 au total).
- **Documentation / Aide** — cette page.

## 2. La page Exploration

### Les filtres

En haut de la page, cinq filtres agissent ensemble sur le score, le radar et
la carte :

| Filtre | Effet |
|---|---|
| **Territoire** | "Toute la ville" ou un conseil de quartier précis — change les chiffres affichés et centre la carte |
| **Mode de transport** | Marche, vélo ou voiture |
| **Durée** | 15 ou 30 minutes |
| **Unité spatiale** | Granularité de la carte : grille 200 m (recommandée), grille 50 m (plus fine), ou conseils de quartier |
| **Niveau de proximité** | Filtre les équipements affichés : local, intermédiaire, ou centralité |

Chaque changement de filtre met à jour le panneau de score, le radar et la
carte automatiquement — pas besoin de valider ou de recharger la page.

### La rosace

La rosace (à gauche, sous le score) affiche les 6 fonctions sociales sous
forme de pétales colorés selon leur score. **Cliquer un secteur** filtre les
équipements affichés sur la carte à cette seule fonction, et met le secteur
en évidence. Cliquer le même secteur à nouveau, ou le **centre** de la
rosace, réinitialise le filtre. Utilisable au clavier : tabulation pour
atteindre un secteur, puis Entrée ou Espace pour l'activer.

### Le radar

Le radar affiche les mêmes 6 scores sous forme de graphique en toile
d'araignée, sur une échelle unique de 0 à 10 — cohérente avec le score
affiché juste au-dessus (contrairement au prototype précédent). En marche
15 minutes, les valeurs sont directement issues des données. Pour les autres
modes/durées, une note sous le radar indique qu'il s'agit d'une
approximation — voir la page Méthodologie pour le détail du calcul.

### Le score

Deux chiffres sont affichés : le **score pondéré** (qui tient compte de la
population de chaque zone — une zone dense pèse plus qu'une zone peu
peuplée) et le **score brut** (moyenne simple, pour comparaison). Un
code couleur (rouge à vert) accompagne chaque score, avec la légende visible
sous la carte.

### La carte

La carte affiche une choroplèthe (zones colorées par score) selon l'unité
spatiale choisie, plus les équipements sous forme de points. **Cliquer un
équipement** ouvre une info-bulle et, si le mode "Marche 15 min" est
sélectionné, affiche le contour de sa zone d'accessibilité réelle
(isochrone) — la seule combinaison mode/durée pour laquelle cette géométrie
est disponible dans les données.

### Détails masqués

Sous le radar, un bouton "Détails par fonction (tableau)" affiche, sur
demande, un tableau chiffré complet — masqué par défaut pour ne pas
surcharger la page.

## 3. Export

Chaque fiche quartier (menu "Fiches quartier") est une page autonome,
imprimable directement depuis le navigateur (Ctrl/Cmd+P) pour un export PDF
simple — utile pour partager le score d'un quartier sans capture d'écran.
