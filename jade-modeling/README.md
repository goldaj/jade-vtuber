# Jade — modélisation Live2D et outils de validation

Ce dossier rassemble les sources artistiques, les modèles Cubism, les animations,
le dernier package VTube Studio pertinent, les scripts Python/PowerShell/C++/Java,
les plans et les rapports courants du projet Jade. La [livraison r21](assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/LISEZMOI.md) réunit le paquet VTube Studio v45.1, le profil mobile v49.1, le rig et les sources de dessin et d’animation. Le code applicatif du bot reste
dans le répertoire principal du même dépôt.

Les fichiers sont des copies vérifiées du dossier local `Jade AI Streamer Project`
et du dernier package installé dans VTube Studio ; les originaux sont conservés.
`ASSET_MANIFEST.json` donne les empreintes SHA-256 et explique chaque choix.

La sélection conserve les versions actives, les jalons et les sources utiles à la
reprise. `INVENTORY.json` décrit le relevé historique du tri initial. Les versions
intermédiaires retirées de la livraison restent accessibles dans l’historique Git.

Les sources, textures, rigs, expressions, mouvements et exports essentiels sont
maintenant enregistrés dans ce dépôt, avec Git LFS pour les binaires. Les copies
d'origine sur le poste sont conservées. `ASSET_MANIFEST.json` recense les tailles
et empreintes de la sélection suivie. Le catalogue `SHA256SUMS.txt` couvre la livraison r21 complète. `DEPENDENCY_CHECK.json` consigne le résultat du contrôle des références de modèles. Consulter le [guide modèle](MODEL_GUIDE.md) pour les fichiers et le [plan directeur approuvé](MODEL2D_MASTER_PLAN.md) pour la reprise avec Turboism et PSD2Live.

Les distributions des applications, les bibliothèques installées, caches et
captures vidéo brutes ne font pas partie du code source du modèle. Les outils
externes (Cubism/Krita/VTube Studio) s'installent séparément. Les configurations
OBS contenant des secrets sont sauvegardées dans le coffre local hors Git.

Dépôt déjà public au 16 novembre 2026 : clarifier la provenance et les droits des éléments artistiques,
des bibliothèques et du code repris, remplacer les chemins locaux et retirer les
instructions personnelles. Aucun droit de redistribution des éléments tiers
n'est présumé. Le modèle et l'intégration complète restent en cours de réalisation.
