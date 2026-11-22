# État de develop — fonctionnalités codées

**Référence :** sources de `goldaj/jade-vtuber`, état préparé pour `develop` sur la PR #34 (21 novembre 2026). **Code raccordé = fonctionnalité implémentée** ; la recette Android/Discord physique reste indépendante, et la configuration privée du PC peut remplacer les valeurs par défaut.

## Livrables PR #38 — code présent, recette en attente (22 novembre 2026)

- **REC-031 (ex DEV-021) :** tâches privées intercanaux et transferts Discord vers destinations explicitement autorisées, recette réelle manquante.
- **REC-032/033 (ex DEV-022/023) :** rappel local lexical et cache mémoire de présence ; recherche très ancienne, L1 et déclenchement d'ouverture PWA partiels.
- **REC-034 (ex DEV-024) :** jalons, durées, p50/p95, tokens, STT mobile, sans coût par tour exact ni preuve d'audition physique.
- **REC-035 (ex DEV-025) :** signaux d'apartés ; discussions multi-fils non pleinement reconnues.
- **REC-036 (ex DEV-026) :** personnalité mémorielle corrigible ; évolution expérientielle plus profonde différée P3.
- **REC-037 (ex DEV-020) :** superviseur local Windows et administration mobile ; pas de recette physique.
- **DEV-010** : décor mobile animé en calques et validé par le propriétaire, **Done** ; **OPS-015** : inventaire artistique **Bloqué** dans l'attente de tokens Codex.

**REC-031/032/033/034 sont Done après validation du propriétaire ; REC-035/036/037 restent À valider.** Les réserves historiques sont détaillées dans l'[audit](../operations/handoffs/2026-11-22-audit-technique-fonctionnel-ci-pr38.md) et dans la vue REC.

## Quick wins VIS-04 / RTE-12, développés le 22 novembre 2026

- **DEV-027, Live2D mobile :** la PWA coupe le ticker de rendu PixiJS et l'auto-actualisation du modèle quand l'onglet est caché, le composant démonté ou l'avatar hors champ. Le dialogue, la voix et les connecteurs restent actifs. L'absence d'IntersectionObserver est gérée ; reprise sans nouveau modèle ni relance de l'Idle. La batterie/FPS Android ne sont pas encore mesurés réellement.
- **DEV-028, livraison :** les destinations initialement planifiées sont distinctes des événements `delivery_evidence` : confirmation d'acceptation par l'API Discord texte, fin de lecture ffplay ou consommation audio Discord. Les redirections mobiles/HTTP et Twitch sans accusé réel ne sont jamais présentées comme livrées ; aucun statut n'affirme que l'utilisateur a entendu le son. Pas de contenu privé dans ces nouvelles preuves.
- Les tests et conditions de recette sont dans [la passation](../operations/handoffs/2026-11-22-chatgpt-vis04-rte12.md) et la [backlog DEV](../backlog/01-DEVELOPPEMENT.md). **Statut de recette réel à vérifier avant Done.**

## Recherche web facultative (REC-038, 22 novembre 2026)

- `JADE_WEB_ENABLED=0` par défaut : aucune recherche web à l'installation ni en veille. Une fois activé, le modèle de dialogue peut appeler librement `jade_web_search` uniquement pendant un tour auquel Jade répond ; ses réponses sans recherche ne déclenchent pas d'appel supplémentaire.
- Fournisseur actif : Tavily via l'adaptateur `src/jade_runtime/web_providers/tavily.py`, remplaçable à travers le contrat `SearchProvider`. Le moteur de dialogue, Discord, PWA et les fichiers de logs ne dépendent pas de Tavily directement.
- Le journal utilise un **dossier privé par défaut `D:/Jade/private/jade-web-search/`**, voisin de `JADE_MEMORY_DB_PATH` (réglage `JADE_WEB_LOG_DIR`) : chaque démarrage live avec recherche web activée crée un nouveau JSONL horodaté avec PID, sans supprimer les sessions précédentes. L'ancienne variable `JADE_WEB_LOG_PATH` reste acceptée comme chemin historique converti vers un dossier voisin ; l'ancien fichier unique reste intact. Toute tentative acceptée est journalisée avant l'appel réseau avec date UTC, requête, raison explicite et provenance ; résultats, statut, coût en crédits disponible et durée sont ensuite ajoutés. Une interruption brutale peut laisser une ligne `started` sans statut final. Un échec d'écriture du journal empêche l'appel réseau.
- Budget : maximum 10 recherches par tour par défaut (réglable de 1 à 10 via `JADE_WEB_MAX_PER_TURN`), recherche `basic` et jusqu'à 5 sources ; coût IA de la continuation de l'outil distinct des crédits Tavily. Pas de compte ni de clé Tavily dans le dépôt. **REC-038 `Done` sur validation explicite du propriétaire le 22/11/2026**, pour la recherche Internet fonctionnelle observée sur son PC ; la CI dédiée web est réussie, les scénarios complémentaires non démontrés restent des réserves documentées dans la vue REC.
- **Politique de réponse web :** Jade synthétise les résultats sans exposer par défaut les URL ou les listes de sources ; lien unique/minimal sur demande explicite ou nécessité directe, et pas d'URL prononcée à l'oral sans demande. Les URL restent présentes dans le journal persistant.

## Fonctions présentes

| Domaine | État observé dans le code |
| --- | --- |
| Lancement | `main.py --all-channels`, launcher Windows, préflight, tous les connecteurs en une instance, sans choix de plateforme |
| Orchestration | `ArbitratingQueue`, `TurnArbiter`, file bornée, équité, **un tour principal à la fois** |
| Discord | Texte, MP, vocal PCM/STT/TTS, sessions, anti-écho et reconnexion ; classifieur social hybride facultatif (budget séparé) et initiatives de bienvenue **activées par défaut** sur entrée dans le vocal, à l'oral si la session et le membre restent présents, sinon en texte ; **aucune relance autonome sans réaction humaine adressée à Jade ou bref acquiescement immédiat** |
| Twitch | IRC entrée/sortie, reconnexion/PING, un seul tour à la fois, solo actif 100 %, groupe 30 % et interpellations directes |
| Dialogue | `prompt_chat.txt`, backend OpenAI configurable ; reprise SQLite intégrale des **24 dernières heures sans plafond de nombre de tours**, mais composition **sélective du prompt** par pertinence locale et budget caractères (réversible par `JADE_SELECTIVE_CONTEXT_ENABLED=0`) |
| Mémoire volontaire DEV-012 | L'outil facultatif natif `jade_save_memory` est disponible au LLM conversationnel sur profil mémoire actif, y compris en streaming vocal. Jade choisit de ne rien écrire ou de proposer L2 (ordinary, 365 j) / L3 (Core, sans purge automatique) ; SQLite vérifie identité, consentement, preuve et périmètre, et renvoie un statut avant la réponse finale. Aucune requête LLM supplémentaire si aucun appel ; une continuation en cas d'action. Les résultats de la curation asynchrone préexistante restent indépendants et ne sont pas réinjectés au LLM. Recette sur matériel réel et approbation DEV-012 encore ouvertes. |
| Demandes explicites de souvenirs | Texte ou voix : toute identité vérifiée avec mémoire active peut demander une mémorisation, enregistrée exclusivement en `kind=ordinary` (durée limitée et portée personnelle/salon) ; même une demande de Core est réduite à l’ordinaire. Jade choisit elle-même ses `core_self` et `core_relationship` via sa curation autonome, aucune commande humaine d’ajout Core. |
| Mémoire | Rappel des souvenirs individualisés désactivé pour les réponses publiques Discord/Twitch/vocal, conservé dans les échanges privés autorisés ; propositions autobiographiques `core_self` de tiers refusées. SQLite v5 privée : L1 brut 7 jours, reprise intégrale 24 h mais injection sélective au modèle ; L2 ordinaire 365 jours ; Core sans purge. **Curation groupée par pertinence** (3 candidats / lot maximum, délai initial 18 s), épinglage de personne au moment de mise en file et contrôle de cohérence d'identité lors des écritures différées. Repères de personnalité issus des mêmes souvenirs autorisés, sans LLM supplémentaire ; autonomie Core conservée |
| Identités | Profil Goldaj partagé par micro PC et PWA mobile authentifiée ; mémoire automatique Discord pour compte identifié (serveur, vocal et MP), sans commande d'oubli global ni blocage de réinscription ; Twitch manuel ; liaison Goldaj vers Discord/Twitch par code à usage unique expirant en 5 min, association durable ; **rappel privé transversal des souvenirs sélectionnés entre comptes liés**, sans reprise d'historique brut ni injection inter-canaux dans les salons publics ; déliaison et portées préservées ; suppression individuelle des souvenirs autorisés |
| Discord MP | Cache borné des véritables canaux privés entrants en cas de cache Discord absent ; succès de livraison nécessaire avant mémorisation durable d'une réponse. Tests physiques DEV-019/REC-002 en attente. |\n| Discord voix/texte | Même historique volatil pour un compte dans le vocal et **son chat textuel natif**, sous la même session ; autres salons distincts |
| Mobile | PWA privée/Tailscale Serve : texte, **WebSocket PCM16 montant progressif avec STT à la fin de l'énoncé, TTS sortant progressif, annulation et fin de phrase locale**, WAV HTTP historique en secours avant connexion duplex ; Live2D Web, décor animé et coûts organisationnels (solde prépayé indisponible) |
| Audio | STT/TTS OpenAI, PCM progressif sous conditions, voix Étincelle `shimmer` 1,25×, pitch optionnel via FFmpeg Rubber Band ; pool Realtime partagé WAV/PCM |
| Émotions | Sept intentions ; **deux expressions faciales r20 + deux libellés PWA par intention**, synchronisation expression/bouche, toggle global |
| Préfiltrage économique | Salutations routinières et doublons écartés avant la curation groupée ; coût exact par composant encore à instrumenter. |\n| Observabilité | Jalons `jade.latency` configurables, et **réservations de dépenses USD estimatives** pour initiatives et classifications sociales en SQLite ; métriques d'usage fournisseur réellement facturé et recette physique restent à recueillir |
| Démonstrations | Démo Express simulée uniquement comme démonstration distribuée ; console hors ligne comme mode du vrai runtime. Renderer r20 intégré au code applicatif |

## Limitations fonctionnelles actuelles

1. **Routage :** Discord/Twitch/HTTP écrits ne déclenchent plus de TTS ni de hotkey VTS dans le callback. Le fallback vocal Discord n'utilise plus ffplay local et masque ses sous-titres OBS partagés. MP et sources privées restent exclus des sous-titres OBS. Le routeur central multi-audience et le filtrage du rendu 2D restent à développer ; recette mixage OBS nécessaire.
2. **Streaming :** Discord vocal utilise le PCM progressif (session autorisée) même si ffplay est disponible pour le micro PC ; le mode phrases reste opt-in, mais le fallback WAV Discord vocal ne joue plus en local. Le hotkey VTS ne retarde plus le début de voix standard.
3. **Concurrence :** l'orchestrateur attend la fin du tour et de sa diffusion pour avancer, même si la curation et les connecteurs peuvent travailler à côté.
4. **Mémoire :** rappels par identité/salon et autres portées liées **uniquement en privé** ; sélection lexicale locale et curation groupée intégrées, mais pas encore de préchargement de présence L1/L2, index FTS approfondi ni de recherche sémantique profonde. La fenêtre SQLite 24 h reste intacte.
5. **Mobile :** WebSocket duplex réseau intégré (PCM entrant par fragments, STT après fin de l'énoncé et sortie TTS progressive) ; ce n'est **pas** une conversation OpenAI Realtime audio continu, ni un APK natif. Tailscale Serve/Chrome Android et vraie latence restent à recetter.
6. **Graphique :** l'avatar autonome r20 démarre avec `--all-channels` et ne dépend pas encore de sa visibilité. Les **14 animations corporelles originales** et le rig final r21 ne font pas partie du catalogue de visages existant.
7. **Modèle IA :** Luna demeure la valeur de configuration par défaut ; un moteur Realtime conversationnel léger sans Luna est prévu ultérieurement, pas intégré.
8. **Installation :** les ports, SDK, comptes et ressources effectifs sont fournis par le PC et sa configuration privée ; le code n'est pas un inventaire des secrets du poste.

## Références sans duplication

[Manuel](README.md) · [architecture](TECHNICAL.md) · [atlas des parcours](../architecture/atlas-fonctionnel-2026-11-16/README.md) · [passation dialogue](../history/gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md) · [backlog prospectif](../ameliorations/README.md).

Les PR, audits et CI antérieurs sont conservés dans [`docs/history/gpt6-jade/`](../history/gpt6-jade/) et [`docs/history/conversations/`](../history/conversations/). Ils conservent leur date historique, sans se substituer à ce document ou au code actuel. Les passations actives des agents figurent dans [`docs/operations/handoffs/`](../operations/handoffs/).
