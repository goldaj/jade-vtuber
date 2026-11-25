# Jade r21 — reprise au 25 novembre 2026

Le propriétaire a donné le feu vert à la production le 25 novembre et a confié la recette visuelle à Codex. [Plan directeur](MODEL2D_MASTER_PLAN.md) · [État de reprise](MODEL2D_CODEX_STATE.md)

## Base à ouvrir

- **Candidat de finition v37.** Dans le projet local sur D:, ouvrir `assets/live2d/r21_professional_art/working_v005/Jade_r21_v37_bouche_centree.cmo3`. Le paquet natif SDK 5.0 correspondant est chargé dans VTube Studio sous le nom `Jade_r21_v37`. Le v37 reprend la restauration graphique du v36 et corrige le centrage de la bouche au repos et en ouverture.
- **Point de départ v32.** `Jade_r21_v32.cmo3`, SHA-256 `C26C686DBF6A9DE08FBAD281088118A6EDF2CFBDBDCEC993058C039F81294D1C`. Il réunit l’atlas recalé sur le dessin v31, deux tuiles de masque d’yeux et les contrôles de pointes d’oreilles `ParamJadeEarTwitchL/R`.
- **Référence native v31.** [Checkpoint aux sous-peintures d’épaules](assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3), SHA-256 `39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C`. Le v30 et le candidat r02 restent des points de retour. Les neuf mèches avant et les commandes corporelles sont déjà présentes dans la lignée v31/v32.
- **Annexes locales.** Dans le même dossier d’art r21, `vts_staging/Jade_r21_idle.motion3.json` boucle sur 36 s avec souffle, tête, appuis et oreilles. `vts_staging/expressions/` contient Smile et Sad. `Jade_r21_hair_candidate_r01.physics3.json` couvre les neuf sorties des mèches avant et de l’ahoge. Prévoir la calibration et vérifier la priorité entre Angle Z de l’idle et le suivi.
- **Sources d’art et secours.** Conserver les [sources éditables du guide](MODEL_GUIDE.md#sources-actuelles), le [maître RGBA](assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png) et le [r20 de secours](runtime-installed/Jade_professional_r20_idle_complete/). Les copies KRA/PSD restent à synchroniser avec le plein pied, les épaules et les cheveux présents dans le CMO3.

## Suite de la finition

Reprendre les marques près des cils, les franges chromatiques des cheveux et la jonction du menton et du col aux grandes inclinaisons. Contrôler ensuite les combinaisons avec la physique et les expressions. La parole continue et les 14 motions du plan restent à recetter.

Utiliser Cubism PRO 5.3.05 pour l’export natif SDK 5.0 et l’API VTube Studio pour charger et poser le modèle. PSD2Live sert aux essais de découpe, de physique et de courbes sur une copie. [Relais yeux](reports/Jade_r21_relais_Astra_yeux.md)

## Historique et récupération

Des essais d’atlas antérieurs faisaient disparaître des pièces ou modifiaient les contours. Le correctif a recalé les textures sur le rendu v31 et représente le départ du v32. Les essais de masque, de fondu et d’alignement antérieurs documentent le clignement. Les publications historiques de ce chantier, dont le relais atlas `4d866b1`, précèdent le v32 et ne constituent pas une recette VTube Studio.

[Suivi daté avant cette reprise](https://github.com/goldaj/jade-vtuber/blob/c3c17b0629471dc3f04bb9c9ca956aed434c5a64/jade-modeling/CONTINUATION.md) · [Passation courante](../docs/operations/handoffs/2026-11-25-codex-jade-r21-reprise.md)
