# Nettoyage du dépôt de Jade

Le 27 novembre 2026, `main@e5dd826` a reçu l’arbre complet de `develop@56eb108`. La comparaison Git est vide. Le nettoyage part de ce commit de develop et conserve main comme point de retour. [CI de la version de référence](https://github.com/goldaj/jade-vtuber/actions/runs/46006614922)

## Références et matériaux récupérables

Les révisions locales et distantes ont été copiées dans un bundle Git vérifié, avec une copie des 127 objets Git LFS et leurs empreintes. Certaines branches contenaient encore des commits propres. Après vérification, 26 branches distantes et cinq anciennes branches locales ont été retirées. La PR documentaire #54 a été fermée avec sa branche. Les répertoires de travail existants restent disponibles à leur commit d’origine. La sauvegarde sur D: conserve les pointes exactes, y compris celle de la PR #54.

## Étendue de la revue

Examen automatisé de l’arbre complet avant modification, soit **899 fichiers suivis**, 752 fichiers texte, 213 051 lignes et 134 pointeurs Git LFS. Les parseurs Python, JSON, TOML, XML et SVG ont traité 415 fichiers structurés sans erreur. La recherche de doublons a identifié 11 groupes de blobs identiques.

Les revues par domaine ont croisé les points d’entrée, imports, appels, sélecteurs HTML-UI, tests et ressources chargées dynamiquement. Le parcours documentaire a vérifié 255 fichiers Markdown et 1 384 liens locaux. Chaque retrait repose sur la recherche de ses consommateurs ou sur une équivalence des fichiers. Les sources d’atelier et les preuves datées restent des éléments de travail ou de traçabilité.

## Changements

- Code et configuration. Retrait du module d’arrivée Discord déjà débranché, de l’ancien adaptateur de déploiement mobile, d’un adaptateur Twitch remplacé, de fonctions de capture et surveillance orphelines, et des styles des sections retirées. Le contrôle PyCharm et la rotation Twitch actuels restent les chemins exploités.
- Assets. Six dérivés mobiles obsolètes, dont quatre copies identiques, libèrent 46 216 156 octets dans le checkout. Le paquet livré garde ses sources et ses exports utilisés. L’inventaire couvre les fichiers suivis et les empreintes du paquet portable sont recalculées. Les anciennes révisions restent récupérables depuis le point de retour ou l’archive.
- Documentation. Les guides d’usage, d’installation, de maintenance et de reprise décrivent le code actuel. Le relevé historique des branches du 18 novembre est conservé dans l’historique.

## Vérifications

- Edge a chargé le r21 avec le SDK Live2D local. Les 18 variantes et les neuf cadrages passent, ainsi que le clignement et la synchronisation de la bouche avec l’audio synthétique. Le relevé compte zéro requête au r20 et zéro erreur JavaScript. Les 83 fichiers du paquet portable et les 97 références de modèles ont été vérifiés.
- Le premier export Windows a dépassé le délai de deux secondes du test Discord Live avec SQLite. Le délai d’attente de ce scénario de test a été porté à dix secondes. L’horloge simulée, le seuil de dépenses et les assertions sont conservés. Deux exécutions locales successives passent.

## Dépendances encore actives

La PWA utilise les dix-huit variantes r21. Le r20 sert toujours au renderer Windows lancé par `--avatar`, y compris via le Run PyCharm, et au secours du client mobile. Le raccordement Windows du r21 et la recette avec un paquet r20 absent sont suivis dans DEV-001. Ces dépendances expliquent la présence des assets r20 dans l’arbre. Les fichiers de voix, de mémoire et de configuration privée du poste restent gérés hors du dépôt.

## Échanges accessibles

- **Propriétaire**, synthèse. Publier d’abord develop sur main comme point de retour. Supprimer les autres branches après contrôle, puis nettoyer tous les répertoires, le code mort, les guides dépassés et les assets obsolètes.
- **Assistant**, synthèse. Vérifie l’égalité de l’arbre de main avec celui de develop avant le nettoyage. Relève des branches divergentes et préserve leurs révisions et leurs objets Git LFS dans une archive locale.

Le journal reprend les décisions destinées à guider la maintenance. Les heures individuelles des messages sont indisponibles.
