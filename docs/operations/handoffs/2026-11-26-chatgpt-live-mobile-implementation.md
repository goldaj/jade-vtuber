# Mission : implémenter Live mobile sur branche dédiée

- **Date :** 26 novembre 2026, Europe/Paris.
- **Responsable :** ChatGPT/Codex, avec contre-revues fournisseur/coûts, architecture/mémoire et mobile/QA.
- **Branche :** `feat/live-mobile-20261126`. Départ `f84bb876125c298e54194121065eb59d7fda0929` ; develop repris en fast-forward au `6dc8d1b7a2a2c9b0e7496a1fae268ddf43b62522`, sans conflit et sans perdre le travail en cours.
- **Autorisation initiale :** réaliser le lot dans l'ordre utile, notifier chaque US, continuer en autonomie, conserver tout sur une branche dédiée. La branche a été conservée séparée jusqu’à la demande suivante. Aucun déploiement ni modification de main effectué dans cette mission.
- **Plan initial :** [cadrage du lot](2026-11-26-chatgpt-live-mobile-roadmap.md) et [plan d'architecture](../../backlog/PLAN-LIVE-MOBILE.md).

## Intégration sur develop autorisée le 26 novembre 2026

Le propriétaire demande : « Ok tu peux mettre tout ça sur develop, je vais faire le teste ». Le lot logiciel `90ec0c757cc0eb2f31ed44c49923ab10bbfb449c` et la mise à jour develop concurrente `b4a85e8acaaa849affa83672ad884f8fde927298` partagent la base `6dc8d1b7a2a2c9b0e7496a1fae268ddf43b62522`. La fusion conserve les deux historiques et les nouvelles cartes DEV-053 / ART-014, leurs critères complets et leur passation. Le chevauchement documentaire est résolu en réunissant les cartes, les rangs et les compteurs (111 cartes uniques), sans conflit de code ni réécriture de l’historique. La documentation courante est actualisée pour refléter cette intégration. Les REC-044 à REC-050 restent À valider ; l’accord de fusion ne constitue pas une recette fonctionnelle.

Le code intégré reste identique au lot validé par les 864 tests (12 skips Discord optionnels). Les contrôles de documentation/backlog et l’absence de changement de code sont vérifiés à nouveau. Les flags et budgets privés ne sont pas modifiés sur le poste du propriétaire. `main` ne fait pas partie de cette intégration.

**Vérification CI après fusion `2b80c31` :** l'étape navigateur, distincte de la suite Python, échoue dans `mobile_avatar_models_test.js` sur l'extraction HTML du Profil. Le test s'arrêtait au premier `</section>`, qui ferme maintenant le bloc Live imbriqué ; une lecture structurée confirme que le sélecteur demeure dans le même parent Profil, exactement une fois, comme sur la base `6dc8d1b`. Le correctif compte les sections jusqu'à la fermeture correspondante et garde les assertions d'appartenance et d'unicité. Les 25 commandes navigateur du workflow sont revérifiées après correction ; aucun fichier de runtime, HTML ou asset n'est modifié par ce suivi. Le scan des secrets et le contrôle de migration ont réussi sur la fusion ; la CI complète est relancée avec le correctif du test.

**Suite Windows au `182a8a3` :** Linux et le scan des secrets réussissent. [La suite Windows](https://github.com/goldaj/jade-vtuber/actions/runs/45889890142/job/140149686859) détecte des assertions avant la fin des opérations dans trois scénarios de `test_live_bridge.py` (rattrapage des fragments, invalidation de l'historique et rétention d'une longue demande) ; l'export isolé remonte le même défaut de test. Le pont clôture volontairement dans un délai borné et continue la persistance hors ligne ; la fixture de test limitait ce délai à 100 ms, puis lisait les données et supprimait les fichiers sans attendre la tâche de persistance. Le test de fragments imposait aussi une fenêtre de 40 ms aux écritures SQLite. Les tests synchronisent les opérations qu'ils veulent observer et attendent leur achèvement avant de supprimer leur répertoire temporaire. Le contrat de fermeture bornée du produit et son test restent conservés, sans augmentation du délai de fermeture ni modification du code de production. Les résultats de cette correction doivent être jugés sur la nouvelle CI, pas sur le passage Linux seul.

**Fermeture du contrôle Live, après `8c10150` :** la nouvelle CI Windows réussit **864 tests, 2 skips**, ainsi que le scan des secrets. Le job Linux atteint sa limite de huit minutes dans `test_real_http_creation_uses_opaque_handle_and_stop_survives_feature_off` ; l'export isolé avait également dépassé sa limite. Une reproduction déterministe sur de vraies sockets locales confirme le défaut produit : si un envoi absorbe une annulation, le `gather` de nettoyage précédant `unsubscribe` garde le bail armé et aucune commande `session.close` n'est émise. Le cas est cohérent avec la [course connue de `asyncio.wait_for`](https://github.com/python/cpython/issues/86296) sur les versions antérieures à son changement d'implémentation.

Le correctif conserve les délais réseau et utilise `asyncio.timeout` (compatible avec le minimum Python 3.11 du projet), pose un état de fermeture avant annulation, puis désabonne le contrôle et déclenche la clôture fournisseur avant d'attendre le nettoyage. Celui-ci utilise `asyncio.wait` borné à une seconde, renouvelle l'annulation des tâches restantes et collecte leurs exceptions sans contenu privé. Les deux boucles de contrôle ne repartent plus après fermeture. La reproduction reste en test de régression ; les assertions de clôture fournisseur ne sont pas retirées. Les tests ciblés du transport classique et Live, puis la suite exportée, couvrent ce correctif avant publication. Les essais avec un vrai compte OpenAI et le Redmi restent dans les REC ouvertes.

**Validation du correctif de fermeture :** 19 tests des modules `test_mobile_live_gateway` et `test_jade_mobile_duplex` réussis ; le cas d'export rejouant toute la suite réussit en 21,379 s. Contrôles documentaires et `git diff --check` réussis. Contre-revue indépendante architecture favorable : invalidation avant nettoyage, terminal fournisseur conservé et tâche d'envoi effectivement terminée. Exécution locale Python 3.12 ; le scénario d'annulation absorbée est injecté pour reproduire le défaut sans prétendre disposer localement d'un interpréteur 3.11. La CI du nouveau commit apporte la validation supplémentaire sous Python 3.11 sur Linux et Windows.

## Résultat par US

| Ancienne US | Code livré | Suivi unique actuel | Preuve et limite |
| --- | --- | --- | --- |
| DEV-046 | Fournisseur HTTP/WebRTC/sideband, config/voix, routes privées, préflight, raccord runtime | REC-044, À valider | Faux fournisseur et vraies sockets loopback ; accès du compte, voix et réseau réel non testés |
| DEV-048 | Bail exclusif, watchdog, idle, mute borné, fermeture confirmée, registre et reprise | REC-045, À valider | Courses OFF/création, expiration, panne SQLite, transport lent et terminal absent ; kill Android/fournisseur réel restant |
| DEV-051 | Ledger durable, réservations voix/backend, compteurs cumulés, limites et métriques | REC-046, À valider | Concurrence, Paris/DST/mois, inconnus, estimations ; facture et benchmark A/B physique restants |
| DEV-049 | Persona/contexte communs, délégations arbitrées, outils, journal, L1 et curation différée | REC-047, À valider | Vrai Runtime/MemoryStore/DocumentService avec fournisseur simulé ; parcours vocal réel restant |
| DEV-047 | Capture locale, VAD/pré-roll, Worklet/WebRTC, contrôle réciproque et nettoyage | REC-048, À valider | Ordre d'échantillons synthétiques, permission/SDP tardifs, mute et pertes ; acoustique/écho/Bluetooth/Redmi restants |
| DEV-050 | Segments de chat, fichiers, états de lecture et avatar piloté par le son distant | REC-049, À valider | Suites JS, rejeux, interruption et génération ; lip-sync physique r20/r21 restant |
| DEV-040 | Profil ON/OFF, préférence révisionnée et transitions avec le classique | REC-050, À valider | Tests app/gateway ; 20–30 bascules et non-régression PTT sur téléphone restant |
| DEV-041 | Catalogue/configuration, ID personnalisé, prompt et corpus hors ligne | DEV-041, En cours | Aube API non confirmée, Brise explicite ; aucune voix créée/écoutée, choix propriétaire restant |
| DEV-052 | US future détaillée | DEV-052, À qualifier | Seuil Discord global 50/40 EUR, tous fournisseurs, mois Paris, correction/retard et indépendance mobile ; aucun adaptateur/automatisme Discord développé |

La gouvernance interdit de conserver un DEV À valider doublonnant sa REC : les sept cartes implémentées sont transférées, avec leurs critères et références. **Aucune carte du lot n'est déclarée Done.** L’intégration sur develop est désormais autorisée et réalisée ; la recette réelle manque encore.

## Choix et correctifs de la contre-revue

- API Live distincte du Realtime TTS classique, avec configuration serveur et clés conservées côté Jade. Le SDK épinglé reste inchangé ; ses schémas incomplets justifient le transport JSON.
- Préférence, bail local et génération payante séparés. Le Profil n'ouvre rien ; l'armement doit précéder la permission. Idle ferme le fournisseur, arrêt fort ferme aussi l'armement.
- Pas de replay automatique d'une création, d'un énoncé ou d'une action d'issue inconnue. Le terminal fournisseur est enregistré avant les écritures d'historique ; un disque indisponible ne doit jamais empêcher l'envoi du close.
- Fermeture bornée sans attendre indéfiniment le nettoyage WebSocket ni le rejeu de `session.started`. Les erreurs de stockage optionnel désactivent Live tout en préservant le démarrage du mobile classique ; les IDs payants lisibles restent réconciliés.
- Coût backend conservateur, qualifié **estimé**, à partir du montant initial réservé ; tokens, frais outils et factures ne sont pas confondus. L'annulation ne crée aucune preuve de gratuité.
- Curation différée à la prochaine session active et soumise à réservation. OFF/kill ne lance pas un nouvel appel facturé. Le consentement/person_id est revérifié lors de l'écriture L1.
- Un unique dispatch d'intention sert classique et Live. Les médias, tracks, worklets et événements tardifs sont invalidés par génération. Les assets/rig 2D ne sont pas retouchés.

## Vérifications

Les suites sont exécutées dans un environnement Python 3.12 avec le SDK OpenAI 3.42.1, les dépendances projet utiles et Node. Les fournisseurs sont simulés ; HTTP/WS de contrôle sont réellement exercés en loopback. Aucun microphone, compte OpenAI ou appareil externe n'est activé.

**Résultat global final : 864 tests exécutés en 41,454 s, zéro échec, 12 skips explicites** (12 scénarios nécessitent la pile Discord optionnelle absente du runner). La suite inclut le contrôle de fermeture de l’export de prévisualisation, qui exécute sa propre copie isolée des tests hors ligne. Compilation, contrat documentaire/backlog, `git diff --check` et audit des fichiers suivis réussis. Les trois programmes JavaScript Live sont exécutés comme sous-tests, sans audio réel.

Commandes reproductibles depuis le dépôt :

```bash
python -m unittest discover -s tests -v
python -m compileall -q src main.py
python scripts/check_docs.py
git diff --check
```

Les suites Live couvrent fournisseur/configuration/voix, budget, manager, pont métier, intégration runtime, gateway HTTP/WS et trois programmes JavaScript client/Worklet/app. Les régressions couvrent le runtime classique, la mémoire, les outils, le PTT, l'avatar, le préflight et l'export de prévisualisation.

**Défaut de baseline identifié séparément :** sur le worktree develop propre `6dc8d1b`, `test_jade_mobile_ui_contract` échoue sur l'ancien sélecteur `.room-art[data-room="kitchen"]::before` (4 tests, 1 échec). Le décor portrait masque désormais `room-art` en chambre et le sélecteur cuisine est `.room-art::before`. L'assertion est actualisée et contrôle également le masquage de la chambre ; aucun asset ni style de décor n'est modifié pour faire passer le test.

L'export de prévisualisation inclut les deux nouveaux scripts Live ; l’absence de service Live laisse le parcours classique indépendant, sous réserve de la disponibilité de son backend habituel. Les bibliothèques d'environnement manquantes ont été installées dans le venv de test, sans changer les dépendances épinglées du dépôt.

## Passe de validation distincte

Les experts ont relu leurs contrats croisés après raccordement, puis exécuté des tests d'intégration réels hors réseau fournisseur. Les constats de fermeture sur erreur SQLite, nettoyage borné, token WS Unicode, génération tardive, montant de réservation initial et double dispatch avatar ont été corrigés et retestés. Cette passe valide la livraison logicielle sur branche ; elle ne remplace pas les critères matériels/fournisseur des REC.

## Configuration, risques et reprise

Les flags et budgets par défaut restent fermés : `JADE_LIVE_ENABLED=0`, `JADE_DISCORD_LIVE_ENABLED=0`, plafonds USD et réserve backend à 0. Le mode choisi dans Profil est persistant ; l'armement ne l'est jamais. Aucun secret n'a été lu, créé ou publié pour ce lot.

Avant pilote, configurer les plafonds et la réserve backend dans le fichier privé, vérifier le compte/modèle/voix, puis exécuter le préflight. Aube reste demandée ; faute d'ID public confirmé, Profil décrit Brise sans alias trompeur. La création de voix originale et les préécoutes sont une dépense séparée à tracer ; le script livré n'en déclenche aucune.

Les trois bases Live sont privées et séparées de la mémoire principale : budget, registre de préférence/session et journal. Elles ne doivent pas entrer dans Git ni être supprimées pour contourner un état inconnu. Un registre lisible permet de retenter la clôture d'un ID connu au prochain démarrage. Un coût ou une création sans ID non réconciliés restent bloquants ; ne jamais les considérer comme zéro par simple expiration locale.

Pour revenir au code classique, couper le mode/flag et obtenir les terminaux des sessions connues avant de changer de branche. Conserver les bases privées pour réconciliation. Le schéma principal de mémoire ne subit pas de migration destructive ; les nouveaux journaux peuvent rester présents lors du retour au classique.

**Ordre restant :** validation réelle d'arrêt/budget et transport sur Redmi, parcours mémoire/outils/transition, mesures A/B et choix vocal. Ensuite seulement qualifier DEV-052 et son adaptateur Discord. Les limitations matérielles ne justifient aucune ouverture de microphone PC, Twitch ou OBS, toujours suspendus dans leurs cartes distinctes.

[Architecture actuelle](../../architecture/LIVE_MOBILE.md) · [Configuration technique](../../handbook/TECHNICAL.md#live-mobile--intégration-develop-du-26-novembre-2026) · [État fonctionnel](../../handbook/BRANCH_STATE.md) · [Backlog](../../backlog/README.md).
