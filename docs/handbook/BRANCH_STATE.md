# Inventaire réel : branche develop

**Point de départ historique du manuel :** `aea51174cabae86274adfaa912990c2e6938b3de`. **Revue de réconciliation du 16 novembre 2026 :** `develop` au commit `b9beb904669dd57f070e5860e04f74b046854fec` (PR #20 fusionnée). Le présent inventaire décrit les fonctionnalités vérifiées dans le code et les tests CI, pas une recette sur le PC Jade. Voir [l'audit de câblage](../gpt6-jade/RECONCILIATION-CODE-CONFIG-DOCS-20261116.md).

## Fonctions intégrées

- `main.py --all-channels` lance ensemble **Discord écrit/vocal, Twitch texte, microphone Windows, API HTTP locale, mobile PWA privée, voix OpenAI et avatar r20 autonome**. VTube Studio est une sortie optionnelle si configurée.
- Launcher Windows déployé **hors du clone**, choix d'une branche Git, fast-forward avec refus des modifications locales, préflight, Poetry `-E all`, Git LFS, console Jade. **Aucun choix de mode** de fonctionnement.
- **`TurnArbiter` + `ArbitratingQueue`** : Jade arbitre les tours de plusieurs conversations en attente par LLM ; pas de priorité constante par support, repli FIFO, délai anti-famine, ordre conservé dans une conversation.
- Discord textes et vocal avec gestion améliorée du fil, politique d'intervention, protection des conversations privées ; Twitch IRC entrée/sortie.
- **PWA Android** privée par Tailscale Serve sur le PC, `127.0.0.1:8766`, authentification `Tailscale-User-Login` et token Bearer mobile distinct ; texte, capture vocale appuyer-pour-parler, TTS joué sur téléphone, rendu Live2D Web à condition d'installer le SDK compatible.
- **Mémoire SQLite optionnelle**, identité propriétaire Goldaj commune au micro PC et client mobile authentifié, souvenirs ordinaires et Core, automatisation facultative de la curation, commandes d'activation et effacement ; autobiographie avec limites documentées.
- **Moteur d'intention** `[INTENT:...]` masqué dans les sorties, voix Étincelle et pitch +2 demi-tons via DSP si dépendances FFmpeg compatibles ; tests simulés.
- **Démo Express Windows** purement locale/simulée, démo console `DemoChat`, démo animée OpenAI distincte dans `demo/reelle/`.

## Ce qui n'est PAS confirmé ou absent

- Aucun déploiement réel **garanti** sur le PC Jade ; services Discord/Twitch, micro, latence, voix TTS et PWA Android demandent des tests physiques.
- SDK Web Live2D propriétaire non inclus : le rendu r20 Android et sa compatibilité avec Cubism 5 **ne sont pas acquis**. Le préflight n'assure pas l'animation Web effective.
- Pas d'APK Android distribué, pas de conversation vocale duplex permanente/WebRTC, pas de push, pas de fallback sur le VPS Hyperliquid.
- Le moteur répond **séquentiellement** même si les entrées arrivent en parallèle : l'arbitrage choisit le prochain tour *en attente*, il n'interrompt pas une réponse déjà générée.
- La Démo Express ne réalise **aucune** inférence IA, aucune sortie vocale ni animation Live2D.

## Différence avec main et gestion des branches

`main` au moment du contrôle est encore sur son moteur modulaire **avec canaux opt-in et file FIFO**, sans launcher tout-en-un, PWA ni mémoire SQLite. Ne pas synchroniser par simple copier-coller ses guides. Les branches historiques intégrées sont recensées dans [BRANCH_MAINTENANCE.md](BRANCH_MAINTENANCE.md) ; leur suppression doit être effectuée par Codex après vérification de l'ascendance, faute d'outil de suppression dans le connecteur de cette intervention. Trois références divergentes nécessitent une revue. L'historique `main` → `develop` a été réconcilié le 16 novembre 2026 par le commit `dda14d1108bd91a53f75c3827af472c626479cca`, en conservant exactement l'arbre de `develop` ; **`main` n'a pas reçu les fonctions de `develop`**.

## Addendum du 15/11/2026 : réactions émotionnelles 2D

La branche dédiée `feat/live2d-intent-expression-sync-20261115` a été créée depuis `develop` pour ajouter le toggle `JADE_AVATAR_INTENT_ENABLED`, la table unique de deux expressions r20 et deux libellés textuels pour chacune des sept intentions, et le pilotage de l'avatar PC / PWA. **Ce sont des expressions, pas des animations corporelles propres**. La PR #18 a été **fusionnée dans `develop` le 15 novembre 2026** : ces expressions et le contrôle PC/PWA font désormais partie du code. `mobile_web/avatar.js` contient le retour à l'expression neutre, mais son comportement avec un véritable SDK Live2D Web **n'est pas validé**. Le SDK Android, les 14 véritables animations corporelles et le rig final r21 en pied restent non validés ou absents. Voir [passation Live2D](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).

## Évolution de develop : 2026-11-15, prompt approuvé et dialogue

**Implémenté dans le code :** `prompt_chat.txt` remplacé exactement par la version validée par Goldaj ; `Settings` + `OpenAIServices` utilisent Low et 320 tokens de complétion par défaut, y compris en streaming ; `MemoryStore` v3 conserve les tours complets des identités opt-in, sans résumé, et le runtime restaure jusqu'à 48 messages récents ; le micro a des IDs uniques par démarrage ; la participation texte Discord/Twitch et vocale Discord distingue le tête-à-tête (100 % des tours admissibles) du groupe (30 % de sélection spontanée, direct traité à part).

**À ne pas surévaluer :** valeurs des fichiers privés du PC inconnues ; le nombre des spectateurs silencieux Twitch n'est pas observable par le connecteur IRC ; les cooldowns, limites de taille, déconnexions et préemptions audio demeurent. Les tests ciblés Python ont été ajoutés mais **pas exécutés ni certifiés sur le PC Jade** via ce connecteur. Les 14 variantes futures (2 par intention) sont documentées, pas animées. Voir [la passation](../gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md).

## État DevOps observé le 15/11/2026

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Le commit `1669d954717d3ac2939f2e094432a48197d3d8c5` de `develop` a produit une CI Ubuntu rouge (520 tests, 17 échecs et 5 erreurs) et un scan Gitleaks vert. La PR #19 (`fix/develop-devops-audit-20261115`) a été **fusionnée le 15 novembre 2026** et fournit les protections de concurrence CI ainsi que la compatibilité des exports SQLite schéma v3. La PR #20 a été **fusionnée le 16 novembre 2026**, après une CI verte Ubuntu/Windows et un scan secrets réussi. La CI de la branche après fusion et la recette réelle PC/Android sont des contrôles distincts.

## Contrôle P0 CI du 16 novembre 2026 (develop)

- Politique de réponse conservée : **100 % en solo vérifié, 30 % en groupe** ; sollicitation explicite prioritaire. Les suivis contextuels en groupe restent échantillonnés et ne garantissent pas une réponse.
- Tests de transport Discord vocal : échantillonnage neutralisé **dans les doubles de test seulement** pour vérifier indépendamment déplacement de canal, interruption et récupération. La présence des participants est une information en lecture seule permettant de distinguer solo/groupe, jamais une autorisation d'écoute.
- Tests Discord écrit : salons à plusieurs participants simulés explicitement pour vérifier le taux et les limites de réponses, sans supprimer la réponse automatique en salon solo.
- Twitch : le test de non-empilement des réponses initialise le participant que l'adaptateur IRC observe normalement. Aucun changement de comportement de production dans ce lot.
- Vérification GitHub Actions Windows/Ubuntu, export de publication, scripts PowerShell et scan de secrets indispensable avant toute affirmation de CI verte. Aucun test vocal matériel ni appel OpenAI réalisé par cette revue.

- Correctif Windows du test IPC Live2D : la simulation valide toujours les deux trames d'expression et de bouche, puis termine par une coupure de pipe contrôlée. L'attente auparavant non bornée du faux moteur était responsable d'annulations Windows au délai de huit minutes ; aucun runtime ni test réel de Live2D n'est remplacé.
