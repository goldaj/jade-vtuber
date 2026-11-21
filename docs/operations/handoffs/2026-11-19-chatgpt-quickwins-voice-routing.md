# Mission : quick wins Jade, voix, routage et télémétrie (19 novembre 2026)

- **Agent/rôles** : ChatGPT, implémentation ; revue par perspectives PO, Tech Lead et QA.
- **Cartes** : DEV-005 (texte sans TTS), DEV-003 (fallback WAV Discord), DEV-006 (VTS non bloquant), DEV-007 (pool TTS), DEV-008 (latence). Toutes **À valider** après CI verte, en attente de validation officielle Codex OU propriétaire.
- **Base** : `develop` `fba75d4010fb0e297b8f1145b6da9800227a13aa` ; branche `feat/jade-quickwins-routing-voice-metrics-20261119`.
- **PR** : [#26](https://github.com/goldaj/jade-vtuber/pull/26) vers `develop` ; branche relue sur SHA `c79976cdc40293262c26ea301e93efbb9033fff6` avant ce commit documentaire.
- **Ordre exécuté** : 1) source écrite sans TTS ; 2) vocal Discord WAV sans son local ; 3) VTS non bloquant ; 4) pool Realtime partagé ; 5) jalons multi-canaux.
- **Preuves prévues** : tests ciblés de politique, révocation, absence de double lecture, hotkey bloqué, pool et métriques sans contenu ; CI hors ligne Ubuntu/Windows et scan secrets. **Constat réel : CI Windows et Ubuntu SUCCESS**, documentation contract PASS, scan secrets SUCCESS sur `c79976c` ([tests](https://github.com/goldaj/jade-vtuber/actions/runs/44478307734), [scan](https://github.com/goldaj/jade-vtuber/actions/runs/44478307610)). Pas de recette matérielle ni d'API payante.
- **Définition de Done** : pas de Done sans code, tests, validation distincte par Codex ou propriétaire, intégration sur develop et traçabilité. ChatGPT en chat seul ne peut pas valider au nom de Codex.
- **Limites** : animations avatar multi-audience non traitées, premier son et coûts réels non mesurés, pratiques PC à confirmer ; REC-005/007/010 restent ouvertes ; RTE-14 console privée reste P2.
- **Aucune action** sur main, comptes, poste, secrets ni fichiers artistiques.
- **Sources** : [DEV](../../backlog/01-DEVELOPPEMENT.md), [DoD](../../backlog/DEFINITION_OF_DONE.md), [état](../../handbook/BRANCH_STATE.md), [journal](../CHANGELOG.md).

- **Réglage de mesure** : `JADE_LATENCY_LOG=1` dans la configuration privée. Les jalons sont désactivés par défaut ; pas de première trame audible ni de coûts réels garantis.

## Passe de revue distincte (PO / Tech Lead / QA, ChatGPT)

- **DEV-005** : contrôle du callback principal et de la matrice de destinations, tests Twitch/Discord texte sans appel TTS malgré voix configurée : constat favorable.
- **DEV-003** : repli WAV Discord limité à la session autorisée, sans son local ni sous-titre OBS partagé ; tests d'annulation/révocation, et remplacement du test historique qui attendait le double lecteur : constat favorable.
- **DEV-006** : hotkey facultatif exécuté sans bloquer la synthèse, annulable à l'arrêt ; test avec hotkey simulé bloquant : constat favorable.
- **DEV-007** : injection du même pool Realtime dans synthèse bufferisée et streaming, sans modifier la règle de non-répétition après émission : constat favorable.
- **DEV-008** : option de métriques désactivée par défaut et tests toutes plateformes ; pas de texte privé dans les métriques, mais pas de preuve de première parole réellement audible : constat favorable pour le périmètre instrumenté.
- **Validation DoD** : cette contre-revue ChatGPT et les CI vertes **ne sont pas une validation Codex**. Aucune carte n'est déclarée Done. Passer à Done uniquement après approbation explicite par Codex ou propriétaire et intégration vérifiée dans develop.
