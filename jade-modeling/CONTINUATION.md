# Jade r21 — reprise au 25 novembre 2026

Le propriétaire a donné le feu vert à la production le 25 novembre et a confié la recette visuelle à Codex. [Plan directeur](MODEL2D_MASTER_PLAN.md) · [État de reprise](MODEL2D_CODEX_STATE.md)

## Base à ouvrir

- **v44 en service.** Le paquet local `assets/live2d/r21_professional_art/vts_export/Jade_r21_v44` ajoute les gestes Curious A et B. Son rig reste celui de `working_v005/Jade_r21_v43_parole.cmo3`, avec l’idle de 36 s, la bouche corrigée et les quinze groupes de physique. Les calques de bouche se trouvent dans `source_sync_v43_bouche/`. [État et recette](MODEL2D_CODEX_STATE.md)
- **Candidat de finition v38.** Dans le projet local sur D:, ouvrir `assets/live2d/r21_professional_art/working_v005/Jade_r21_v38_portrait.cmo3`. Le paquet natif SDK 5.0 porte le nom `Jade_r21_v38`. Le clignement, les raccords menton–cou–épaules et le détourage des mèches au col ont passé la revue croisée en portrait. Le v37 conserve le précédent jalon de centrage de la bouche.
- **Point de départ v32.** `Jade_r21_v32.cmo3`, SHA-256 `C26C686DBF6A9DE08FBAD281088118A6EDF2CFBDBDCEC993058C039F81294D1C`. Il réunit l’atlas recalé sur le dessin v31, deux tuiles de masque d’yeux et les contrôles de pointes d’oreilles `ParamJadeEarTwitchL/R`.
- **Référence native v31.** [Checkpoint aux sous-peintures d’épaules](assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3), SHA-256 `39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C`. Le v30 et le candidat r02 restent des points de retour. Les neuf mèches avant et les commandes corporelles sont déjà présentes dans la lignée v31/v32.
- **Annexes locales.** Dans le même dossier d’art r21, `vts_staging/Jade_r21_idle.motion3.json` boucle sur 36 s avec souffle, tête, appuis et oreilles. `vts_staging/expressions/` contient Smile et Sad. `Jade_r21_hair_candidate_r01.physics3.json` couvre les neuf sorties des mèches avant et de l’ahoge. Prévoir la calibration et vérifier la priorité entre Angle Z de l’idle et le suivi.
- **Sources d’art et secours.** Conserver les [sources éditables du guide](MODEL_GUIDE.md#sources-actuelles), le [maître RGBA](assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png) et le [r20 de secours](runtime-installed/Jade_professional_r20_idle_complete/). Les copies KRA/PSD restent à synchroniser avec le plein pied, les épaules et les cheveux présents dans le CMO3.

## Suite de la finition

L’étape 7 porte sur deux motions de corps par intention. La curiosité a ses deux variantes dans le v44. Restent les paires `neutral`, `playful`, `excited`, `tender`, `reassuring` et `serious`, ainsi que la synchronisation complète des KRA/PSD.

## Piloter une réplique dans VTube Studio

Charger `Jade_r21_v44` (ou le v43 pour la parole seule) et lancer `python tools/vts_jade_performance.py` depuis le dossier de modélisation. Le lecteur audio envoie un objet JSON par ligne au rythme de la lecture. Par exemple, après `{"type":"start","id":"r1","expression":"Smile"}`, il envoie des niveaux comme `{"type":"mouth","id":"r1","value":0.55}`. À la coupure, envoyer `{"type":"interrupt","id":"r1"}` puis donner à la réplique suivante un nouvel identifiant. Une fin normale utilise `{"type":"end","id":"r1"}`. La commande `{"type":"stop"}` remet le visage au repos et termine le pilote. Le branchement sur la lecture audio du bot est suivi en DEV-001. [Pilote de parole](tools/vts_jade_performance.py)

## Déclencher la curiosité dans VTube Studio

Sur le modèle v44 installé, les deux actions « Play Animation » lisent chacune une motion une fois. Depuis le dossier de modélisation, utiliser `python tools/vts_model_switch.py --hotkey Jade_curious_A` pour « Tendre l’oreille » ou `python tools/vts_model_switch.py --hotkey Jade_curious_B` pour « Chercher puis comprendre ». Les deux fichiers se trouvent à la racine du paquet VTS et dans le groupe `Curious` du `.model3.json`. Pour recréer ces actions sur un autre poste, associer chaque fichier à une action « Play Animation » et laisser désactivé le maintien de la dernière image. [Motions de Jade](assets/live2d/r21_professional_art/intent_motions/) · [Lecture des animations dans VTube Studio](https://github.com/DenchiSoft/VTubeStudio/wiki/Animations)

Pour retravailler les gestes dans PSD2Live sur le poste de Jade, ouvrir `working_v005/Jade_r21_v44_motions.psd2live` dans le dossier d’art r21 local. Pour les importer sur une autre copie du rig v43, envoyer chacun des deux clips à `motion.put` via le MCP en utilisant la révision courante de l’atelier. Le fichier d’édition conserve les temps des clés et les tangentes des courbes. [Source PSD2Live des deux gestes](assets/live2d/r21_professional_art/intent_motions/Jade_curious.psd2live-motions.json)

Utiliser Cubism PRO 5.3.05 pour l’export natif SDK 5.0 et l’API VTube Studio pour charger et poser le modèle. PSD2Live sert aux essais de découpe, de physique et de courbes sur une copie. [Relais yeux](reports/Jade_r21_relais_Astra_yeux.md)

## Historique et récupération

Des essais d’atlas antérieurs faisaient disparaître des pièces ou modifiaient les contours. Le correctif a recalé les textures sur le rendu v31 et représente le départ du v32. Les essais de masque, de fondu et d’alignement antérieurs documentent le clignement. Les publications historiques de ce chantier, dont le relais atlas `4d866b1`, précèdent le v32 et ne constituent pas une recette VTube Studio.

[Suivi daté avant cette reprise](https://github.com/goldaj/jade-vtuber/blob/c3c17b0629471dc3f04bb9c9ca956aed434c5a64/jade-modeling/CONTINUATION.md) · [Passation courante](../docs/operations/handoffs/2026-11-25-codex-jade-r21-reprise.md)
