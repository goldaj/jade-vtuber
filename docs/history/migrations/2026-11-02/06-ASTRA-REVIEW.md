# Revue Astra — 2 novembre 2026

**Avis : plan validé pour exécution par Terra avec les précisions ci-dessous.** Elles complètent et, en cas de divergence, remplacent les passages correspondants de `03-PLAN.md`. Ce feu vert concerne le travail d’intégration ; il ne certifie pas encore le runtime corrigé ou une installation live.

Contrôles ciblés : neuf références distantes inchangées, PR #2 toujours ouverte en brouillon, huit reproductions rejouées avec les mêmes défauts. Les constats F01–F12 sont conservés avec leurs niveaux de preuve. La suite de 51 tests reste la preuve de la passe Terra, sans nouvelle exécution complète ici. Aucun code runtime modifié.

## 1. Ordre d’exécution corrigé

1. Depuis la branche documentaire propre, créer la branche d’intégration et reprendre les six commits documentaires de `develop` selon le lot 1. Conserver `GIT_LFS_SKIP_SMUDGE=1` dans cette copie de travail ; comparer les arbres Git des assets, pas leurs octets locaux non matérialisés.
2. Diagnostiquer Actions dès le début, pendant que les corrections avancent localement. Ne pas attendre la fin du code pour découvrir un obstacle de quota ou de runner.
3. Traiter les lots 2 et 3 avec les contrats ci-dessous, puis produire le lock et vérifier une installation neuve.
4. **Pousser le candidat relu sur la branche source de la PR #2 avant d’exiger sa CI finale.** Le plan initial plaçait ce push après la CI : ordre corrigé. Garder la PR en brouillon pendant les vérifications.
5. Après validations locales/CI et recette des modes retenus, intégrer une fois vers `develop`. La première mise en service reste distincte et supervisée.

Le défaut F11 de preview public peut rester documenté et différé ; il ne justifie aucune publication ni blocage de l’intégration privée. Speech-to-speech et les cinq pistes produit restent hors de ces correctifs.

## 2. Arrêt : corriger l’application entière

Piège confirmé par lecture : `main.py` quitte son `TaskGroup` avant d’appeler `runtime.stop()`. Or `DiscordText.connect_forever()` attend `voice_bridge.close()` dans son `finally`, qui draine le STT. Corriger uniquement `Runtime.stop()` laisse donc un blocage en amont.

1. Donner à un coordinateur unique la propriété du runtime, captures, tâches des connecteurs, lecteurs et client OpenAI. Enregistrer chaque nettoyage dès l’acquisition, y compris avant un démarrage qui peut échouer.
2. Introduire les états `RUNNING → STOPPING → STOPPED`. Refuser les nouvelles admissions dès `STOPPING`, avant toute attente ; fermeture répétée idempotente.
3. Sur Ctrl+C/erreur fatale : demander immédiatement l’arrêt des producteurs, invalider le backlog, annuler le travail actif et arrêter les lecteurs. Déclencher cela **avant** d’attendre la fermeture du groupe de tâches. Aucun `pending.join()` non borné dans les fermetures des connecteurs.
4. Pour chaque élément retiré d’une queue, exécuter exactement un `task_done()`, y compris abandon et sentinelle. Régler aussi les futures des demandeurs en échec/annulation. Ne pas accéder aux attributs privés de `asyncio.Queue`.
5. Attendre les tâches et lecteurs avec une échéance monotone globale, puis fermer transports et client SDK. Pour ffplay/FFmpeg : terminer, attendre brièvement, tuer si nécessaire, attendre effectivement la fin, puis supprimer le temporaire. Propager `CancelledError` après nettoyage.
6. Garder un arrêt gracieux explicite : admissions fermées, drainage limité, puis bascule en arrêt immédiat. Valeur de départ proposée pour l’arrêt logiciel : 5 s au total, à tester ; ce n’est pas une performance matérielle mesurée.

**Tests requis :** arrêt de l’application complète avec faux connecteur bloqué dans son nettoyage ; queue pleine ; démarrage partiellement échoué ; fermeture répétée ; zéro nouvel appel après arrêt immédiat. Si un pilote natif refuse de s’arrêter, signaler l’échec et interdire une nouvelle capture ; ne pas annoncer une fermeture physique réussie.

## 3. Micro et double lecture : éviter deux fausses corrections

`capture_async()` utilise `to_thread` autour de `sounddevice.wait()`. Annuler la coroutine ne suffit pas à arrêter la capture physique.

1. Créer un propriétaire unique de la capture, avec demande d’arrêt et acquittement de fin. Préférer un flux audio possédé explicitement ; éviter d’interrompre une capture sans attendre sa terminaison puis d’en démarrer une seconde.
2. Implémenter un mode half-duplex partagé : réserver la parole avant lecture, empêcher une nouvelle capture, invalider le segment déjà commencé et demander son arrêt. Vérifier la génération du segment **avant STT et après toute attente** ; un segment invalidé ne doit pas être transcrit.
3. Ne jamais conserver le verrou audio pendant `runtime.idle()`, un appel réseau ou l’attente d’une ressource dont le propriétaire a besoin de ce verrou. Utiliser des transitions courtes et des événements pour les acquittements.
4. Dans `SpeechOutput`, remplacer la politique implicite de `gather` : si un lecteur échoue, annuler et attendre l’autre avant de vider les sous-titres. Un `TaskGroup` convient si les deux lecteurs nettoient réellement leurs processus sur annulation.
5. Découpler le retour texte des sorties facultatives et borner chaque sortie. Une voix défaillante ne doit ni effacer la réponse texte ni relancer le LLM.

**Tests requis :** les deux ordres capture/parole ; une seule capture physique ; zéro STT pour segment invalidé ; un lecteur échoue pendant que l’autre joue ; aucun lecteur restant, sous-titres vidés et texte livré. Ces tests utilisent de faux périphériques avant la recette Windows.

## 4. HTTP, délais et mémoire : un contrat commun

1. Faire transporter par la queue une enveloppe de travail : message, identifiant, échéance monotone, état d’annulation, résultat. Préserver l’interface des autres connecteurs par des valeurs par défaut.
2. Rendre un résultat terminal explicite pour succès, refus, expiration, arrêt et erreur fournisseur. Aujourd’hui l’erreur est seulement comptée par le runtime : le client HTTP attend alors inutilement 25 s. Régler chaque future au plus une fois, sans corps d’erreur fournisseur ni contenu privé.
3. Vérifier expiration/annulation juste avant appel LLM, avant validation de son résultat dans l’historique, puis avant TTS et diffusion. Un résultat arrivé trop tard ne doit ni parler ni modifier l’historique. Le délai global doit envelopper aussi les retries SDK.
4. Un timeout HTTP invalide le travail et annule l’appel actif lorsque possible. Une annulation d’un handler ne doit pas annuler le worker commun ou une autre requête. Aucun retry automatique de la requête expirée dans le MVP ; une idempotence ultérieure doit avoir un cache borné, pas une promesse de facturation « exactement une fois ».
5. Borner les handlers HTTP actifs **avant lecture**, les travaux en attente et les sessions. Une sémaphore avec une infinité de tâches en attente ne borne pas le nombre de connexions. Limiter aussi le temps total de lecture des en-têtes et l’attente d’écriture/fermeture.
6. Regrouper historique, IDs vus et verrou dans un état de session évictable. Ne pas évincer une session utilisée ou attendue ; TTL et nombre maximal globaux, tous deux testés. Refuser une nouvelle session si aucune éviction sûre n’est possible.

**Tests requis :** requête expirée en queue sans appel ; résultat tardif sans mémoire ni voix ; erreur fournisseur rendue sans attendre le timeout ; course timeout/résultat ; saturation des connexions ; réutilisation d’une session sans second verrou concurrent. Le compte d’appels après timeout est vérifié par des doubles.

## 5. Discord, configuration et installation

- Discord vocal : sérialiser `connect()`/`close()` et les événements `on_ready` concurrents ; nettoyer toute initialisation partielle, y compris un échec de `listen()`. Réinitialiser buffers et tâches à la déconnexion. Retirer les buffers vides ne suffit pas : expirer aussi les segments partiels abandonnés, sinon douze fragments peuvent encore exclure le treizième locuteur.
- Protéger l’admission Twitch **et Discord texte** contre `QueueFull` et l’état d’arrêt, sans casser leur connexion. Mentions Discord explicitement neutralisées ; paramètres de salons contrôlés avant activation.
- Un préflight positif doit correspondre aux conditions du lancement : présence FFmpeg pour Discord vocal, bonne distribution `discord.py`, fichiers de persona requis et chemins de sortie utilisables. `find_spec('discord')` seul ne distingue pas les piles incompatibles.
- Garder Poetry comme premier choix de lock, puisque le manifeste l’utilise déjà. Installer l’outil dans un environnement dédié sous D:, fixer sa version, vérifier la résolution Python 3.11 Windows et les extras choisis, puis réinstaller depuis le lock sans nouvelle résolution. Si une contrainte d’extra ne résout pas, corriger cette contrainte avec preuve, sans élargir toutes les versions au hasard.
- Première installation : checkout privé au commit de release et venv associé, lancé depuis la racine avec `main.py`. Le manifeste ne fournit pas à lui seul une application autonome avec prompt/profils ; ne pas substituer un wheel isolé sans recette de packaging. Garder la configuration privée existante séparée.

## 6. Git et CI : terminer sans perdre l’ascendance

1. Avant le push, refaire `fetch`, vérifier l’ascendance de la source PR dans le candidat et comparer les références courantes à celles revues. En PowerShell contrôler `$LASTEXITCODE` après chaque commande Git ; un échec de merge ne doit pas être suivi automatiquement d’un commit/push.
2. Pousser explicitement `HEAD:refs/heads/research/gpt6-jade-publication-readiness-20261028`, en avance normale seulement. Si refus pour divergence, récupérer et intégrer le travail concurrent, puis revalider. Aucun push implicite de la branche documentaire vers `develop`.
3. Adapter les triggers CI pour la branche source et `develop`, les PR vers `develop`, ainsi que `poetry.lock`, profils et workflows. Tester Windows/Python 3.11 au minimum, base et extras retenus. Préserver les tests offline sans clés ni capture.
4. Relever ensemble SHA source, SHA cible et SHA réellement testé. La métadonnée `base.sha` de PR #2 renvoie encore `fe4b7f4` alors que la référence de branche est `6420e24` : utiliser la référence Git courante pour les comparaisons. Revalider si la cible bouge.
5. Fusion finale par **merge commit**, sans squash/rebase, pour conserver la preuve que les branches rebuild/research sont incluses. Vérifier le nouvel arbre et l’ascendance de la source ; conserver toutes les branches historiques.
6. En cas de revert du merge, vérifier les parents et choisir celui de `develop` (normalement parent 1) ; un revert préserve l’ascendance et ne permet pas simplement de « remerger la même branche » pour réappliquer le code. Préparer ensuite de nouveaux correctifs ou une annulation du revert relue.

Le diagnostic Actions et les tests hors ligne peuvent avancer sans accès live. Les comptes, appareils, budget d’essai et recette des fonctions activées restent les seules preuves externes à obtenir avant leur mise en service ; aucune difficulté sur ces points ne doit arrêter les corrections indépendantes.
