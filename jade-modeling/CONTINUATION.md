# Jade r21 — reprise au 25 novembre 2026

Le propriétaire a donné le feu vert à la production le 25 novembre et a confié la recette visuelle à Codex. [Plan directeur](MODEL2D_MASTER_PLAN.md) · [État de reprise](MODEL2D_CODEX_STATE.md)

## Base à ouvrir

- **Livraison v45.1 en service.** Ouvrir le [guide de la livraison téléchargeable](assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/LISEZMOI.md). Le sous-dossier `Jade_r21_v45` est installable. `Sources` réunit le KRA, le PSD et le manifeste des plaques. `Edition` conserve le CMO3 et l’atelier des gestes. `CALIBRATION.md` donne les réglages et la recette sur le profil opérateur.

- **Candidat de finition v38.** Dans le projet local sur D:, ouvrir `assets/live2d/r21_professional_art/working_v005/Jade_r21_v38_portrait.cmo3`. Le paquet natif SDK 5.0 porte le nom `Jade_r21_v38`. Le clignement, les raccords menton–cou–épaules et le détourage des mèches au col ont passé la revue croisée en portrait. Le v37 conserve le précédent jalon de centrage de la bouche.
- **Point de départ v32.** `Jade_r21_v32.cmo3`, SHA-256 `C26C686DBF6A9DE08FBAD281088118A6EDF2CFBDBDCEC993058C039F81294D1C`. Il réunit l’atlas recalé sur le dessin v31, deux tuiles de masque d’yeux et les contrôles de pointes d’oreilles `ParamJadeEarTwitchL/R`.
- **Référence native v31.** [Checkpoint aux sous-peintures d’épaules](assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3), SHA-256 `39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C`. Le v30 et le candidat r02 restent des points de retour. Les neuf mèches avant et les commandes corporelles sont déjà présentes dans la lignée v31/v32.
- **Annexes locales.** Dans le même dossier d’art r21, `vts_staging/Jade_r21_idle.motion3.json` boucle sur 36 s avec souffle, tête, appuis et oreilles. `vts_staging/expressions/` contient Smile et Sad. `Jade_r21_hair_candidate_r01.physics3.json` couvre les neuf sorties des mèches avant et de l’ahoge. Prévoir la calibration et vérifier la priorité entre Angle Z de l’idle et le suivi.
- **Sources d’art et secours.** Conserver les [sources éditables du guide](MODEL_GUIDE.md#sources-actuelles), le [maître RGBA](assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png) et le [r20 de secours](runtime-installed/Jade_professional_r20_idle_complete/). Les copies KRA/PSD restent à synchroniser avec le plein pied, les épaules et les cheveux présents dans le CMO3.

## Suite de la finition

Les quatorze motions, les sources réconciliées et le paquet final sont livrés. La calibration en situation sur le modèle est acceptée. Le câblage automatique dans l’application précède la dernière recette intégrée. [Passation de livraison](../docs/operations/handoffs/2026-11-25-codex-livraison-modele-jade.md)

## Piloter une réplique dans VTube Studio

Charger `Jade_r21_v45` et lancer `python tools/vts_jade_performance.py` depuis le dossier de modélisation. Le lecteur audio envoie un objet JSON par ligne au rythme de la lecture. Par exemple, après `{"type":"start","id":"r1","expression":"Smile"}`, il envoie des niveaux comme `{"type":"mouth","id":"r1","value":0.55}`. À la coupure, envoyer `{"type":"interrupt","id":"r1"}` puis donner à la réplique suivante un nouvel identifiant. Une fin normale utilise `{"type":"end","id":"r1"}`. La commande `{"type":"stop"}` remet le visage au repos et termine le pilote. Le branchement sur la lecture audio du bot est suivi en DEV-001. [Pilote de parole](tools/vts_jade_performance.py)

## Jouer les quatorze gestes

Les 14 mouvements sont accessibles dans le profil VTube Studio `Jade_r21_v45`. L’ordre dans chaque groupe est A puis B. Pour jouer une variante depuis le dossier du projet, lancer par exemple `python tools/vts_model_switch.py --hotkey Jade_playful_A`. Les actions du profil utilisent « Play Animation » et relâchent la pose en fin de lecture. Pour reconstruire les raccourcis sur un autre poste, associer chaque fichier de la racine du paquet à une action « Play Animation », sans maintien de la dernière pose.

| Intention | Variante A | Variante B |
| --- | --- | --- |
| `neutral` | [Reprendre son appui](assets/live2d/r21_professional_art/intent_motions/Jade_neutral_A.motion3.json) (4,12 s) | [Saluer d’un signe](assets/live2d/r21_professional_art/intent_motions/Jade_neutral_B.motion3.json) (3,28 s) |
| `playful` | [Feinte de côté](assets/live2d/r21_professional_art/intent_motions/Jade_playful_A.motion3.json) (3,46 s) | [Balancement complice](assets/live2d/r21_professional_art/intent_motions/Jade_playful_B.motion3.json) (3,86 s) |
| `excited` | [Élan vers le haut](assets/live2d/r21_professional_art/intent_motions/Jade_excited_A.motion3.json) (3,28 s) | [Se tourner pour partager](assets/live2d/r21_professional_art/intent_motions/Jade_excited_B.motion3.json) (4,12 s) |
| `curious` | [Tendre l’oreille](assets/live2d/r21_professional_art/intent_motions/Jade_curious_A.motion3.json) (4,56 s) | [Chercher puis comprendre](assets/live2d/r21_professional_art/intent_motions/Jade_curious_B.motion3.json) (3,72 s) |
| `tender` | [La joue vers l’épaule](assets/live2d/r21_professional_art/intent_motions/Jade_tender_A.motion3.json) (4,84 s) | [Confidence à mi-voix](assets/live2d/r21_professional_art/intent_motions/Jade_tender_B.motion3.json) (4,12 s) |
| `reassuring` | [Oui, je suis là](assets/live2d/r21_professional_art/intent_motions/Jade_reassuring_A.motion3.json) (3,90 s) | [Une présence tranquille](assets/live2d/r21_professional_art/intent_motions/Jade_reassuring_B.motion3.json) (5,04 s) |
| `serious` | [Se redresser](assets/live2d/r21_professional_art/intent_motions/Jade_serious_A.motion3.json) (3,94 s) | [Marquer le propos](assets/live2d/r21_professional_art/intent_motions/Jade_serious_B.motion3.json) (3,57 s) |

Pour l’édition sur une autre copie du rig v43, chaque fichier `Jade_<intention>.psd2live-motions.json` fournit les deux clips à envoyer à `motion.put`. Chaque fichier conserve les temps de clés, les tangentes et les fondus. [Courbes Cubism et PSD2Live](assets/live2d/r21_professional_art/intent_motions/)

Utiliser Cubism PRO 5.3.05 pour l’export natif SDK 5.0 et l’API VTube Studio pour charger et poser le modèle. PSD2Live sert aux essais de découpe, de physique et de courbes sur une copie. [Relais yeux](reports/Jade_r21_relais_Astra_yeux.md)

## Historique et récupération

Des essais d’atlas antérieurs faisaient disparaître des pièces ou modifiaient les contours. Le correctif a recalé les textures sur le rendu v31 et représente le départ du v32. Les essais de masque, de fondu et d’alignement antérieurs documentent le clignement. Les publications historiques de ce chantier, dont le relais atlas `4d866b1`, précèdent le v32 et ne constituent pas une recette VTube Studio.

[Suivi daté avant cette reprise](https://github.com/goldaj/jade-vtuber/blob/c3c17b0629471dc3f04bb9c9ca956aed434c5a64/jade-modeling/CONTINUATION.md) · [Passation courante](../docs/operations/handoffs/2026-11-25-codex-jade-r21-reprise.md)
