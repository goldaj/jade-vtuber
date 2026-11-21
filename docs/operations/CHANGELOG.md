# Journal technique unique — develop

Ce document est **la seule pièce documentaire systématiquement exigée en CI** pour les changements techniques. Les guides, atlas et passations sont révisés uniquement quand le comportement ou les procédures qu'ils décrivent changent. Une entrée indique les faits vérifiés ; un ancien journal ne remplace pas le code.

## 2026-11-21 — Six évolutions économiques : mémoire, sociabilité, initiatives, voix et mobile (PR #34)

- **Produit :** historique SQLite intégral 24 h **conservé**, avec sélection lexicale locale plafonnée pour le prompt ; L1 7 j, L2 ordinaire 365 j, Core sans expiration inchangés. Curation par lots de 3 événements au plus, délai court et validation autonome des Core. Personnalité enrichie uniquement des souvenirs autorisés, sans nouvel appel IA.
- **Sociabilité :** sélection locale prioritaire ; second avis LLM facultatif uniquement sur questions ambiguës de groupe et seulement avec budget USD de classification configuré. Aucun polling du modèle en période sans intervention humaine.
- **Initiatives :** déclencheur de première version = arrivée d'un humain dans le vocal Discord de Jade, qui peut émettre un salut écrit dans le chat natif du salon **sans préalable verbal**. **Si personne ne répond, aucune relance autonome dans ce salon** ; un message humain réel ou la réouverture d'un salon précédemment vidé réarme la possibilité. Pas de nombre maximum journalier. Initiatives **actives par défaut**, budgets financiers facultatifs ; `0` pour les deux budgets initiatives signifie non plafonné et n'empêche pas le salut. Aucune session LLM de veille en silence.
- **Mobile :** WebSocket propriétaire sous Tailscale Serve, entrée PCM16 découpée pendant l'enregistrement, STT OpenAI existant après fin de phrase, réponse texte et TTS progressifs, annulation, VAD de silence local et maintien du repli historique WAV. Aucune API conversationnelle Realtime supplémentaire. Copie autorisée de `duplex-client.js` dans l'aperçu privé de publication.
- **Contrôles :** `CostGuard` stocke dans le SQLite privé uniquement des hashes d'événements et réservations de dollars **estimées**, pas une facture certifiée. Rollback par flags (`JADE_INITIATIVES_ENABLED`, `JADE_SOCIAL_HYBRID_ENABLED`, `JADE_MEMORY_BATCH_ENABLED`, `JADE_SELECTIVE_CONTEXT_ENABLED`). Les limites USD se règlent par variables dédiées et n'excluent pas des dépassements d'estimation ; prévoir un plafond fournisseur si besoin de limite financière stricte.
- **Tests et preuves :** `test_jade_economy_memory.py`, `test_jade_economy_social.py`, `test_jade_mobile_duplex.py`, tests historiques, `tests/mobile_stream_client_test.js`, compilation Python et JavaScript, vérification des secrets via GitHub Actions. Une passe CI antérieure (PR #34, SHA `2f177387`) a réussi hors ligne ; **la validation finale doit porter sur le SHA d'intégration**, et aucune recette physique PC, Android ou Discord/Tailscale n'est déclarée ici.
- **Fichiers et design :** `context_selection.py`, `memory_batch.py`, `memory_service.py`, `personality_evolution.py`, `social_intelligence.py`, `initiatives.py`, `cost_guard.py`, `dialogue.py`, `discord_text.py`, `discord_voice.py`, `main.py`, `config.py`, `mobile_duplex.py`, `mobile_gateway.py`, scripts PWA, workflow CI et doc d'architecture. **Pas de secrets, de mémoire personnelle ni de modifications sur `main`.**

## 2026-11-21 — Souvenirs transversaux privés pour les comptes liés (develop)

- **Produit :** dans la PWA, le micro PC et les MP Discord, Jade retrouve les souvenirs condensés des autres portées d'un même profil ayant au moins deux identités authentifiées liées. Maximum huit souvenirs dans le contexte dont quatre d'autres portées ; la mémoire locale de salon reste prioritaire.
- **Garde-fou léger :** aucun souvenir d'une autre portée n'est chargé dans les salons publics Discord/vocaux ou Twitch. L'historique complet de niveau 1 reste par salon ; seuls les résumés de niveau 2 et les Core relationnelles stockées dans `memories` circulent en privé. L'autobiographie `jade_self_core` reste propriétaire.
- **Technique :** nouvelle lecture SQL `MemoryStore.recall_linked` appelée conditionnellement par `MemoryService.context_for`, sans migration SQLite, réécriture des enregistrements ni appels IA supplémentaires. Conservation 7j/365j/Core, code de liaison 5 minutes, autonomie Core, effacement et déliaison inchangés.
- **Fichiers et QA :** `memory_store.py`, `memory_service.py`, texte de la PWA, tests `test_jade_cross_channel_memory.py`, guides/état de develop et passation. Un test historique (`test_jade_explicit_memory_request.py`) attendait encore une activation manuelle en MP Discord et a été remis en phase avec la décision du 21/11. La CI Linux a ensuite réussi ; le passage Windows a identifié un verrou temporaire de SQLite dans le nouveau test d'expiration, corrigé par fermeture explicite via `contextlib.closing`. Vérifier la CI finale sur ce commit et conserver la recette PC/Discord/Android au propriétaire.

## 2026-11-21 — Mémoire automatique en MP Discord et clarification de la liaison mobile (develop)

- **Produit :** inscription mémoire automatique pour un compte Discord vérifié dès un tour traité en MP, comme en serveur et en vocal ; aucun pseudonyme ne vaut identification et Twitch reste sur activation explicite. L'opt-out durable Discord via `!jade-memoire oublier` et le retour volontaire via `!jade-memoire activer` restent prioritaires.
- **Mobile :** instructions en trois étapes distinguant précisément les commandes à exécuter sur Discord ou Twitch, la saisie de l'ID sur la PWA et la confirmation de retour sur le même compte. Le libellé précise que **seul le code à usage unique expire après cinq minutes**, tandis que la liaison confirmée reste sans limite de durée. Aucun changement du TTL, des règles de vérification des comptes ou de l'isolation par salon.
- **Sources :** `memory_service.py`, PWA `index.html`/`app.js`/`styles.css`, tests d'inscription Discord/MP et liaison HTTP, consignes de projet, `BRANCH_STATE.md`, guides utilisateur/technique et passation.
- **Contrôle :** régressions ajoutées pour MP Discord par défaut, effacement empêchant la réinscription en MP et en serveur, confirmation depuis un MP sans activation manuelle et isolation des historiques. Exécution Python locale, CI GitHub et recette PC/Android à vérifier ; ne pas les déclarer acquises avant leurs résultats.
- **Vigilance :** informer les correspondants Discord, notamment en MP, du stockage et de la conservation ; les règles de confidentialité et la désactivation explicite ne changent pas.

## 2026-11-20 — Politique de conservation Jade : 7j / 365j / Core sans purge (feat/memory-retention-7d-365d-24h-20261120)

- **Stockage :** migration SQLite v3→v4, niveau 1 `conversation_turns` purgé après 7 jours, souvenirs ordinaires `memories.kind=ordinary` expirant après 365 jours depuis `created_at`, même pour les anciennes lignes v3. Core Memories relationnelles et autobiographiques jamais purgées par la politique temporelle ; correction/effacement explicite préservé.
- **Reprise :** récupération de tous les tours datés des 24 dernières heures, pour la même identité et le même salon ; suppression des limites numériques 24 échanges / 48 messages sur les sessions réhydratées. Le modèle peut atteindre sa fenêtre de contexte et augmenter la consommation de tokens, mais Jade ne tronque plus arbitrairement en nombre de messages.
- **Exploitation :** nettoyage immédiat à l'ouverture de la base et périodique toutes les heures en mode réel, avec arrêt propre de la tâche asynchrone ; la démo hors ligne reste non persistante.
- **Qualité :** tests de purge 7 jours, expiration 365 jours, non-expiration Core, compatibilité de sauvegarde v4, récupération de plus de 100 tours, isolation, réhydratation dans le runtime ; résultats CI à valider au SHA de la PR.
- **Attention migration :** sauvegarder le fichier SQLite privé avant redémarrage ; cette purge supprime effectivement les anciens tours, sans garantie d'effacement physique des copies de sauvegarde.

## 2026-11-20 — DEV-011 révisée : souvenirs ordinaires sur demande, Core Memories autonomes (fix/dev-011-ordinary-only-autonomous-core-20261120)

- **Décision du propriétaire (postérieure à la PR #29) :** aucune personne, y compris Goldaj, ne peut imposer de Core Memory profonde. Le développement de la PR #29 permettant à Goldaj de créer directement `core_self`/`core_relationship` est **remplacé** par ce correctif ; les anciennes notes de la PR sont historiques, pas le comportement attendu.
- **Code :** nouveau `explicit_memory_intent.py` (français oral/écrit), retrait de `owner_core_intent.py` et de `MemoryStore.put_owner_core`, interception par `memory_service.py` sans appel LLM ni curation, écriture transactionnelle `MemoryStore.put_requested_ordinary` (`kind=ordinary`, TTL 90 jours, identité/salon et doublons vérifiés). Même une demande « Core Memories » est enregistrée **uniquement en ordinaire**, avec réponse explicite.
- **Autonomie :** seule la curation de Jade peut ensuite choisir des Core Memories indépendamment des instructions de l'utilisateur ; le traitement d'une demande explicite ne déclenche jamais cette curation. Les commandes privées de lecture/effacement Core existantes sont maintenues pour la protection des données, sans droit d'écriture forcée.
- **Vérifications :** tests ciblés de grammaire STT, refus des faux ordres, unicité, expiration, oubli, écriture SQL, cloisonnement, refus des secrets, runtime sans LLM et curation Core autonome ; résultats CI Linux/Windows consignés dans la passation. Aucune recette sur le PC réel.

## 2026-11-20 — DEV-011 Core Memories explicites par Goldaj (feat/dev-011-explicit-owner-core-memories-20261120)

- **Code :** `owner_core_intent.py` (demande naturelle explicite), `memory_service.py` (interception prioritaire, confirmation réelle), `memory_store.py` (transaction Core propriétaire, catégorisation, refus des comptes non liés, déduplication et effacement des souvenirs autobiographiques de comptes liés, y compris par commande propriétaire), ainsi que commandes privées `lister-core`/`supprimer-core` pour les Core relationnelles.
- **Comportement :** instruction texte ou voix de Goldaj authentifié ; écritures `core_self` et `core_relationship` pérennes sans attente du LLM ; réponses ne divulguant pas le contenu sur les salons publics. Refus des identités non reconnues, des textes vides ou trop longs et des secrets courants.
- **Vérifications :** tests unitaires de parsing, identité, liaison, oubli, suppression, redémarrage, isolation, doublons, SQL en échec et runtime sans appel LLM ; CI GitHub Actions Linux et Windows réussie (run `44816114240`), contrôle des secrets réussi (run `44816114280`). Pas de recette physique sur le PC/Discord propriétaire depuis cet environnement.
- **Risques :** l'interprétation des variantes non explicitement reconnues retombe sur le dialogue usuel ; ne pas confondre une réponse de langage avec une confirmation SQLite. La création d'une Core Memory par une instruction du propriétaire est volontaire, non une preuve indépendante des faits rapportés.

## 2026-11-20 — Mémoire persistante active et inscription Discord sans commande (branche feat/auto-memory-discord-20261120-v2)

- **Configuration / runtime :** conserver les nouveaux défauts `JADE_MEMORY_ENABLED=1` et `JADE_MEMORY_CURATOR_ENABLED=1` apportés sur `develop`, ajouter un chemin SQLite privé et absolu par défaut (`D:\\Jade\\private\\jade-memory.sqlite3` si D: existe sous Windows ; `~/.jade/jade-memory.sqlite3` ailleurs), ne pas créer de base pendant la démo hors ligne. Les variables privées explicitement à `0` continuent de primer.
- **Identités / conservation :** inscrire automatiquement un utilisateur identifié lors d’une interaction effectivement traitée sur un serveur Discord (texte ou voix). Garder une activation explicite pour les messages privés Discord et Twitch. Ne pas fusionner les profils ni lever les restrictions de salon.
- **Droit d’effacement :** `!jade-memoire oublier` supprime les données du compte et interdit les réinscriptions automatiques Discord, même après redémarrage ; réactivation volontaire via `!jade-memoire activer`. Nouvelle table additive `memory_auto_enrollment_blocks` conservant uniquement les identifiants requis au refus, sans changer le numéro de schéma SQLite v3.
- **Vérifications :** tests de régression ajoutés pour les défauts, l’enregistrement, l’isolation, les MP, Twitch, le refus persistant et la compatibilité v3. Exécution CI à contrôler ; aucune validation sur le PC réel revendiquée.
- **Risques / exploitation :** informer clairement les membres Discord avant leur participation, garder le fichier SQLite privé et réutiliser le chemin d’une éventuelle base existante ; la curation active ajoute potentiellement des appels API facturés.

## 2026-11-16 — Réorganisation du dépôt (branche chore/develop-repository-cleanup-20261116)

- Démonstrations : garder `demo/express/` ; retirer `demo/reelle/` et `demo/windows/` et leurs tests spécifiques. **Le renderer r20 auparavant dépendant de `demo/reelle/avatar.py` est déplacé vers `src/jade_runtime/avatar_renderer.py`**, avec son appel mis à jour. Les tests du protocole avatar et du TTS de production sont conservés sous des noms `test_jade_*`.
- Documentation : séparer `docs/handbook/`, `docs/architecture/`, `docs/ameliorations/`, `docs/operations/` et `docs/history/`; reclasser les fichiers historiques sans les jeter, réparer leurs liens et définir les lieux de passation inter-agents.
- Hygiène : supprimer du suivi Git les huit fichiers `.idea/`, les ignorer à l'avenir et retirer trois anciennes branches des triggers `jade-rebuild.yml`.
- Contrat documentaire : remplacer l'obligation de rééditer neuf guides à chaque changement par l'unique entrée changelog technique, avec vérification des liens locaux des guides actifs et actualisation ciblée des documents affectés.
- Transparence : expliciter que `goldaj/jade-vtuber` est déjà public et que les contrôles de provenance, droits et secrets ne sont pas automatiquement acquis.
- Modélisation : inspection des 221 fichiers Git de `jade-modeling/` : aucun SHA de blob strictement dupliqué ; aucun art source, checkpoint ni outil de rigging supprimé sans preuve d'inutilité.
- **Validation** : état des modifications constaté dans GitHub sur cette branche ; exécution complète des tests, du rendu Windows et contrôle des objets LFS matériels à confirmer via CI/poste local.

## Format des entrées futures

`YYYY-MM-DD — <mission> (<branche>, <PR/commit>)` : changement observable, références code, documentation impactée, contrôles réellement effectués, limitations et suivi. Ne pas recopier les mêmes lignes dans tous les manuels.


## 2026-11-16 — Discord PCM, liaison mémoire et PWA (PR #23, branche fix/discord-pcm-memory-mobile-20261116)

- **Code :** supprimer le verrou erroné entre `ffplay` (micro local) et streaming PCM Discord ; continuer à autoriser le mode phrases facultatif seulement pour Discord vocal autorisé.
- **Mémoire :** conserver les tours SQLite complets lors de `complete_link` et d'un `unlink` non ambigu, en regroupant `discord`/`discord_voice` et `microphone`/`mobile` ; codes à cible vérifiée valables 5 min, invalidation du code précédent, masquage dans les logs **et le contexte Discord** ; commande d'identification technique avant confirmation.
- **Mobile :** PWA Goldaj uniquement, `POST /api/link` avec la double authentification déjà existante, formulaire et copie de commande. Le SDK Live2D Web reste une dépendance du PC, aucun bundle propriétaire ajouté.
- **Tests / impacts :** régressions PCM all-channels, liaison/historique et API propriétaire, mises à jour du guide utilisateur, technique, état de branche et fiche de passation. Les résultats CI, les essais matériels, coûts et latence ne sont pas présumés. Aucun déploiement matériel effectué ; statut de fusion de la PR #23 à consulter sur GitHub.
- **Revue sécurité finale :** `oublier` via Discord/Twitch ne peut plus effacer le profil entier de Goldaj ; il ne supprime que les données de l'identité demanderesse. Commande `delier` conservant les données ; isolation des anciens historiques sous réserve d'identités non ambiguës ; masquage des codes temporaires y compris avant arbitrage IA. Tests spécifiques ajoutés.
- **Limites :** fallback WAV et ancien broadcast non refondus ; profils multi-comptes d'une même plateforme avec vieux tours non attribuables nécessitent une revue manuelle pour la déliaison ; Live2D mobile réel reste à installer/recetter.

- **Revue croisée complémentaire (branche de PR #23) :** lecture du dernier `develop`, maintien des nouvelles règles documentaires et tests de régression d'identités et de confidentialité. La suite complète et le scan de secrets doivent être vérifiés au SHA final de la PR ; recette réelle PC/Android/Discord toujours ouverte.

## 2026-11-18 — Contrôles backlog et simplification de la reprise des agents (`develop`)

- **Code de contrôle documentaire :** `scripts/check_docs.py` inclut désormais `docs/backlog/` dans le contrôle des liens Markdown locaux et impose la présence/non-vacuité de ses six documents canoniques (index, DoD et quatre vues) dans la CI existante. Aucune nouvelle CI ni obligation documentaire générale ajoutée.
- **Process :** un commit par lot cohérent quand possible (pas par fichier), limite souple de trois cartes simultanées, reprise prioritaire en tête de l'index, formulaire de recette court réutilisable dans une passation existante ; DoD Codex **OU** propriétaire inchangée.
- **Git :** audit distant de 23 branches de travail (14 pointes ancêtres, 8 divergentes, 1 à recontrôler), sans suppression, force push, changement de visibilité ou modification de `main`. Les contrôles matériels et réglages de protection restent explicitement à réaliser dans la prochaine session adaptée.
- **Fichiers :** `scripts/check_docs.py`, `docs/operations/CHANGELOG.md`, `docs/backlog/README.md`, `docs/backlog/02-RECETTE.md`, `docs/handbook/BRANCH_MAINTENANCE.md`, `AGENTS.md`, `docs/operations/AGENT_COORDINATION.md`, `README.md`.
- **Validation à observer après push :** workflows Windows/Ubuntu hors ligne et secret-scan sur le nouveau SHA. Les validations réelles PC/Android/Discord/Twitch/Cubism, l'administration des branches et la protection de `main` n'ont pas été réalisées depuis ce chat.

## 2026-11-18 — Confidentialité OBS et intégrité backlog (DEV-004, P0)

- **Correctif :** `src/jade_runtime/output.py` masque les sous-titres OBS des DM Discord et des sources privées pendant la lecture WAV, avec garde défensive équivalente dans le chemin PCM. Les sous-titres des sources publiques restent disponibles ; les réponses mobiles sont normalement servies par leur passerelle dédiée.
- **Tests :** `tests/test_jade_discord_dm_voice_privacy.py` observe le fichier de sous-titres pendant la lecture pour DM, microphone, HTTP, mobile, Discord public et Twitch public. Le test préexistant couvre la non-facturation TTS en l'absence de destination autorisée.
- **CI :** `scripts/check_docs.py` contrôle IDs uniques, statuts, priorités, dépendances manquantes/cycliques, rangs et compte des sections du backlog ; `tests/test_docs_backlog_contract.py` couvre la vérification du référentiel et une dépendance inconnue.
- **Produit :** DEV-004 créée en P0, non Done tant que tests CI et validation Codex/propriétaire ne sont pas documentés ; REC-005 reste ouverte pour la recette réelle OBS et du mixage audio. Total : 58 tâches opérationnelles.
- **Limites :** aucun essai réel sur Discord, OBS, le PC ou l'audio du propriétaire ; la refonte du routage reste hors périmètre. Vérifier les workflows au SHA final.

## 2026-11-19 — Cinq quick wins routage, voix et latence (DEV-003/005–008)

- **DEV-005** : `main.py` supprime le TTS pour les réponses écrites Discord, Twitch et HTTP, et `turn_logging.py` aligne les destinations ; voix console explicitement demandée et micro local préservés.
- **DEV-003** : chemin WAV `discord_voice` limité à la session Discord autorisée, jamais au lecteur local ; révocation annule la lecture. REC-005/007 physiques toujours ouvertes, aucune fuite matérielle alléguée.
- **DEV-006** : hotkey VTS exécuté par tâche asynchrone suivie, annulée au shutdown ; aucune attente avant la voix et aucun hotkey pour les écrits.
- **DEV-007** : synthèse Realtime bufferisée utilise le même pool WebSocket que le PCM progressif ; le retry sans création de réponse et le lock existants sont préservés.
- **DEV-008** : `jade.latency` mesure les jalons file, mémoire, LLM, diffusion, fin/échec de chaque canal sans texte ni identités ; coût réel, STT, premier son et p95 de production restent REC-010.
- **Contrôles** : régressions ajoutées/actualisées, CI Ubuntu/Windows et scan secrets à relever sur PR, aucun appel fournisseur payé, PC/Android/Discord/OBS/VTS non testés matériellement.
- **Livraison** : branche `feat/jade-quickwins-routing-voice-metrics-20261119` depuis `develop` `fba75d4`, sans modification de `main`.

- **Complément DEV-008 (revue Tech Lead)** : option `JADE_LATENCY_LOG=1` lue de la configuration privée, exposition stderr seulement si activée, et correction des modalités micro/Discord vocal dans les mesures. Documentation TECHNICAL et exemple d'environnement mis à jour.

- **Revue sécurité complémentaire DEV-003** : le vocal Discord (fallback WAV et PCM) ne doit plus écrire son texte sur le fichier de sous-titres OBS partagé, qui pourrait appartenir à une autre audience ; test d'observation pendant lecture WAV et absence de son local.

- **Réparation de la régression QA DEV-003** : test historique `test_one_player_failure_cancels_and_awaits_other` devenu caduc après suppression du double lecteur. Le remplaçant vérifie une panne de diffusion Discord sans lecture locale et borne explicitement la durée (ancien test bloqué jusqu'au timeout CI, identifié dans les logs Windows du run 44477086397).

- **QA du lot au SHA c79976c (PR #26)** : [CI offline Ubuntu/Windows SUCCESS](https://github.com/goldaj/jade-vtuber/actions/runs/44478307734), [scan de secrets SUCCESS](https://github.com/goldaj/jade-vtuber/actions/runs/44478307610), revue des critères DEV-003/005–008 consignée dans la passation. Statut **À valider**, validation formelle Codex ou propriétaire non reçue ; tests physiques REC-005/007/010 à effectuer.

## 2026-11-20 — Avatar r20 dans la PWA

- Charge le module de compatibilité PixiJS sous la politique de scripts existante et raccorde les ordres de rendu de Cubism Core 6 à l'adaptateur 0.4.0.
- 37 tests ciblés réussis. À fenêtre mobile émulée, le modèle r20 s'affiche et bouge au repos dans Chromium. Le test Android passe par REC-019.
- [Preuves et déploiement](handoffs/2026-11-20-codex-avatar-mobile-r20.md).

## 2026-11-20 — Chambre mobile, personnalité et reconnexion Discord

- La chambre printanière approuvée remplace l'ancien décor CSS. Le WebP conserve l'illustration validée, avec trois mouvements localisés et une pause hors écran ou en mode mouvement réduit. [Passation chambre](handoffs/2026-11-20-codex-chambre-mobile.md).
- Le prompt réserve « papa » aux moments exceptionnels de tendresse et évite sa répétition. L'accueil mobile dit « Je suis là. ».
- Jade retente une connexion après une coupure propre au vocal, avec annulation à l'arrêt ou en cas de perte de la connexion Discord principale. [Passation Discord](handoffs/2026-11-20-codex-reconnexion-vocale.md).

## 2026-11-20 — Plan rapproché de Jade dans la PWA

- Cadrage approuvé par le propriétaire. Le modèle Web r20 est affiché à 150 % de son échelle précédente et décalé de 16 % de la hauteur de la scène vers le bas. La composition montre surtout le visage et le buste, avec les extrémités du modèle temporaire hors cadre.
- [Passation et validation](handoffs/2026-11-20-codex-chambre-mobile.md#cadrage-du-modèle-r20).

## 2026-11-20 — Mouvements et cadrage de la chambre

- La position de l'avatar est décalée de 8 % de la largeur de la scène vers la droite pour dégager la tasse sous le plan rapproché.
- Le rideau se balance davantage et son ourlet dispose de plus de marge. Les ombres peintes près du chevet et les reflets sur le parquet bougent plus sensiblement. Les effets suivent la préférence de mouvement réduit.
- [Passation](handoffs/2026-11-20-codex-chambre-mobile.md#ajustements-après-essai-mobile).

## 2026-11-20 — Fiabilité de l'export et de la validation locale

- L'export de prévisualisation inclut le script et le décor WebP de la PWA. Le binaire approuvé est vérifié avant la création de l'export.
- La simulation microphone emploie une durée PCM adaptée au filtre audio. [Passation](handoffs/2026-11-20-codex-audit-ops.md).

## 2026-11-20 — Dépenses OpenAI et voix mobile progressive (`codex/backlog-prioritaire-20261120`)

- La PWA privée présente les coûts API du jour et du mois UTC par devise, via `billing.py` et la route authentifiée `/api/billing`. La clé administrateur est facultative et reste côté PC ; les valeurs périmées sont identifiées et les périodes échues masquées. Le solde prépayé et l'alerte associée restent indisponibles ; voir [configuration](reference/OPENAI-COSTS.md).
- Le mobile reçoit le texte puis l'audio PCM au fil de la synthèse, avec repli WAV selon le modèle ou le navigateur, sans deuxième synthèse après erreur. La fermeture de la page interrompt le travail ; le pitch démarre en parallèle du premier fragment PCM. Les endpoints existants restent compatibles.
- Risques et limites : aucune mesure de latence réelle ni recette Android/Discord ou connexion à l'API d'administration ; capture mobile et transcription restent tamponnées, et le dialogue n'est pas duplex. Aucune mise en service sur `develop`.
- Contrôles et reprise : voir [passation du lot](handoffs/2026-11-20-codex-couts-voix-mobile.md).

## 2026-11-20 — Retours Discord et préparation des tests PyCharm

- Discord : fin de parole à 500 ms avec seuil d'énergie relatif borné et mémoire temporaire du bruit, à régler après recette réelle ; participation spontanée 20 % en groupe pour voix et texte Discord, Twitch conservé à 30 %. La parole reçue pendant une réponse n'interrompt plus Jade et n'est pas transcrite pour rechercher un ordre d'arrêt.
- Résilience : reconnexion vocale à délai progressif plafonné à 30 s tant que le Gateway est actif, au lieu d'abandonner après six essais. Deux arrêts ont été signalés ; faute de logs historiques, la cause du crash complet reste indéterminée et une nouvelle recette est nécessaire (REC-023).
- Tests sur ce poste : profil Discord/mobile PyCharm avec configuration privée chargée localement et instance unique ; la production reste lancée hors PyCharm. Voir [guide](reference/PYCHARM-LOCAL.md).
- Vérifications et limites dans [la passation](handoffs/2026-11-20-codex-retours-discord.md).

- Ajustement de personnalité demandé : `prompt_chat.txt` autorise un humour plus cru et des insultes non édulcorées lorsque le contexte s'y prête, sans vulgarité systématique ; le profil privé actif ne surcharge pas ce prompt. Une visionneuse de diagnostics permet aussi le lancement autonome demandé pour cette session.
- L'export de prévisualisation emporte le lanceur et ses configurations de test ; les tableaux documentaires conservent leurs informations sans être pris à tort pour des cartes du backlog.
