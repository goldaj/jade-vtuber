# Mission : implémenter Live mobile sur branche dédiée

- **Date :** 26 novembre 2026, Europe/Paris.
- **Responsable :** ChatGPT/Codex, avec contre-revues fournisseur/coûts, architecture/mémoire et mobile/QA.
- **Branche :** `feat/live-mobile-20261126`. Départ `f84bb876125c298e54194121065eb59d7fda0929` ; develop repris en fast-forward au `6dc8d1b7a2a2c9b0e7496a1fae268ddf43b62522`, sans conflit et sans perdre le travail en cours.
- **Autorisation :** réaliser le lot dans l'ordre utile, notifier chaque US, continuer en autonomie, conserver tout sur une branche dédiée. Aucun merge develop/main ni déploiement demandé. Pas de nouvelle PR publiée dans cette mission.
- **Plan initial :** [cadrage du lot](2026-11-26-chatgpt-live-mobile-roadmap.md) et [plan d'architecture](../../backlog/PLAN-LIVE-MOBILE.md).

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

La gouvernance interdit de conserver un DEV À valider doublonnant sa REC : les sept cartes implémentées sont transférées, avec leurs critères et références. **Aucune carte du lot n'est déclarée Done.** L'intégration develop est volontairement différée par instruction du propriétaire, et la recette réelle manque encore.

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

[Architecture actuelle](../../architecture/LIVE_MOBILE.md) · [Configuration technique](../../handbook/TECHNICAL.md#live-mobile--branche-dédiée-du-26-novembre-2026) · [État fonctionnel](../../handbook/BRANCH_STATE.md) · [Backlog](../../backlog/README.md).
