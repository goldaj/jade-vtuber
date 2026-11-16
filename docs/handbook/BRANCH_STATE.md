# État de develop — fonctionnalités codées

**Référence :** sources de `goldaj/jade-vtuber`, branche `develop`, examinées le 16 novembre 2026. **Code raccordé = fonctionnalité implémentée**, sans catégorie supplémentaire « testé/non testé ». Le PC peut charger une configuration privée différente des défauts.

## Fonctions présentes

| Domaine | État observé dans le code |
| --- | --- |
| Lancement | `main.py --all-channels`, launcher Windows, préflight, tous les connecteurs en une instance, sans choix de plateforme |
| Orchestration | `ArbitratingQueue`, `TurnArbiter`, file bornée, équité, **un tour principal à la fois** |
| Discord | Texte, messages privés, vocal PCM/STT/TTS, sessions, stop/reprise, anti-écho, sélection par participants observés |
| Twitch | IRC entrée/sortie, reconnexion/PING, un seul tour à la fois, solo actif 100 %, groupe 30 % et interpellations directes |
| Dialogue | `prompt_chat.txt`, backend OpenAI configurable, défaut `gpt-6-luna` / `low` / 320 tokens, historique volatil 48 messages |
| Mémoire | SQLite v3 optionnelle, consentement opt-in, souvenirs ordinaires/Core, autobiographie privée, curation asynchrone, échanges complets et récupération des 24 derniers tours |
| Identités | Profil Goldaj partagé par micro PC et PWA mobile authentifiée ; liaison Goldaj vers comptes Discord/Twitch consentants par code vérifié à usage unique ; scopes de confidentialité |
| Discord voix/texte | Même historique volatil pour un compte dans le vocal et **son chat textuel natif**, sous la même session ; autres salons distincts |
| Mobile | PWA privée/Tailscale Serve, texte, capture WAV, TTS à la demande, modèle Live2D Web via assets/SDK installés |
| Audio | STT/TTS OpenAI, PCM progressif sous conditions, voix Étincelle `shimmer` 1,25×, pitch optionnel via FFmpeg Rubber Band |
| Émotions | Sept intentions ; **deux expressions faciales r20 + deux libellés PWA par intention**, synchronisation expression/bouche, toggle global |
| Démonstrations | Démo Express simulée uniquement comme démonstration distribuée ; console hors ligne comme mode du vrai runtime. Renderer r20 intégré au code applicatif |

## Limitations fonctionnelles actuelles

1. **Routage :** une réponse à Discord/Twitch écrit est envoyée en texte, mais peut déclencher une voix supplémentaire sur le PC/Discord vocal. Les MP Discord ne sont pas diffusés publiquement. Le routeur exclusivement par canal d'origine n'est pas codé.
2. **Streaming :** Discord vocal utilise le PCM progressif (TTS Realtime et session autorisée) même avec `ffplay` activé dans `--all-channels` pour le micro PC ; le mode phrases reste opt-in et le fallback WAV peut encore employer la sortie locale.
3. **Concurrence :** l'orchestrateur attend la fin du tour et de sa diffusion pour avancer, même si la curation et les connecteurs peuvent travailler à côté.
4. **Mémoire :** rappel par identité et portée, chronologique et limité ; pas de cache de présence Goldaj/Discord L1-L2, de préchargement anticipé ou de recherche sémantique profonde.
5. **Mobile :** capture WAV et réponse audio complète ; pas de duplex/streaming temps réel ou APK natif.
6. **Graphique :** l'avatar autonome r20 démarre avec `--all-channels` et ne dépend pas encore de sa visibilité. Les **14 animations corporelles originales** et le rig final r21 ne font pas partie du catalogue de visages existant.
7. **Modèle IA :** Luna demeure la valeur de configuration par défaut ; un moteur Realtime conversationnel léger sans Luna est prévu ultérieurement, pas intégré.
8. **Installation :** les ports, SDK, comptes et ressources effectifs sont fournis par le PC et sa configuration privée ; le code n'est pas un inventaire des secrets du poste.

## Références sans duplication

[Manuel](README.md) · [architecture](TECHNICAL.md) · [atlas des parcours](../architecture/atlas-fonctionnel-2026-11-16/README.md) · [passation dialogue](../history/gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md) · [backlog prospectif](../ameliorations/README.md).

Les PR, audits et CI antérieurs sont conservés dans [`docs/history/gpt6-jade/`](../history/gpt6-jade/) et [`docs/history/conversations/`](../history/conversations/). Ils conservent leur date historique, sans se substituer à ce document ou au code actuel. Les passations actives des agents figurent dans [`docs/operations/handoffs/`](../operations/handoffs/).
