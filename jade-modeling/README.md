# Jade — modélisation Live2D et outils de validation

Ce dossier rassemble les sources artistiques, les modèles Cubism, les animations,
le dernier package VTube Studio pertinent, les scripts Python/PowerShell/C++/Java,
les plans et les rapports courants du projet Jade. Le code applicatif du bot reste
dans le répertoire principal du même dépôt.

Les fichiers sont des copies vérifiées du dossier local `Jade AI Streamer Project`
et du dernier package installé dans VTube Studio ; les originaux sont conservés.
`ASSET_MANIFEST.json` donne les empreintes SHA-256 et explique chaque choix.

La sélection conserve uniquement les dernières versions pertinentes. Les anciens
jalons, exports, rendus et fixtures ne sont pas ajoutés à la version courante.
`INVENTORY.json` décrit les catégories exclues ; leurs originaux restent locaux.

Les sources, textures, rigs, expressions, mouvements et exports essentiels sont
maintenant enregistrés dans ce dépôt, avec Git LFS pour les binaires. Les copies
d'origine sur le poste sont conservées. `ASSET_MANIFEST.json` recense les tailles
et empreintes de l'import ; `DEPENDENCY_CHECK.json` vérifie les références des
packages. Consulter `MODEL_GUIDE.md` pour les points d'entrée et l'état exact.

Les distributions des applications, les bibliothèques installées, caches et
captures vidéo brutes ne font pas partie du code source du modèle. Les outils
externes (Cubism/Krita/VTube Studio) s'installent séparément. Les configurations
OBS contenant des secrets sont sauvegardées dans le coffre local hors Git.

Avant publication : clarifier la provenance et les droits des éléments artistiques,
des bibliothèques et du code repris, remplacer les chemins locaux et retirer les
instructions personnelles. Aucun droit de redistribution des éléments tiers
n'est présumé. Le modèle et l'intégration complète restent en cours de réalisation.
