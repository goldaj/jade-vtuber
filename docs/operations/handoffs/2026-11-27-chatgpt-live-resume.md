# DEV-055 · Reprise du Live mobile après interruption de conversation

- **Date :** 27 novembre 2026, Europe/Paris.
- **Demande :** retrouver la fin de « Planifier le live mobile », vérifier ce qui a réellement été livré et terminer les travaux nécessaires sur `develop`.
- **Branche de travail :** `fix/live-resume-audit-20261127`, depuis `develop@3d2f3ea72286241c658598bf4ec1e11671bec1c1`. Worktree distinct ; aucun travail local d'une autre mission écrasé.
- **Coordination :** agent principal, audit indépendant mobile, audit backend et revue fournisseur. Publication directe sur `develop` autorisée par la demande reprise ; aucune PR supplémentaire nécessaire.
- **Suivi :** DEV-055 porte les correctifs logiciels observés. REC-044 à REC-050 restent `À valider` pour les essais réels. DEV-041 garde la création/écoute/choix de voix ; DEV-052 demeure le chantier Discord futur.

## État retrouvé et périmètre

Le commit `3d2f3ea` était bien la tête publiée de `develop`, sans modification locale restante dans le worktree du chantier précédent. La [CI Linux/Windows](https://github.com/goldaj/jade-vtuber/actions/runs/45901475467) et le [scan des secrets](https://github.com/goldaj/jade-vtuber/actions/runs/45901475346) étaient réussis.

L'audit confirme les défauts ON global/mobile, la préférence classique explicite conservée, l'absence d'ouverture fournisseur au chargement du Profil, les baux avant capture et la suppression des montants mobiles. Le suivi d'usage reste passif, y compris en cas de panne ou de consommation élevée. Aucun plafond quotidien ou mensuel n'est réintroduit.

Les seuils de 50 EUR/mois, ou 40 EUR si suivi incomplet, concernent exclusivement la future décision Discord sur les dépenses de toutes les API. Ils ne pilotent ni la préférence ni les sessions mobiles. L'utilisateur avait demandé ce chantier après fonctionnement du lot mobile ; il n'est pas engagé par cet audit.

## Défauts reproduits et corrections

### 1. Format des événements serveur à la création Live

`LiveConfig.session_config` transmettait `allowed_server_events` sous forme de quatre chaînes. La [référence de création officielle](https://developers.openai.com/api/reference/resources/live/methods/create) exige des objets `ServerEventSelector` avec `type`. Le SDK OpenAI 3.42.1 épinglé par le projet confirme ce contrat : `DataChannelConfig.model_validate(..., strict=True)` rejette l'ancien payload. Un refus d'ouverture par le service réel était donc possible ; aucun HTTP 400 réel n'a été observé ici.

Les événements restent exactement `session.started`, `session.resumed`, `session.paused` et `session.closed`, maintenant sous forme `{"type": "…"}`. `allowed_client_events=[]` reste inchangé. La validation locale refuse avant réseau le mode global `all`, les anciennes chaînes et les sélecteurs mal formés ; `response_event` n'est admissible que pour `response.event`.

Le test de création contrôle le **corps HTTP réellement capturé** avec le modèle officiel du SDK, au lieu de seulement comparer le payload à un double qui accepterait la même erreur. Les deux tests ciblés échouaient avant correction (schéma officiel invalide et ancien format non refusé), puis réussissent. Aucun changement de SDK, de modèle ou de voix.

### 2. Message de fin de réponse conservé après arrêt

Après mute, le client écrivait « Micro coupé. Jade termine sa réponse. » dans le champ persistant des diagnostics. Celui-ci gardait la priorité d'affichage après expiration des 15 secondes ou fermeture serveur, alors que l'audio était déjà libéré.

Ce texte n'est plus mémorisé comme diagnostic : l'application sait déjà le déduire de `lease_state=draining`. Il disparaît donc avec cet état, sans effacer les incidents fournisseur. Régression reproduite avant correction ; scénarios timeout, terminal serveur anticipé et diagnostic conservé ajoutés à la suite existante.

### 3. Instruction résiduelle de budget dans le kit vocal

`live_voice.py` et le descriptif de `scripts/live_voice_preview.py` évoquaient encore un parcours mobile avec budget. Ces formulations sont retirées. Le kit reste une préparation hors ligne ; aucune candidate vocale n'est créée ou écoutée et aucune clé n'est modifiée.

## Vérifications et passe distincte

Avant correction, 97 tests backend et 35 tests pont/fournisseur/voix confirmaient les contrats déjà livrés ; les suites navigateur existantes réussissaient. Ces résultats ne couvraient pas le mauvais format des sélecteurs, maintenant testé contre le schéma officiel.

Après correction ciblée, 24 tests fournisseur/configuration réussissent. Quatre suites Node réussissent (client Live, Worklet, application Live et authentification). Les deux défauts fonctionnels ont été reproduits avant modification ; la suppression des seules formulations budgétaires n'ajoute pas de test miroir.

**Suite complète du lot :** 885 tests recensés en 41,343 s, aucun échec, 12 ignorés explicitement pour des composants Discord optionnels absents de cet environnement (873 tests exécutés avec succès). La suite inclut son export autonome et les tests exécutés dans cet export. Compilation, contrôle documentaire/backlog et `git diff --check` réussis.

**Passe distincte de validation de code du 27/11 : positive pour DEV-055.** Le sous-agent `/root/audit_live_backend` relit séparément les trois correctifs, confirme le schéma dans le SDK déjà épinglé, puis relance 24 tests config/fournisseur (0,050 s), deux suites Node et les trois tests de préparation vocale. Aucun nouveau budget, microphone, appel fournisseur ni élargissement des permissions. Le correctif logiciel est accepté pour intégration dans le commit portant cette fiche ; la recette OpenAI/Redmi reste ouverte. Les résultats de CI du nouveau commit doivent être vérifiés après sa publication, indépendamment de la CI verte de la base.

## Livraison et limites

Le présent lot est publié en un commit sur `develop`, avec `3d2f3ea` comme parent et sans réécriture d’historique. Le SHA final et la CI sont fournis dans la livraison de la mission.

Les fichiers modifiés sont `live_config.py`, `live_provider.py`, `live_voice.py`, le client mobile Live, leurs tests, le script de préparation vocale et les documents réellement impactés (journal, état fonctionnel, architecture, backlog et cette passation). `main` et les assets 2D ne sont pas concernés.

Le mécanisme de kill est codé, avec bail de 5 secondes, watchdog au plus toutes les 0,5 seconde, puis attente bornée de confirmation fournisseur. Cela ne prouve pas un arrêt instantané de la facture : une fermeture non confirmée reste visible et empêche une nouvelle session. L'accès effectif du compte, WebRTC/ICE, son, Bluetooth, kill Android et résidu facturé restent à observer sur le Redmi.

La voix configurée reste Brise ; Aube n'a toujours pas d'identifiant confirmé dans la référence API consultée. La voix originale exige les candidates, leur écoute et le choix du propriétaire.

Après mise à jour `develop`, redémarrer Jade et recharger la PWA. Une ancienne surcharge privée `JADE_LIVE_ENABLED=0` ou `JADE_MOBILE_LIVE_ENABLED=0` reste prioritaire sur le défaut ON ; un choix classique déjà enregistré dans Profil reste également conservé. Aucun secret du poste n'a été lu ni modifié par cette mission.

[État fonctionnel](../../handbook/BRANCH_STATE.md) · [Architecture](../../architecture/LIVE_MOBILE.md) · [REC](../../backlog/02-RECETTE.md) · [DEV](../../backlog/01-DEVELOPPEMENT.md).
