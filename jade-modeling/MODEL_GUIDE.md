# Jade — reprendre le modèle et les animations

Le [plan directeur approuvé](MODEL2D_MASTER_PLAN.md) gouverne la reprise r21 via Turboism et PSD2Live. Le [plan qualité du 13 novembre](PLAN_QUALITE_PRO_20261113.md) conserve le contexte artistique.

## Sources actuelles

La livraison Jade r21 contient le modèle VTube Studio v45.1 en pied et ses quatorze gestes, le profil mobile v49.1 et ses dix-huit gestes, ainsi que les sources Cubism, PSD2Live et KRA/PSD. [Guide de la livraison](assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/LISEZMOI.md)

Reprendre le mobile depuis [le CMO3 v49.1](assets/live2d/r21_professional_art/working_v005/Jade_r21_v49_1_visage_continu.cmo3) et le profil servi à la PWA. Le paquet r20 reste utilisé par le renderer autonome Windows tant que le raccordement du r21 sur ce poste est suivi dans DEV-001.

## Jalons antérieurs

Tous les chemins ci-dessous sont relatifs à ce dossier. Les fichiers binaires se
récupèrent avec `git lfs pull` ; `git lfs fsck` vérifie les objets locaux.

| Usage | Fichier ou dossier |
| --- | --- |
| Candidat de reprise v32, stocké sur D: hors du checkout | `assets/live2d/r21_professional_art/working_v005/Jade_r21_v32.cmo3` dans le projet local |
| Jalon natif r21, v30 | `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_back_hair_restore_v30.cmo3` |
| Candidat natif v31, raccords épaules partiels | `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3` |
| Candidat cheveux, pas encore validé comme jalon natif | `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_v30.TEST_hair_leaves_r02.cmo3` |
| Dernière source Krita conservée du rig artistique | `assets/live2d/r21_professional_art/working_v005/jade_art_v005_r21_rig_art_v2_face_complete_v9.kra` |
| PSD d'interchange du rig | `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_rig_only_v2.psd` |
| Maître graphique intact | `assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png` |
| Package animé r20 complet à restaurer | `runtime-installed/Jade_professional_r20_idle_complete/` |
| Tri initial | `INVENTORY.json` pour le relevé historique, `ASSET_MANIFEST.json` pour la sélection suivie |

Les sources KRA/PSD de ces anciens jalons ne sont pas synchronisées avec les derniers ajouts
plein pied et cheveux du CMO3 r21. Ne pas réimporter aveuglément le PSD dans le
dernier CMO3 : cela risquerait de réintroduire des éléments anciens. Les fichiers
`CONTINUATION.md` et `PLAN_MODELE_JADE.md` décrivent les limites et la suite exacte.

Le v31 fournit la référence native du dessin et du rig. Le v32 local en reprend le corps, avec l’atlas recalé, deux textures de masque dédiées et des contrôles d’oreilles. Le v30 et le r02 restent disponibles comme jalons précédents. Les composants source du bas du corps, des épaules, des yeux et de la bouche sont conservés.

## Restaurer le paquet historique r20

1. Installer VTube Studio séparément et quitter l'application avant la copie.
2. Récupérer les objets LFS. Vérifier la présence de `Jade.moc3`, des fichiers de
   textures, de `Jade.model3.json`, `Jade.physics3.json`, des expressions et des
   fichiers `*.motion3.json` dans le package r20.
3. Copier tout le dossier `runtime-installed/Jade_professional_r20_idle_complete`
   dans un nouveau sous-dossier de `VTube Studio_Data/StreamingAssets/Live2DModels`.
   Conserver les packages déjà installés et leurs réglages.
4. Ouvrir VTube Studio, sélectionner ce modèle, vérifier les textures, expressions,
   raccourcis, mouvements et réglages du suivi. La calibration du poste peut demander
   un ajustement.

Le paquet r20 contient les mouvements idle, preuve et perte de suivi, les expressions
et la physique. Pour installer le r21 actuel dans VTube Studio, suivre le guide de
la livraison r21.

## Reprendre le rig r21

Ouvrir une **copie de travail** de la source correspondant à la cible dans Cubism PRO 5.3.05. Le mobile part du CMO3 v49.1 et VTube Studio du CMO3 v45.1 de la livraison. Identifier le document actif via Turboism. PSD2Live sert aux préparations et aux essais isolés. Le point de reprise du 25 novembre conserve les décisions et les sources de la livraison VTube Studio. [Point de reprise](CONTINUATION.md)

`ASSET_MANIFEST.json` fournit les SHA-256 des octets d'origine ; les pointeurs LFS
doivent référencer les mêmes SHA-256 et tailles. `DEPENDENCY_CHECK.json` détaille
la présence des fichiers référencés par chaque `*.model3.json`. Ce contrôle de
fichiers ne remplace pas une validation visuelle dans Cubism/VTube Studio.

Exécuter `python jade-modeling/verify_assets.py` depuis la racine du dépôt après
un `git lfs pull` pour contrôler les octets récupérés et les références du package.
Les références d'expressions et de mouvements de VTube Studio peuvent utiliser
un nom simple dans un sous-dossier du modèle ; ce comportement est décrit dans
la [documentation VTube Studio](https://github.com/DenchiSoft/VTubeStudio/wiki/Loading-your-own-Models).

Les outils Python du modèle utilisent notamment NumPy, Pillow et websockets.
Le plugin `tools/krita_r21_builder` s'exécute dans Krita avec ses modules Krita et
PyQt5 fournis par l'application. Les helpers Java/C++ requièrent un compilateur et
les bibliothèques de l'application installée ; leurs exécutables ne sont pas inclus.

## Éléments conservés hors du dépôt

Les exécutables Cubism/Krita/ScreenToGif, leurs distributions et les dépendances
installées restent des outils externes. Les vidéos brutes de capture sont des
preuves lourdes de séance et ne sont pas requises pour charger ou éditer le modèle.
Les configurations OBS `service.json` et `basic.ini`, qui contiennent des secrets,
sont copiées dans le coffre privé local avec empreintes vérifiées, sans être
ajoutées à l'historique Git. Les originaux sur le poste sont conservés.
