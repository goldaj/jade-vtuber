# Jade — état de reprise du modèle 2D

## Jalon du 25 novembre 2026

Le propriétaire a approuvé le [plan directeur Live2D](MODEL2D_MASTER_PLAN.md) et donné le feu vert à la production. Après le rejet du v34, il a confié à Codex la recette visuelle et les corrections.

- **Base locale** · `Jade_r21_v32.cmo3`, SHA-256 `C26C686DBF6A9DE08FBAD281088118A6EDF2CFBDBDCEC993058C039F81294D1C`. Le v31 natif reste un jalon de référence visuelle.
- **Premier paquet** · VTube Studio 1.35.10 a affiché Jade en pied avec le premier export r21, ses deux textures de 4096 px, neuf sorties de physique capillaire, Smile/Sad et un idle de 36 s. Le propriétaire a relevé des défauts de découpe et autorisé la poursuite.
- **Candidat de finition v33** · `Jade_r21_v33_finition_candidate.cmo3`, SHA-256 `CEC6A4521ED32A878BFB6A82E95513CA2358BA27F5989CF122AFF163099EDDDF`. Festons, bords des mains, transparence au nez et sous-peinture d’une partie des cheveux arrière retouchés. Export natif SDK 5.0, assemblé et chargé comme modèle séparé `Jade_r21_v33`. L’API a confirmé le chargement et ses 42 paramètres. Les retouches restent à observer en mouvement dans VTube Studio.
- **Rejet du v34** · Le v34 a été rejeté à l’écran. Comparer les MOC3 et leurs atlas a isolé des différences de couverture des textures dans l’export PSD2Live. Les défauts présents aussi sur le v33 natif ont été repris depuis le dessin maître.
- **v36, base de finition** · `Jade_r21_v36_recette_candidate.cmo3`, SHA-256 `1122A3B8D05D82467A6FC5A26511B54815EB8DE5596351949E794EEBF6C1723E`. Reconstruction des bras et mains, robe, chevilles, tête et cou. Les neuf sorties capillaires et les deux paramètres d’oreilles déplacent les nouveaux maillages. Export natif SDK 5.0 en trois pages 4096 px, chargé par API et observé plein pied dans VTube Studio. Le même export a été revu au neutre, en diagonales et sous respiration, fermeture des yeux et ouverture de la bouche.
- **Sources** · Le report de sept pièces de jupe, jambes, chaussures et épaules a commencé sur des copies KRA/PSD. Le modèle et les sources éditables restent sur D:.
- **Outils** · Préférer PSD2Live et Turboism pour les opérations qu’ils prennent en charge et l’API VTube Studio pour les chargements, poses et déclenchements qu’elle expose. Employer l’export natif SDK 5.0 de Cubism PRO 5.3.05 pour la recette visuelle. Juger les textures en plus de la réponse des paramètres.
- **Branche** · Plan aligné sur `develop` à `c3c17b0`, travaux documentaires sur `codex/jade-r21-reprise`.

**Reprise de la production.** Le v36 sert de base pour le polissage du visage, du cou et du contour des cheveux. Les petites marques de cils, les franges chromatiques et le recouvrement du col aux grandes inclinaisons restent au suivi local. Calibrer ensuite les combinaisons, la physique et les expressions, puis compléter le lot des 14 motions.

## Informations à relever à chaque jalon

Indiquer l’unité, le statut, la version ou le SHA, le fichier obtenu, la vérification réellement faite et son résultat, les limites utiles et la prochaine action. Pour les changements de branche ou de modèle Codex, suivre le [protocole](MODEL2D_CODEX_PLAYBOOK.md). [Point de reprise et fichiers](CONTINUATION.md) · [Passation](../docs/operations/handoffs/2026-11-25-codex-jade-r21-reprise.md)
