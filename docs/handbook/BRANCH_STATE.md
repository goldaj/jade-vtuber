# État de develop — fonctionnalités codées

**Référence :** sources de `goldaj/jade-vtuber`, état préparé pour `develop` sur la PR #34 (21 novembre 2026). **Code raccordé = fonctionnalité implémentée** ; la recette Android/Discord physique reste indépendante, et la configuration privée du PC peut remplacer les valeurs par défaut.

## Fonctions présentes

| Domaine | État observé dans le code |
| --- | --- |
| Lancement | `main.py --all-channels`, launcher Windows, préflight, tous les connecteurs en une instance, sans choix de plateforme |
| Orchestration | `ArbitratingQueue`, `TurnArbiter`, file bornée, équité, **un tour principal à la fois** |
| Discord | Texte, MP, vocal PCM/STT/TTS, sessions, anti-écho et reconnexion ; classifieur social hybride facultatif (budget séparé) et initiatives de bienvenue **activées par défaut** sur entrée dans le vocal, en texte dans le chat natif ; **aucune relance autonome sans réaction humaine** |
| Twitch | IRC entrée/sortie, reconnexion/PING, un seul tour à la fois, solo actif 100 %, groupe 30 % et interpellations directes |
| Dialogue | `prompt_chat.txt`, backend OpenAI configurable ; reprise SQLite intégrale des **24 dernières heures sans plafond de nombre de tours**, mais composition **sélective du prompt** par pertinence locale et budget caractères (réversible par `JADE_SELECTIVE_CONTEXT_ENABLED=0`) |
| Demandes explicites de souvenirs | Texte ou voix : toute identité vérifiée avec mémoire active peut demander une mémorisation, enregistrée exclusivement en `kind=ordinary` (durée limitée et portée personnelle/salon) ; même une demande de Core est réduite à l’ordinaire. Jade choisit elle-même ses `core_self` et `core_relationship` via sa curation autonome, aucune commande humaine d’ajout Core. |
| Mémoire | SQLite v4 privée : L1 brut 7 jours, reprise intégrale 24 h mais injection sélective au modèle ; L2 ordinaire 365 jours ; Core sans purge. **Curation groupée par pertinence** (3 candidats / lot maximum, délai initial 18 s), épinglage de personne au moment de mise en file et contrôle anti-résurrection après oubli. Repères de personnalité issus des mêmes souvenirs autorisés, sans LLM supplémentaire ; autonomie Core conservée |
| Identités | Profil Goldaj partagé par micro PC et PWA mobile authentifiée ; mémoire automatique Discord pour compte identifié (serveur, vocal et MP), opt-out persistant ; Twitch manuel ; liaison Goldaj vers Discord/Twitch par code à usage unique expirant en 5 min, association durable ; **rappel privé transversal des souvenirs sélectionnés entre comptes liés**, sans reprise d'historique brut ni injection inter-canaux dans les salons publics ; déliaison, effacement et portées préservés |
| Discord voix/texte | Même historique volatil pour un compte dans le vocal et **son chat textuel natif**, sous la même session ; autres salons distincts |
| Mobile | PWA privée/Tailscale Serve : texte, **WebSocket PCM16 montant progressif avec STT à la fin de l'énoncé, TTS sortant progressif, annulation et fin de phrase locale**, WAV HTTP historique en secours avant connexion duplex ; Live2D Web, décor animé et coûts organisationnels (solde prépayé indisponible) |
| Audio | STT/TTS OpenAI, PCM progressif sous conditions, voix Étincelle `shimmer` 1,25×, pitch optionnel via FFmpeg Rubber Band ; pool Realtime partagé WAV/PCM |
| Émotions | Sept intentions ; **deux expressions faciales r20 + deux libellés PWA par intention**, synchronisation expression/bouche, toggle global |
| Observabilité | Jalons `jade.latency` configurables, et **réservations de dépenses USD estimatives** pour initiatives et classifications sociales en SQLite ; métriques d'usage fournisseur réellement facturé et recette physique restent à recueillir |
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
