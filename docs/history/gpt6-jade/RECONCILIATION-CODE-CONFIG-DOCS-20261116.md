# Mission 2 — Réconciliation code, configurations et documentation sur develop

**Instantané de réconciliation daté du 16 novembre :** les faits décrits sont ceux du SHA indiqué, pas un statut à recopier indéfiniment. L'état fonctionnel actuel est le [code de develop et son inventaire](../../handbook/BRANCH_STATE.md) ; le [catalogue](../../ameliorations/README.md) centralise les idées non réalisées.

Date de revue : 16 novembre 2026. Dépôt `goldaj/jade-vtuber`.
Base du contrôle : `develop` au SHA `b9beb904669dd57f070e5860e04f74b046854fec`.
Ce document est un **inventaire de câblage vérifié dans Git**, non un certificat de fonctionnement sur le PC Jade.

## Personas et périmètre du contrôle

- **Product Owner** : vérifier la cohérence de la promesse produit (un seul Jade, 100 % en solo vérifié, 30 % de réponse spontanée en groupe, intentions et mémoire opt-in).
- **Architecte logiciel** : tracer les connecteurs depuis les arguments CLI, les configurations et les flux de sortie.
- **Développeur senior Python asynchrone** : distinguer imports, instanciation, démarrage et conditions d'échec, y compris les connecteurs qui tombent pendant l'exploitation.
- **QA / intégration** : relier chaque branche de code aux tests existants et à la CI, séparer l'émulation des interactions réelles.
- **DevOps / sécurité** : vérifier les conditions locales de lancement, secrets, frontières réseau et état réel des merges.

## Matrice de câblage vérifiée

| Capacité | Raccordement dans develop | Preuve dans le dépôt | Limite réelle |
| --- | --- | --- | --- |
| Démarrage `--all-channels` | `main.py` active `live, voice, mic, twitch, discord, discord_voice, http, avatar, mobile`, VTube Studio si configuré | `main.py`, `tests/test_jade_all_channels.py` | Requiert secrets, services et périphériques ; un connecteur fatal peut provoquer l'arrêt du groupe |
| Orchestration unifiée | Une seule instance `Runtime`, `ArbitratingQueue` et `TurnArbiter` ; tours traités séquentiellement | `src/jade_runtime/orchestrator.py`, `turn_arbitration.py`, `tests/test_jade_all_channels.py` | Pas de génération simultanée de plusieurs réponses |
| Discord écrit | `DiscordText` branché à `runtime.submit`, émission par `send_chat` et contexte des salons | `main.py`, `discord_text.py`, `discord_text_policy.py` | Solo 100 % si un seul auteur humain vérifié récemment ; groupe échantillonné et conditions de cooldown |
| Discord vocal | `OpenVoiceBridge` branché au runtime et à `SpeechOutput.secondary_player` | `main.py`, `discord_voice.py`, `voice_decision.py` | STT/TTS réels, reconnexion, permissions et latence à recetter |
| Twitch écrit | `TwitchIRC` reçoit les messages, `Work.finished` ferme la fenêtre single-inflight, `on_reply` répond si autorisé | `main.py`, `twitch_irc.py`, `tests/test_persona_runtime_20261115.py` | IRC ne connaît pas les spectateurs silencieux, pas de test Twitch connecté dans la CI |
| Mémoire SQLite et curation | `MemoryStore` + `MemoryService` instanciés si `JADE_MEMORY_ENABLED`; conservation et curation optionnelles | `main.py`, `memory_service.py`, `memory_store.py`, tests mémoire | Base SQLite et activation opt-in doivent être préparées sur le PC ; aucun fichier de mémoire privé dans Git |
| Identité propriétaire | Microphone et mobile authentifié convergent sur l'identité de Goldaj | `main.py`, `memory_store.py`, `tests/test_jade_integrated_mobile_memory.py` | Ne pas confondre avec l'identité publique Discord/Twitch |
| PWA Android | `MobileGateway` créé depuis `main.py`, origine HTTPS `.ts.net` et identité Tailscale vérifiées par `Settings` | `mobile_gateway.py`, `mobile_web/`, `config.py`, tests mobiles | Tailscale Serve, SDK Live2D Web propriétaire et mobile réel non validés |
| Intentions, facial et texte | Étiquette d'intention normalisée, deux réactions par intention ; avatar PC et PWA ont accès au contrat partagé | `intent_engine.py`, `intent_visuals.py`, `avatar.py`, `mobile_web/avatar.js`, `test_jade_intent_visuals.py` | 14 expressions/réactions configurées ne sont **pas** 14 motions corporelles Live2D riggées |
| Launcher Windows | Scripts d'installation/lancement et préflight existants, démarrage du moteur en `--all-channels` | `scripts/jade-launcher.ps1`, `scripts/jade-runner.ps1`, `tests/`, CI Windows | L'installation et la recette sur le poste Jade restent à exécuter localement |
| Sous-titres et sorties | `SpeechOutput`, sorties Discord/Twitch et avatar sont branchés à `on_reply` | `main.py`, `output.py`, `turn_logging.py` | Les sorties dépendent des périphériques, clés, SDK et autorisations effectives |

## Incohérences documentaires corrigées pendant cette mission

1. `BRANCH_STATE.md` présentait la synchronisation d'expressions comme **non intégrée**, alors que la PR #18 a été fusionnée le 15 novembre 2026. La mention est corrigée, sans prétendre que les 14 animations riggées existent.
2. Le même guide présentait la PR #19 comme encore conditionnelle ; elle est fusionnée depuis le 15 novembre 2026.
3. Le statut de la CI après la PR #20 du 16 novembre est distingué de la recette physique : Ubuntu, Windows et scan secrets verts sur la tête de PR ; la validation après merge et le PC réel sont des contrôles distincts.
4. `BRANCH_MAINTENANCE.md` signale désormais les PR #18/#19/#20 intégrées et le nouveau merge d'ascendance `main` → `develop` au commit `dda14d1`, sans prétendre qu'un nettoyage des branches a été réalisé.
5. L'application Web contient une méthode de retour à l'expression neutre ; sa compatibilité SDK reste non prouvée, contrairement à une ancienne mention générale d'absence.

## Critères encore ouverts, à confier par ordre

- **Intégration locale, persona DevOps Windows** : vérifier sans écraser les modifications Terra/Codex : `git status`, branches/worktrees, sauvegarde/commit des travaux, fetch, fast-forward contrôlé ; valider Poetry, ffplay, Tailscale Serve, SQLite, secrets locaux et launcher.
- **Recette multicanal, persona QA + voix Discord** : tests réels Discord écrit/vocal, Twitch, micro et mobile ; vérifier la vraie politique 100 %/30 %, les ordres d'interruption et les conversations conservées sans fuite entre comptes.
- **Recette visuelle, persona Live2D** : r20 animé PC, SDK Web réel sur téléphone et retour au neutre ; le r21 en pied et les 14 motions 2D restent un chantier indépendant.
- **Observabilité, persona SRE** : mesurer délais STT/LLM/TTS, taux de sélection, queue, annulations, coût, déconnexions et limites, sans exposer de secrets ou de contenu privé.
- **Nettoyage Git, persona responsable intégration** : comparer chaque branche en lecture seule avec `develop`, ne supprimer que les branches explicitement intégrées, sans modifier `main` ni les worktrees locaux.

## Références Git de vérification

- PR #18 : https://github.com/goldaj/jade-vtuber/pull/18 (fusionnée)
- PR #19 : https://github.com/goldaj/jade-vtuber/pull/19 (fusionnée)
- PR #20 : https://github.com/goldaj/jade-vtuber/pull/20 (fusionnée)
- CI de la PR #20 : https://github.com/goldaj/jade-vtuber/actions/runs/43930954680 (Windows et Ubuntu réussis)
- Scan de secrets de la PR #20 : https://github.com/goldaj/jade-vtuber/actions/runs/43930954773 (réussi)
- Réconciliation historique : https://github.com/goldaj/jade-vtuber/commit/dda14d1108bd91a53f75c3827af472c626479cca

**Conclusion** : les principaux modules annoncés sont instanciés et câblés dans `develop`, mais l'intégration matérielle et l'exploitation réelle ne sont pas validées par une CI hors ligne. Ne pas promouvoir cette preuve de câblage en preuve de déploiement ou de performance.
