# Jade r21 · Livraison VTube Studio et mobile

Le dossier [Jade_r21_v45](Jade_r21_v45/) contient le modèle plein pied pour VTube Studio. Le nom de dossier et les noms de fichiers historiques permettent aux commandes de Jade de retrouver le profil v45 et ses gestes. La finition v45.1 correspond à la correction des deux iris.

La PWA charge le manifeste `Jade_r21_mobile.model3.json`, le visage continu v49.1
et dix-huit gestes pour neuf intentions. Ses courbes éditables se trouvent dans
`Edition/mobile-intentions/`. VTube Studio lit le manifeste `Jade_r21_v45.model3.json`
et ses quatorze gestes du paquet v45.1. [Manifeste mobile](Jade_r21_v45/Jade_r21_mobile.model3.json)

## Installer dans VTube Studio

1. Dans VTube Studio, ouvrir le dossier des modèles depuis le sélecteur de modèle. Si ce dossier contient déjà `Jade_r21_v45`, charger un autre modèle et conserver la copie existante avec son profil personnalisé dans un dossier de sauvegarde **à l’extérieur** de `Live2DModels`.
2. Copier le dossier complet `Jade_r21_v45` dans `Live2DModels`. Le chemin attendu se termine par `Live2DModels/Jade_r21_v45/Jade_r21_v45.vtube.json`. Laisser les trois textures dans leur sous-dossier et les deux expressions dans `expressions`.
3. Ouvrir `Jade_r21_v45` dans le sélecteur. Le profil livré contient le suivi, la physique, la boucle de repos de 36 secondes et les commandes de gestes et d’expressions. Les touches de clavier des gestes peuvent être attribuées dans l’éditeur de raccourcis de VTube Studio. Les pilotes retrouvent les identifiants des commandes auprès du modèle chargé.

Pour revenir à la configuration précédente, charger un autre modèle, placer le dossier v45.1 hors de `Live2DModels`, puis remettre la copie de sauvegarde à son emplacement initial. Chaque copie de travail du fichier `.vtube.json` évolue lorsque VTube Studio enregistre les réglages.

Après le clonage, exécuter `git lfs pull` pour récupérer les fichiers binaires. Le profil portable fournit ses propres identifiants de modèle et de raccourcis. Les pilotes de Jade les retrouvent par le nom et le fichier du geste. Régler le cadrage dans VTube Studio sur le poste de destination.

Les réglages de suivi et les observations en situation sont consignés dans la [calibration du modèle livré](CALIBRATION.md).

## Reprendre le dessin ou les gestes

| Travail | Fichier |
| --- | --- |
| Dessin, rig, masques et atlas corrigés dans Cubism PRO 5.3.05 | [CMO3 natif](Edition/Jade_r21_v45_1_iris.cmo3) |
| Dessin sur calques dans Krita ou Photoshop | [Sources éditables et consignes de réimport](Sources/LISEZMOI.md) |
| Courbes et tangentes des 14 clips dans PSD2Live | [Atelier v45](Edition/Jade_r21_v45_motions.psd2live) et [sept paires de courbes](Edition/intent_motions/) |
| Courbes des 18 gestes mobiles dans PSD2Live | [Neuf paires de courbes](Edition/mobile-intentions/) |
| Réglages de l’instance VTube Studio | [Profil portable livré](Jade_r21_v45/Jade_r21_v45.vtube.json) |

L’atelier PSD2Live contient le dessin importé au jalon des gestes. Pour exporter une nouvelle version après une retouche d’iris, repartir du CMO3 v45.1 et reprendre les courbes de cet atelier. Les fichiers de dessin et d’animation se conservent hors du dossier des modèles de VTube Studio.

Le jalon mobile `cheveux-continus-v48-fa9b3480` reste livré. L’autre copie `cheveux-continus-v48` contenait les mêmes quatre fichiers que `trois-quarts-v47-2`. Les textures provisoires de `face-turn` et `profile-smile` appartiennent à la version sauvegardée. [Livraison avant nettoyage](https://github.com/goldaj/jade-vtuber/tree/e5dd826/jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1)

## Vérifier une copie

Exécuter `powershell -NoProfile -File .\Verifier.ps1` depuis la racine de la livraison. Cette commande lit les fichiers et compare leurs empreintes SHA-256 à [SHA256SUMS.txt](SHA256SUMS.txt). Ce contrôle s’applique à la copie de livraison, avant que VTube Studio ne réenregistre le profil installé. [Origine des fichiers et contenu vérifié](PROVENANCE.json)
