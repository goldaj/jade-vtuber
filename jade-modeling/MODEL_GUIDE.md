# Jade — reprendre le modèle et les animations

## Sources actuelles

Tous les chemins ci-dessous sont relatifs à ce dossier. Les fichiers binaires se
récupèrent avec `git lfs pull` ; `git lfs fsck` vérifie les objets locaux.

| Usage | Fichier ou dossier |
| --- | --- |
| Dernier jalon natif r21, v30 | `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_back_hair_restore_v30.cmo3` |
| Candidat cheveux, pas encore validé comme jalon natif | `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_v30.TEST_hair_leaves_r02.cmo3` |
| Dernière source Krita conservée du rig artistique | `assets/live2d/r21_professional_art/working_v005/jade_art_v005_r21_rig_art_v2_face_complete_v9.kra` |
| PSD d'interchange du rig | `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_rig_only_v2.psd` |
| Maître graphique intact | `assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png` |
| Package animé r20 complet à restaurer | `runtime-installed/Jade_professional_r20_idle_complete/` |
| Politique retenus/exclus | `INVENTORY.json`, avec justification par fichier dans `ASSET_MANIFEST.json` |

Les sources KRA/PSD ne sont pas encore synchronisées avec les derniers ajouts
plein pied et cheveux du CMO3 r21. Ne pas réimporter aveuglément le PSD dans le
dernier CMO3 : cela risquerait de réintroduire des éléments anciens. Les fichiers
`CONTINUATION.md` et `PLAN_MODELE_JADE.md` décrivent les limites et la suite exacte.

Les deux CMO3 ont des rôles distincts : v30 est le dernier jalon enregistré dans
Cubism ; r02 est le candidat courant qui doit encore être validé dans l'application.
Les composants source les plus récents du bas du corps, des épaules, des yeux et
de la bouche sont également conservés. Les versions intermédiaires restent locales.

## Restaurer le package VTube Studio

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

Le package r20 contient notamment les mouvements idle, preuve et perte de suivi,
les expressions et le réglage de physique. Il sert de sauvegarde de l'animation
existante ; il n'est pas présenté comme un export final du CMO3 r21 en cours.

## Reprendre le rig r21

Ouvrir une **copie de travail** du CMO3 v30 dans la version compatible de Cubism
utilisée par le projet (5.2.03 PRO selon les notes). Conserver les jalons d'origine.
Le candidat r02 doit encore passer les observations natives prévues avant de
devenir v31. Les sources, rapports et outils nécessaires restent réunis dans
l'arborescence d'origine relative pour faciliter la reprise.

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
