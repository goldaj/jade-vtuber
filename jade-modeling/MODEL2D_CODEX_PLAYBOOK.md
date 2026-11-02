# Jade — protocole Codex pour l'ensemble du modèle 2D VTuber

**VALIDÉ par le propriétaire le 28 octobre 2026**, après relecture orale du protocole initial de rig et extension explicite à **toute la création et validation du modèle 2D**. Cette approbation porte sur l'organisation du travail, **pas** sur un plan technique futur ni sur une validation visuelle de Jade.

## Portée : création du personnage 2D, pas développement du bot
S'applique à : conception visuelle, dessin et retouches, préparation et séparation des calques, sources Krita/PSD et exports graphiques, organisation des assets, modèle Live2D/Cubism, déformeurs et rig, cheveux/vêtements/accessoires, physique, expressions, animation et idle, exports et configuration dans VTube Studio, tests de rendu et contrôles de bout en bout du personnage.
Les scripts/outils **directement nécessaires** à ce flux de production 2D sont inclus ; « non-code » décrit l'objectif artistique/VTuber, pas une interdiction d'utiliser du code d'automatisation.
**Exclus** : architecture du bot Python, LLM/STT/TTS, Discord/Twitch, infrastructure, déploiement applicatif et refonte du runtime, sauf interface strictement nécessaire pour vérifier le modèle VTuber. Pas d'autorisation implicite de merge, déploiement ou modification hors périmètre.

## Lecture obligatoire au démarrage d'une session 2D
1. Lire `AGENTS.md`, `docs/CODEX_PARALLEL_GPT6.md`, puis ce protocole et `jade-modeling/MODEL2D_CODEX_STATE.md`.
2. Lire `jade-modeling/MODEL_GUIDE.md`, `jade-modeling/CONTINUATION.md`, `jade-modeling/PLAN_MODELE_JADE.md`, manifestes, rapports pertinents et `docs/CHATGPT_PROJECT_HISTORY.md` si utile.
3. Lire `jade-modeling/MODEL2D_MASTER_PLAN.md` **s'il existe et a été effectivement validé**. Sinon suivre la phase de planification Astra.
4. Vérifier les fichiers, les branches, Git LFS, la disponibilité des applications natives et les travaux concurrents ; ne pas confondre l'état documenté avec l'état effectivement constaté.

Les consignes de sécurité, de conservation des sources et les instructions récentes explicites du propriétaire priment.

## Choix du modèle : Codex propose, l'utilisateur change manuellement
- **GPT-6 Astra** (raisonnement élevé si disponible) : audit initial et **plan directeur complet** de toute la chaîne 2D ; décisions artistiques/techniques structurantes, cas difficiles, **revue à la fin de chaque grande phase**.
- **GPT-6.1 Terra** (raisonnement moyen si disponible) : exécutant **par défaut** des unités précisément planifiées, retouches ciblées, préparation des assets, opérations répétables et contrôles circonscrits.
- **GPT-6.1 Sol** (raisonnement moyen si disponible) : diagnostic intermédiaire lorsque Terra ne résout pas un problème local.

Ce sont des **rôles recommandés**, pas une promesse de performance, ni un fait démontré sur leur coût réel. Adapter aux modèles effectivement proposés par l'interface. Si le modèle actif n'est pas observable, demander une confirmation ponctuelle ; ne pas l'inventer. **Aucun changement automatique de modèle**. Si le modèle est déjà adapté, ne pas interrompre inutilement.

Quand un relais est requis, s'arrêter proprement et afficher exactement les informations suivantes :
> **CHANGEMENT DE MODÈLE RECOMMANDÉ**  
> Modèle actuel : [confirmé / inconnu]  
> Sélectionne : **[Astra, Sol ou Terra]**, [niveau de raisonnement conseillé]  
> Pourquoi : [blocage précis, plan initial ou revue de phase]  
> Prochaine étape : [identifiant de tâche et résultat attendu]  
> État et preuves : `jade-modeling/MODEL2D_CODEX_STATE.md` [autres chemins utiles]  
> Après le changement manuel, réponds : **« Reprends Jade »**.

Ne pas supposer que l'utilisateur a changé de modèle avant sa confirmation. Ne pas effectuer des changements de modèle pour des tâches insignifiantes.

## Phase A : Astra construit le plan directeur intégral une fois
Si `MODEL2D_MASTER_PLAN.md` manque ou n'a pas été validé, proposer de passer à Astra, sans refaire tout le personnage. Astra **inspecte réellement** les sources et livrables existants avant de décider.
Produire `jade-modeling/MODEL2D_MASTER_PLAN.md` couvrant **la chaîne complète jusqu'au modèle Jade utilisable et contrôlé dans VTube Studio**, et non simplement un rig partiel :
1. Inventaire et qualité des dessins existants, identité visuelle, cohérence des proportions, éléments manquants et retouches réellement nécessaires ;
2. découpage, couches et transparences, articulation et marges de déformation, synchronisation sources Krita/PSD/CMO3 ;
3. construction/ajustement des paramètres Live2D et du rig : visage, yeux, bouche, tête, corps, vêtements, cheveux, accessoires ;
4. physique, expressions, mouvements et animations idle, combinaison des paramètres et comportements visuels ;
5. exports natifs, configuration dans VTube Studio, mapping, comportement et validation sur des cas représentatifs ;
6. tests de non-régression, qualité visuelle, conservation des sources, livrable final et reprise.

Chaque grande phase contient des **unités courtes exécutables par Terra**, avec identifiant, dépendances, fichiers exacts, instructions reproductibles, livrable, critère de réussite **observable**, contrôle minimal requis, modèle recommandé, risque et condition d'escalade. Distinguer sans ambiguïté vérification de structure/simulation et validation native **réellement effectuée** dans Krita, Cubism ou VTube Studio. Ne pas inventer de capture, de licence, de test ni d'avis artistique humain.
Après rédaction du plan, demander la validation du plan au propriétaire avant les modifications structurantes ; l'approbation de ce protocole **ne vaut pas validation du plan futur**. Une fois prêt à exécuter, demander le passage à Terra.

## Phase B : Terra exécute, avance, conserve les preuves
- Prendre **une unité** du plan et produire le résultat attendu, en limitant les modifications à son périmètre.
- Ne pas multiplier les analyses, les variantes et les raffinements non demandés. Une tâche considérée conforme à ses critères n'est pas reprise pour une amélioration cosmétique facultative : noter cette amélioration dans un backlog de finition.
- Faire **les tests ciblés indispensables** pour éviter pertes de calques, assets cassés, trous dans les textures, erreurs de hiérarchie, joints visibles ou paramètres corrompus. Les audits et tests complets appartiennent aux jalons importants.
- Préserver les masters, CMO3 natifs, KRA/PSD, archives, checkpoints, manifestes et empreintes. Utiliser des copies de travail, ne jamais écraser silencieusement des versions.
- Après chaque unité, mettre à jour `MODEL2D_CODEX_STATE.md` : statut, artefacts, tests/observations réels, limites, prochaine tâche précise et modèle suggéré ; commit sur branche appropriée si autorisé. Pas de merge implicite.

## Phase C : blocages, relais et limites de l'environnement
- **Terra** : au maximum deux approches réellement différentes sur un même blocage, diagnostic enregistré, puis recommandation Sol.
- **Sol** : au maximum deux tentatives circonscrites ; si échec ou question architecturale/artistique complexe, demander Astra.
- **Astra** : lever le blocage ou amender le plan de manière traçable ; retourner à Terra dès que la suite est exécutable.
- Un logiciel Cubism/VTube Studio indisponible, une session Windows inaccessible, un asset LFS absent ou une validation visuelle impossible **ne sont pas résolus par un switch de modèle**. Décrire l'intervention humaine/outillage requis et stopper les essais inutiles.
- Pour un choix artistique subjectif, ne pas substituer un verdict inventé à l'avis du propriétaire : présenter une comparaison concrète et la décision à prendre.

## Phase D : revue Astra à la fin de chaque grande phase
Demander le changement manuel vers Astra **au jalon**, non après chaque retouche ou mèche. Astra vérifie les dépendances entre unités, la cohérence visuelle et technique, les risques de régression, les sources et les observations réellement accessibles ; tests d'intégration si disponibles.
Verdict documenté : **VALIDÉ / À REPRENDRE / BLOQUÉ PAR ENVIRONNEMENT**, avec preuves, limites et éventuelles corrections du plan. Si validé, demander retour à Terra pour la phase suivante. Ne pas déclarer le modèle final terminé sans export natif **et** preuve d'utilisation réelle dans VTube Studio.

## Point de départ historique à contrôler (pas une validation nouvelle)
- Checkpoint Cubism r21 v30 conservé ; candidat `v30.TEST_hair_leaves_r02` avec neuf mèches/feuilles indépendantes et 45 poses, **non validé nativement** à ce stade.
- Runtime animé r20 : repli antérieur, **pas** le package final r21.
- Sources KRA/PSD historiques pas entièrement synchronisées avec les derniers ajouts CMO3 ; ne pas réimporter à l'aveugle.
- Pour le détail des fichiers, suivre `MODEL_GUIDE.md`, `CONTINUATION.md` et les manifestes ; ne pas refaire les contrôles sans nécessité.

## Clôture et continuité
Chaque session doit finir avec : **réalisé / non réalisé**, branche/commit, preuve réelle, point de blocage, **prochaine action exécutable** et **modèle recommandé**. Mettre à jour l'état **avant** de proposer un changement de modèle, pour qu'une reprise n'exige pas une nouvelle exploration coûteuse.
Toute tâche de création 2D doit utiliser ce protocole ; la refonte logicielle reste indépendante.