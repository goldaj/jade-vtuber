# Jade — réalisation du MVP Discord

Plan de travail sur `develop`, à exécuter dans l'ordre. La démo est considérée
comme terminée. Référence : [feuille de route](ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md).

**Reprise Terra :** les deux défauts de silence signalés dans le
[relais Astra](ASTRA-REVUE-MVP-20261110.md) sont corrigés et testés hors ligne.
La recette vocale réelle sur téléphone et le partage de l'avatar restent à
effectuer avec le propriétaire ; voir [TASKS](TASKS.md).

**Décision ultérieure du propriétaire :** le serveur privé est dédié à Jade ;
elle peut interagir avec les personnes et les autres bots, dans tous ses salons,
sans liste individuelle ni validation supplémentaire. Cette décision remplace
les consignes contraires dans les documents historiques. La propre voix de Jade
est ignorée pour éviter qu'elle se réponde en boucle.

## 1. Mettre à jour le moteur principal

**Réalisé :** modèles, transport partagé, tests hors ligne et essai réel court
sur audio synthétique réussis ; résultats dans [TASKS](TASKS.md).

1. Reprendre les modèles et le TTS Realtime de la démo ; adapter les interfaces
   du moteur principal, le retour WAV, les erreurs et l'annulation. Une simple
   substitution du nom TTS sur l'ancien endpoint ne suffit pas.
2. Mettre à jour la configuration privée sans exposer les valeurs ni perdre
   les anciens réglages ; garder le dialogue, le STT et le TTS configurables.
3. Tester les chemins texte, STT, TTS et erreurs hors ligne, puis effectuer un
   essai réel court à budget minimal déjà convenu, sans microphone physique.

**Terminé quand** le moteur principal produit une réponse et une voix réelles,
et que les erreurs ne déclenchent pas de requêtes payantes répétées en silence.

## 2. Finaliser le vocal Discord

1. Reprendre les connecteurs : ne pas filtrer les salons ou les autres bots par
   autorisation interne ; accepter toute personne ou bot présent dans le salon
   vocal rejoint. Discord permet le déplacement entre salons ; une connexion
   vocale ne couvre pas simultanément tous les salons d'un même serveur.
2. Tester et corriger la fin de tour, les suivis sans nom d'activation, le
   silence, l'anti-écho et l'arrêt. Le tête-à-tête est déjà simulé ; le groupe
   actuellement silencieux doit pouvoir interagir dans le salon dédié à Jade.
3. Vérifier que le son et la réponse restent dans leur session, et que sortie,
   changement de participants ou déconnexion annulent les travaux périmés.

**Terminé pour la préparation quand** les scénarios automatisés passent ; la
conversation humaine réelle est vérifiée à l'étape 4.

## 3. Relier avatar, voix et téléphone

1. Partir du modèle r20 et des composants de la démo ; vérifier leur réutilisation
   dans le parcours Discord avant d'ajouter une autre intégration. Si VTube Studio
   est retenu, utiliser son API locale et conserver son jeton hors dépôt.
2. Déclencher les mouvements de parole au début de la lecture effective et
   revenir au repos à la fin ou à l'erreur ; vérifier l'amplitude de bouche.
3. Préparer le partage manuel de la fenêtre depuis le client Discord PC vers le
   téléphone. Isoler le son pour éviter le doublon entre le partage et le bot.

**Terminé pour la préparation quand** le parcours est testable sans caméra et
que son lancement est documenté. Le r21 reste un chantier distinct.

## 4. Stabiliser, recetter et documenter

1. Exécuter les tests, le scan de secrets et les vérifications d'installation ;
   traiter les erreurs de connexion, permissions, quota, arrêt et reconnexion.
2. Avec le propriétaire et les personnes présentes, tester depuis le téléphone
   au moins dix tours variés, sans nom obligatoire : suivis, silence, arrêt et
   panne ; vérifier image, bouche, son unique, latence et coût observés.
3. Corriger les défauts constatés, fournir les étapes de démarrage et dépannage,
   puis faire valider le MVP par le propriétaire. Le produit mobile autonome vient
   après cette validation ; une fusion vers `main` exige sa décision.

**Terminé quand** le propriétaire voit et entend Jade sur téléphone et peut lui
parler naturellement, avec les limites restantes documentées.

## Contre-lecture par métier

- **Développement :** réutiliser les composants de la démo sans recopier deux
  implémentations divergentes ; vérifier la compatibilité du moteur principal.
- **Audio et vidéo :** un mouvement déclenché par une hotkey ne prouve pas la
  synchronisation des lèvres ; contrôler la lecture effective et l'écho.
- **Sécurité et vie privée :** bloquer audio et réponses hors session autorisée ;
  ne pas écrire clés, enregistrements ou transcriptions dans le dépôt ou les logs.
- **Qualité :** les mocks ne prouvent pas Discord, le microphone ou le téléphone ;
  distinguer explicitement préparation automatisée et recette humaine.
- **Utilisateur final :** une procédure de lancement trop compliquée compromet le
  MVP ; conserver une marche à suivre courte et des erreurs compréhensibles.
- **Utilisateur payant de Codex :** éviter les audits répétés, abstractions et
  prototypes sans décision à prendre ; un contrôle ciblé suffit avant de poursuivre.
