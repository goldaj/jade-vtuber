# État de develop — fonctionnalités codées

**Référence :** sources de `goldaj/jade-vtuber`, branche `develop`, examinées le 19 novembre 2026 (quick wins en cours d'intégration). **Code raccordé = fonctionnalité implémentée**, sans catégorie supplémentaire « testé/non testé ». Le PC peut charger une configuration privée différente des défauts.

## Fonctions présentes

| Domaine | État observé dans le code |
| --- | --- |
| Lancement | `main.py --all-channels`, launcher Windows, préflight, tous les connecteurs en une instance, sans choix de plateforme |
| Orchestration | `ArbitratingQueue`, `TurnArbiter`, file bornée, équité, **un tour principal à la fois** |
| Discord | Texte, messages privés, vocal PCM/STT/TTS, sessions, stop/reprise, anti-écho, sélection par participants observés et reconnexion lors de la perte du vocal seul |
| Twitch | IRC entrée/sortie, reconnexion/PING, un seul tour à la fois, solo actif 100 %, groupe 30 % et interpellations directes |
| Dialogue | `prompt_chat.txt`, backend OpenAI configurable, défaut `gpt-6-luna` / `low` / 320 tokens, historique volatil 48 messages |
| Demandes explicites de souvenirs | Texte ou voix : toute identité vérifiée avec mémoire active peut demander une mémorisation, enregistrée exclusivement en `kind=ordinary` (durée limitée et portée personnelle/salon) ; même une demande de Core est réduite à l’ordinaire. Jade choisit elle-même ses `core_self` et `core_relationship` via sa curation autonome, aucune commande humaine d’ajout Core. |
| Mémoire | SQLite v3 persistante et curation activées par défaut en mode réel, fichier privé hors Git, inscription automatique par interaction identifiée sur serveur Discord (effacement + refus persistant), activation manuelle MP/Twitch ; souvenirs ordinaires/Core, autobiographie privée, curation asynchrone, échanges complets et récupération des 24 derniers tours |
| Identités | Profil Goldaj partagé par micro PC et PWA mobile authentifiée ; liaison Goldaj vers comptes Discord/Twitch par code vérifié à usage unique ; déliaison et effacement propres à l'identité vérifiée ; scopes de confidentialité |
| Discord voix/texte | Même historique volatil pour un compte dans le vocal et **son chat textuel natif**, sous la même session ; autres salons distincts |
| Mobile | PWA privée/Tailscale Serve, texte, capture WAV, TTS progressif selon modèle/navigateur, coûts API de l’organisation (solde prépayé indisponible), modèle Live2D Web et chambre animée |
| Audio | STT/TTS OpenAI, PCM progressif sous conditions, voix Étincelle `shimmer` 1,25×, pitch optionnel via FFmpeg Rubber Band ; pool Realtime partagé WAV/PCM |
| Émotions | Sept intentions ; **deux expressions faciales r20 + deux libellés PWA par intention**, synchronisation expression/bouche, toggle global |
| Observabilité | Jalons `jade.latency` sans contenu ni identité sur tous les canaux, activables par `JADE_LATENCY_LOG=1` (défaut 0) ; mesures physiques STT/premier son/coût restantes |
| Démonstrations | Démo Express simulée uniquement comme démonstration distribuée ; console hors ligne comme mode du vrai runtime. Renderer r20 intégré au code applicatif |

## Limitations fonctionnelles actuelles

1. **Routage :** Discord/Twitch/HTTP écrits ne déclenchent plus de TTS ni de hotkey VTS dans le callback. Le fallback vocal Discord n'utilise plus ffplay local et masque ses sous-titres OBS partagés. MP et sources privées restent exclus des sous-titres OBS. Le routeur central multi-audience et le filtrage du rendu 2D restent à développer ; recette mixage OBS nécessaire.
2. **Streaming :** Discord vocal utilise le PCM progressif (session autorisée) même si ffplay est disponible pour le micro PC ; le mode phrases reste opt-in, mais le fallback WAV Discord vocal ne joue plus en local. Le hotkey VTS ne retarde plus le début de voix standard.
3. **Concurrence :** l'orchestrateur attend la fin du tour et de sa diffusion pour avancer, même si la curation et les connecteurs peuvent travailler à côté.
4. **Mémoire :** rappel par identité et portée, chronologique et limité ; pas de cache de présence Goldaj/Discord L1-L2, de préchargement anticipé ou de recherche sémantique profonde.
5. **Mobile :** capture WAV et génération IA complètes avant réponse ; audio sortant progressif sous conditions, pas de duplex temps réel ni APK natif.
6. **Graphique :** l'avatar autonome r20 démarre avec `--all-channels` et ne dépend pas encore de sa visibilité. Les **14 animations corporelles originales** et le rig final r21 ne font pas partie du catalogue de visages existant.
7. **Modèle IA :** Luna demeure la valeur de configuration par défaut ; un moteur Realtime conversationnel léger sans Luna est prévu ultérieurement, pas intégré.
8. **Installation :** les ports, SDK, comptes et ressources effectifs sont fournis par le PC et sa configuration privée ; le code n'est pas un inventaire des secrets du poste.

## Références sans duplication

[Manuel](README.md) · [architecture](TECHNICAL.md) · [atlas des parcours](../architecture/atlas-fonctionnel-2026-11-16/README.md) · [passation dialogue](../history/gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md) · [backlog prospectif](../ameliorations/README.md).

Les PR, audits et CI antérieurs sont conservés dans [`docs/history/gpt6-jade/`](../history/gpt6-jade/) et [`docs/history/conversations/`](../history/conversations/). Ils conservent leur date historique, sans se substituer à ce document ou au code actuel. Les passations actives des agents figurent dans [`docs/operations/handoffs/`](../operations/handoffs/).
