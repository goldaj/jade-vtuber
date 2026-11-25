# Jade — état de reprise du modèle 2D

## Jalon du 25 novembre 2026

Le propriétaire a approuvé le [plan directeur Live2D](MODEL2D_MASTER_PLAN.md) et donné le feu vert à la production. Il observe les validations en direct.

- **Base locale** · `Jade_r21_v32.cmo3`, SHA-256 `C26C686DBF6A9DE08FBAD281088118A6EDF2CFBDBDCEC993058C039F81294D1C`. Le v31 natif reste un jalon de référence visuelle.
- **Premier paquet** · VTube Studio 1.35.10 a affiché Jade en pied avec le premier export r21, ses deux textures de 4096 px, neuf sorties de physique capillaire, Smile/Sad et un idle de 36 s. Le propriétaire a relevé des défauts de découpe et autorisé la poursuite.
- **Candidat de finition v33** · `Jade_r21_v33_finition_candidate.cmo3`, SHA-256 `CEC6A4521ED32A878BFB6A82E95513CA2358BA27F5989CF122AFF163099EDDDF`. Festons, bords des mains, transparence au nez et sous-peinture d’une partie des cheveux arrière retouchés. Export natif SDK 5.0, assemblé et chargé comme modèle séparé `Jade_r21_v33`. L’API a confirmé le chargement et ses 42 paramètres. Les retouches restent à observer en mouvement dans VTube Studio.
- **Candidat v34** · Retouches des coudes, du bord gauche de taille et des commissures sur le CMO3 de travail. Export PSD2Live en MOC3 version 5, assemblage et chargement dans VTube Studio par API. Les diagonales, la fermeture des yeux et la bouche ouverte répondent dans VTube Studio. Les entrées visage pour les yeux et la bouche couvrent désormais les plages natives 0–1. La confirmation visuelle en mouvement reste ouverte.
- **Sources** · Le report de sept pièces de jupe, jambes, chaussures et épaules a commencé sur des copies KRA/PSD. Le modèle et les sources éditables restent sur D:.
- **Outils** · Préférer PSD2Live et Turboism pour les opérations qu’ils prennent en charge et l’API VTube Studio pour les chargements, poses et déclenchements qu’elle expose. L’export MOC3 PSD2Live compatible a été exercé sur le v34. L’export natif SDK 5.0 de Cubism PRO 5.3.05 sert de repli.
- **Branche** · Plan aligné sur `develop` à `c3c17b0`, travaux documentaires sur `codex/jade-r21-reprise`.

**Reprise de la production.** Poursuivre les raccords taille, avant-bras, tempes et cou. Les éléments mineurs concernant les yeux, la bouche et les franges de l’oreille restent ouverts dans le suivi visuel local sur D:. Comparer au neutre et en mouvement avant de clore chaque correction.

## Informations à relever à chaque jalon

Indiquer l’unité, le statut, la version ou le SHA, le fichier obtenu, la vérification réellement faite et son résultat, les limites utiles et la prochaine action. Pour les changements de branche ou de modèle Codex, suivre le [protocole](MODEL2D_CODEX_PLAYBOOK.md). [Point de reprise et fichiers](CONTINUATION.md) · [Passation](../docs/operations/handoffs/2026-11-25-codex-jade-r21-reprise.md)
