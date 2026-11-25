# Jade r21 — reprise au 25 novembre 2026

Le [plan directeur](MODEL2D_MASTER_PLAN.md) est approuvé. La documentation, le tri prudent et le chargement des copies sont autorisés. **Attendre le nouveau feu vert du propriétaire avant les retouches, l’export et la recette.** Le propriétaire observera les validations en direct, sans ScreenToGif. [État de reprise](MODEL2D_CODEX_STATE.md)

## Base à ouvrir

- **Candidat local v32.** Depuis le projet Jade sur D:, `assets/live2d/r21_professional_art/working_v005/Jade_r21_v32.cmo3`. 62 650 660 octets, SHA-256 `C26C686DBF6A9DE08FBAD281088118A6EDF2CFBDBDCEC993058C039F81294D1C`. Il réunit l’atlas recalé sur le dessin v31, des tuiles opaques pour les deux masques d’yeux et deux contrôles de pointes normales `ParamJadeEarTwitchL/R`. Préparer une copie de travail.
- **Référence native v31.** [Checkpoint aux sous-peintures d’épaules](assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3), SHA-256 `39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C`. Le v30 et le candidat r02 restent des points de retour. Les neuf mèches avant et les commandes corporelles sont déjà présentes dans la lignée v31/v32.
- **Annexes locales.** Dans le même dossier d’art r21, `vts_staging/Jade_r21_idle.motion3.json` boucle sur 36 s avec souffle, tête, appuis et oreilles. `vts_staging/expressions/` contient Smile et Sad. `Jade_r21_hair_candidate_r01.physics3.json` couvre les neuf sorties des mèches avant et de l’ahoge. Prévoir la calibration et vérifier la priorité entre Angle Z de l’idle et le suivi.
- **Sources d’art et secours.** Conserver les [sources éditables du guide](MODEL_GUIDE.md#sources-actuelles), le [maître RGBA](assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png) et le [r20 de secours](runtime-installed/Jade_professional_r20_idle_complete/). Les copies KRA/PSD restent à synchroniser avec le plein pied, les épaules et les cheveux présents dans le CMO3.

## Premier jalon après feu vert

La copie `Jade_r21_travail.cmo3` est ouverte dans **Cubism PRO 5.3.05** et reconnue par Turboism. Après le feu vert, contrôler l’ourlet, les jambes et les chaussures en vue atlas, plus les vrais yeux fermés et l’ouverture de la bouche. Sur le candidat intermédiaire recalé, l’ourlet festonné a déjà été observé dans les deux vues de Cubism. Le v32 complet, son clignement et l’export VTube Studio restent à valider.

Une fois le plein pied utilisable, exporter le paquet r21 et ses annexes puis ouvrir le candidat dans son propre dossier VTube Studio. Garder le double cil éventuel à la quasi-fermeture dans le lot de finition des yeux. Utiliser PSD2Live sur un projet séparé pour les essais de découpe, de physique et de courbes. [Relais yeux](reports/Jade_r21_relais_Astra_yeux.md)

## Historique et récupération

Des essais d’atlas antérieurs faisaient disparaître des pièces ou modifiaient les contours. Le correctif a recalé les textures sur le rendu v31 et représente le départ du v32. Les essais de masque, de fondu et d’alignement antérieurs documentent le clignement. Les publications historiques de ce chantier, dont le relais atlas `4d866b1`, précèdent le v32 et ne constituent pas une recette VTube Studio.

[Suivi daté avant cette reprise](https://github.com/goldaj/jade-vtuber/blob/c3c17b0629471dc3f04bb9c9ca956aed434c5a64/jade-modeling/CONTINUATION.md) · [Passation courante](../docs/operations/handoffs/2026-11-25-codex-jade-r21-reprise.md)
