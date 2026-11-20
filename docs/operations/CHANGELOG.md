# Journal technique unique — develop

Ce document est **la seule pièce documentaire systématiquement exigée en CI** pour les changements techniques. Les guides, atlas et passations sont révisés uniquement quand le comportement ou les procédures qu'ils décrivent changent. Une entrée indique les faits vérifiés ; un ancien journal ne remplace pas le code.

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
