# Jade r21 — reprise au 25 novembre 2026

Le propriétaire a donné le feu vert à la production le 25 novembre et a confié la recette visuelle à Codex. [Plan directeur](MODEL2D_MASTER_PLAN.md) · [État de reprise](MODEL2D_CODEX_STATE.md)

## Base à ouvrir

- **v41 en service.** Ouvrir `assets/live2d/r21_professional_art/working_v005/Jade_r21_v41_cheveux.cmo3` dans le projet local. Le paquet `Jade_r21_v41` conserve les appuis et l’ourlet du v40. [État et recette](MODEL2D_CODEX_STATE.md).
- **Candidat de finition v38.** Dans le projet local sur D:, ouvrir `assets/live2d/r21_professional_art/working_v005/Jade_r21_v38_portrait.cmo3`. Le paquet natif SDK 5.0 porte le nom `Jade_r21_v38`. Le clignement, les raccords menton–cou–épaules et le détourage des mèches au col ont passé la revue croisée en portrait. Le v37 conserve le précédent jalon de centrage de la bouche.
- **Point de départ v32.** `Jade_r21_v32.cmo3`, SHA-256 `C26C686DBF6A9DE08FBAD281088118A6EDF2CFBDBDCEC993058C039F81294D1C`. Il réunit l’atlas recalé sur le dessin v31, deux tuiles de masque d’yeux et les contrôles de pointes d’oreilles `ParamJadeEarTwitchL/R`.
- **Référence native v31.** [Checkpoint aux sous-peintures d’épaules](assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3), SHA-256 `39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C`. Le v30 et le candidat r02 restent des points de retour. Les neuf mèches avant et les commandes corporelles sont déjà présentes dans la lignée v31/v32.
- **Annexes locales.** Dans le même dossier d’art r21, `vts_staging/Jade_r21_idle.motion3.json` boucle sur 36 s avec souffle, tête, appuis et oreilles. `vts_staging/expressions/` contient Smile et Sad. `Jade_r21_hair_candidate_r01.physics3.json` couvre les neuf sorties des mèches avant et de l’ahoge. Prévoir la calibration et vérifier la priorité entre Angle Z de l’idle et le suivi.
- **Sources d’art et secours.** Conserver les [sources éditables du guide](MODEL_GUIDE.md#sources-actuelles), le [maître RGBA](assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png) et le [r20 de secours](runtime-installed/Jade_professional_r20_idle_complete/). Les copies KRA/PSD restent à synchroniser avec le plein pied, les épaules et les cheveux présents dans le CMO3.

## Suite de la finition

Étape 6, expressions et idle de 36 s. Régler le retour au repos après la parole et les interruptions, en combinant suivi, clignement, souffle, appuis et tressautements d’oreilles. Réutiliser la physique du paquet VTS qui contient les quatorze groupes. L’atelier PSD2Live en importe douze, transforme l’axe vertical en horizontal dans les huit groupes avant et refuse la double entrée du même paramètre pour le sommet et la masse arrière. La synchronisation complète des KRA/PSD et les 14 motions restent au plan.

Utiliser Cubism PRO 5.3.05 pour l’export natif SDK 5.0 et l’API VTube Studio pour charger et poser le modèle. PSD2Live sert aux essais de découpe, de physique et de courbes sur une copie. [Relais yeux](reports/Jade_r21_relais_Astra_yeux.md)

## Historique et récupération

Des essais d’atlas antérieurs faisaient disparaître des pièces ou modifiaient les contours. Le correctif a recalé les textures sur le rendu v31 et représente le départ du v32. Les essais de masque, de fondu et d’alignement antérieurs documentent le clignement. Les publications historiques de ce chantier, dont le relais atlas `4d866b1`, précèdent le v32 et ne constituent pas une recette VTube Studio.

[Suivi daté avant cette reprise](https://github.com/goldaj/jade-vtuber/blob/c3c17b0629471dc3f04bb9c9ca956aed434c5a64/jade-modeling/CONTINUATION.md) · [Passation courante](../docs/operations/handoffs/2026-11-25-codex-jade-r21-reprise.md)
