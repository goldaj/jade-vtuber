# Instructions du projet Jade — develop

## Point d'entrée et gouvernance documentaire

**Toute IA (Codex, Terra, Astra, ChatGPT) commence par ce fichier**, puis lit [le centre opérationnel](docs/operations/README.md) et [les règles de collaboration](docs/operations/AGENT_COORDINATION.md). Le [journal des modifications](docs/operations/CHANGELOG.md) consigne chaque changement technique. Les échanges entre agents sont écrits dans `docs/operations/handoffs/`, avec une fiche **par mission**, puis référencés dans la PR ; jamais dans un rapport historique pris pour un ordre courant.

## Sources de vérité et décisions du propriétaire

**Le code de la branche consultée définit les fonctionnalités existantes.** Si un module est intégré et raccordé au runtime, le considérer comme implémenté. Les tests/recettes relèvent de l'assurance qualité et ne créent pas un deuxième statut fonctionnel. Les variables privées peuvent modifier le comportement du poste.

- **[État du code de develop](docs/handbook/BRANCH_STATE.md)** : liste canonique des fonctions et limitations.
- **[Manuel et guide technique](docs/handbook/README.md)** ; [atlas des décisions et appels](docs/architecture/atlas-fonctionnel-2026-11-16/README.md) et [contrat de flux](docs/architecture/atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md) (instantanés datés à confronter au code).
- **[Backlog opérationnel priorisé](docs/backlog/README.md)** : **source de vérité pour les travaux et recettes en attente**, quatre vues (DEV/REC/OPS/ART), jalons A/B, dépendances et statuts de travail.
- **[Catalogue des améliorations futures](docs/ameliorations/README.md)** : idées prospectives distinctes, non engagées automatiquement comme tâches du backlog opérationnel.
- [Archives et index des conversations](docs/history/conversations/INDEX.md) : contexte historique, pas des ordres d'exécution actuels.

**Décision maintenue :** Goldaj veut d'abord tester Jade avant de développer les pistes du catalogue d'améliorations ; le backlog **opérationnel** créé le 18 novembre organise au contraire installation, recette, modèle r21 et maintenance déjà attendues. Ne pas engager de développement à partir du catalogue prospectif sans nouvelle demande ; la création du backlog opérationnel n'autorise pas à elle seule l'exécution de ses tâches ni des appels facturés. Le routage exclusivement par canal source, le préchargement mémoire, la visibilité conditionnelle de l'avatar et le moteur Realtime sans Luna sont des objectifs **non intégrés**. Luna reste le modèle configuré par défaut dans le code actuel.

## Branches, poste et confidentialité

- Travailler sur `develop` pour les changements autorisés ; pas de merge sur `main` sans autorisation explicite et renouvelée. Ne pas effacer ou écraser les travaux locaux de Terra/Codex. Ne pas copier les documents de develop tels quels sur main.
- Sur le PC du propriétaire, conserver dépôt, outils, modèles, caches et temporaires sur **D:**, en préservant fichiers uniques et checkpoints. Le launcher est installé séparément du dépôt et se réinstalle quand ses scripts changent.
- Ne jamais publier secrets, configuration privée, mémoire SQLite, transcriptions ou captations audio. La configuration privée est sélectionnable avec `JADE_SECRETS_FILE`. Ne pas activer de connecteurs, microphones ou appels facturés sans autorisation.
- Mobile privé uniquement par Tailscale Serve et identité propriétaire + Bearer ; **pas de Funnel public**, pas d'exposition LAN, pas d'utilisation/modification du VPS Hyperliquid.
- Préserver l'identité des comptes, leur opt-in, l'isolement des sessions et la suppression de mémoire. Les entrées privées PC/mobile/HTTP et les MP ne doivent pas sortir en Discord/Twitch/OBS public.

## Runtime codé sur develop

- `main.py --all-channels` lance ensemble les connecteurs configurés, sans sélecteur de mode. `TurnArbiter` arbitre les conversations en attente et le worker principal reste séquentiel.
- Discord écrit/vocal et Twitch IRC sont intégrés. Solo humain observé : réponse aux tours admissibles ; groupe : intervention spontanée échantillonnée à 30 %, interpellations directes prioritaires. Twitch refuse d'empiler un second message pendant un tour en cours.
- Mémoire SQLite v3, opt-in et curation facultative ; profil privé Goldaj partagé par micro PC et mobile authentifié ; historique complet en base avec fenêtre récente bornée ; conversation Discord voix/chat natif du même vocal unifiée par compte et session.
- Réponses vocales OpenAI ; voix `shimmer` 1,25×, pitch +2 via FFmpeg Rubber Band quand disponible. Intention `[INTENT:...]` filtrée. **Deux réactions faciales r20 et deux textes PWA par chacune des sept intentions** codés ; **14 motions corporelles originales** et rig r21 final à créer.
- PWA Android privée : texte, prise de parole WAV, TTS mobile, avatar Web sous SDK compatible. Le duplex temps réel n'est pas codé.
- Streaming PCM Discord disponible sous conditions : `--all-channels` conserve `ffplay` pour le microphone PC, mais le PCM de Discord vocal l'utilise désormais indépendamment. Le mode par phrases reste opt-in, le fallback WAV et l'ancien broadcast restent à réexaminer. Les réponses écrites peuvent encore déclencher du TTS sur d'autres sorties : le routage exclusif reste à développer.

## Maintenance et passation

Avant modification, consulter les sources du domaine, [AI_HANDOFF](docs/handbook/AI_HANDOFF.md) et la [passation active de la mission](docs/operations/handoffs/README.md). **Les passations historiques suivantes sont des références complémentaires à lire seulement si le sujet le justifie, pas des instructions en vigueur :** [voix](docs/history/gpt6-jade/HANDOFF-CODEX-VOICE-INTENTS-20261113.md), [mémoire](docs/history/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md), [Discord](docs/history/gpt6-jade/HANDOFF-DISCORD-UNIFIED-20261115.md), [PC/Android](docs/history/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md), [Live2D](docs/history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md), [DevOps](docs/history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md).

Pour toute modification **technique** (code, configuration, dépendances, scripts, assets, workflow), mettre à jour **un seul document imposé par la CI** : [`docs/operations/CHANGELOG.md`](docs/operations/CHANGELOG.md), avec la justification, les fichiers concernés, les risques et les vérifications. Examiner ensuite les guides et schémas du domaine : **modifier seulement ceux réellement impactés**. `BRANCH_STATE.md` reste la source de vérité fonctionnelle lorsque le comportement change ; `AGENTS.md` seulement lorsque les règles changent. Les tests seuls et les archives documentaires ne forcent pas une réécriture des guides. Voir [`scripts/check_docs.py`](scripts/check_docs.py) et [règles de collaboration](docs/operations/AGENT_COORDINATION.md).

Préserver les assets Git LFS et leurs droits (`python jade-modeling/verify_assets.py`). La compilation et les tests (`python -m unittest discover -s tests -v`, `python -m compileall -q src main.py`) servent aux contrôles de changement ; leur exécution ne modifie pas à elle seule le statut d'une fonction déjà présente dans le code.
