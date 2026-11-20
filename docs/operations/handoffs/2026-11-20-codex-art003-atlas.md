# ART-003 — atlas r21 plein pied

**Mission :** poursuivre le modèle demandé par le propriétaire en conservant les jambes et les deux chaussures. Codex, branche `work/art003-atlas-r21` depuis `48128df` de `develop`. [Carte ART-003](../../backlog/04-PRODUCTION-2D.md) **en cours** : contrôle natif et export manquants.

Le premier outil isole sept textures depuis le v31 natif. Le deuxième place les 59 images réellement utilisées sur deux pages 4096×4096, sans réduction ni rotation. L’image maître 3840×4160 est préservée ; ses douze maillages échantillonnent désormais une copie de la zone utilisée. Les marges transparentes tiennent compte des coordonnées logiques des textures ; une pièce ne doit pas emprunter les pixels de sa voisine.

## Reconstruction

Depuis la racine du dépôt, avec les objets LFS présents, Python, NumPy et Pillow, créer un dossier de travail **neuf sur D:**. Les scripts refusent d'écraser les fichiers de sortie. Exemple PowerShell (remplacer le dossier s’il existe). Ni fenêtre d’éditeur ni connexion VTS ne sont nécessaires pour ces commandes :

```powershell
$atlasDir = (New-Item -ItemType Directory -Path 'D:\Codex\tmp\jade-atlas-reconstruction').FullName
$v31 = 'jade-modeling/assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3'
python jade-modeling/tools/cmo3_r21_atlas_crop_working.py $v31 --output "$atlasDir/pre.cmo3" --audit "$atlasDir/pre.json"
python jade-modeling/tools/cmo3_r21_native_atlas_working.py "$atlasDir/pre.cmo3" --output "$atlasDir/atlas.cmo3" --audit "$atlasDir/atlas.json"
python jade-modeling/tools/check_jade_r21_atlas_mapping.py "$atlasDir/pre.cmo3" "$atlasDir/atlas.cmo3"
```

**Passe de vérification distincte (Codex, 20 novembre) :** contrôleur en lecture seule sur le candidat SHA-256 `CFD67A576F780750F9B017AD27D89D743C289C2E453364F5B88A77EF40977A65`. Résultat : 78/78 maillages, 59 placements, 2 pages. Écart maximal de coordonnées source→atlas aux points testés : moins de 10⁻¹² pixel ; écart maximal avant/après recadrage sur les couleurs interpolées : moins de 0,005 sur 255. Les pixels entiers des placements finaux ont aussi été comparés aux ressources décodées. Ces mesures concernent le fichier, pas la pile de rendu de Cubism ni les poses en mouvement.

**Reproduction indépendante :** les trois commandes ont aussi été exécutées depuis un worktree du dépôt public avec le v31 LFS. L’intermédiaire et le candidat reproduisent leurs deux empreintes complètes ; le contrôleur a de nouveau retrouvé 78 maillages et 59 placements. Le manifeste et ses 23 références de paquet sont cohérents. Aucun binaire dérivé n’est requis dans Git.

**Prochain jalon :** dans Cubism PRO existant, comparer en plein pied l’image source et l’atlas à pose égale, puis les épaules/cheveux en inclinaison. Si conforme, exporter sur D: dans un dossier distinct et vérifier jupe, jambes et chaussures dans VTube Studio. Ne modifier ni le checkpoint v31 ni le secours r20 ; ne pas clôturer ART-003 avant cette vérification.
