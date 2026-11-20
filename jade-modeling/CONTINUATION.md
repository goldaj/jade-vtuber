# Jade r21 — reprise

**Objectif :** Jade Live2D professionnelle en plein pied dans VTube Studio, sans modernisation de l’application. Travailler sur D:, conserver Cubism PRO 5.2.03 sans mise à jour. Ne pas écraser les checkpoints.

**Terminé :** v31 conserve le corps complet, neuf mèches et les sous-peintures d’épaules. Le candidat d’atlas réunit 59 images utilisées par 78 ArtMeshes sur deux pages de 4096×4096, à l’échelle 1:1. Les cinq pièces du bas du corps et les deux sous-peintures ont chacune une image recadrée. Le maître original reste embarqué ; seule sa zone utile aux douze maillages concernés est dupliquée et remappée. La comparaison hors ligne a contrôlé les 78 maillages, les pixels de chaque placement et la conservation de la géométrie.

**En cours :** [ART-003, atlas plein pied](../docs/backlog/04-PRODUCTION-2D.md). Le candidat n’est pas un export et le rendu Cubism/VTS n’est pas validé. r20 reste le dernier paquet VTS conservé.

**Prochaine action exacte :** ouvrir le candidat par son empreinte dans la session Cubism PRO existante. Basculer entre images source et atlas sans recréer l’atlas ; vérifier la même pose neutre du sommet de la tête aux deux chaussures, puis les raccords épaules/cheveux. Si conforme, exporter dans un dossier r21 distinct du paquet r20 et vérifier dans VTube Studio. Ne pas promouvoir en cas de défaut.

**Fichiers importants :**

- Checkpoint v31 : `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3`, SHA-256 `39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C`.
- Intermédiaire recadré reproductible : SHA-256 `0DF71AF75A6B8C55A1E3ADF6D53CBC6DB3F206EF704D5B079802C8D83D1B9920`. Candidat avec atlas : SHA-256 `CFD67A576F780750F9B017AD27D89D743C289C2E453364F5B88A77EF40977A65`. Seul le v31 est publié comme binaire dans ce lot ; les outils reconstruisent les dérivés sur D:.
- [Plan professionnel](PLAN_QUALITE_PRO_20261113.md), [plan du modèle](PLAN_MODELE_JADE.md), [passation atlas](../docs/operations/handoffs/2026-11-20-codex-art003-atlas.md), [relais yeux](reports/Jade_r21_relais_Astra_yeux.md).

**Vérifications :** `python jade-modeling/verify_assets.py`, puis les [trois commandes de reconstruction et de contrôle](../docs/operations/handoffs/2026-11-20-codex-art003-atlas.md#reconstruction). Le contrôle mathématique des textures ne remplace pas le contrôle de l’éditeur ou du joueur.

**Décisions / limites :** ne pas utiliser l’ancien essai `image_split_r01` comme base. Préserver v30, r02, v31, les vrais sprites fermés, l’iris non aplati et les oreilles normales pour Surprise. Raccords aux poses combinées, clignement près de zéro, synchro KRA/PSD, physique r21, expressions, calibration et recette animée restent à finir. Ne pas régénérer les filtres du PSD historique ni recopier la physique r20 ; ScreenToGif uniquement pour la recette finale.
