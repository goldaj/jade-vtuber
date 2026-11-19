# Mission : quick wins Jade, voix, routage et télémétrie (19 novembre 2026)

- **Agent/rôles** : ChatGPT, implémentation ; revue par perspectives PO, Tech Lead et QA.
- **Cartes** : DEV-005 (texte sans TTS), DEV-003 (fallback WAV Discord), DEV-006 (VTS non bloquant), DEV-007 (pool TTS), DEV-008 (latence). Toutes **En cours** pendant la vérification.
- **Base** : `develop` `fba75d4010fb0e297b8f1145b6da9800227a13aa` ; branche `feat/jade-quickwins-routing-voice-metrics-20261119`.
- **PR** : ouvrir sur `develop` et renseigner le lien et le SHA de validation.
- **Ordre exécuté** : 1) source écrite sans TTS ; 2) vocal Discord WAV sans son local ; 3) VTS non bloquant ; 4) pool Realtime partagé ; 5) jalons multi-canaux.
- **Preuves prévues** : tests ciblés de politique, révocation, absence de double lecture, hotkey bloqué, pool et métriques sans contenu ; CI hors ligne Ubuntu/Windows et scan secrets. Pas de recette matérielle ni d'API payante.
- **Définition de Done** : pas de Done sans code, tests, validation distincte par Codex ou propriétaire, intégration sur develop et traçabilité. ChatGPT en chat seul ne peut pas valider au nom de Codex.
- **Limites** : animations avatar multi-audience non traitées, premier son et coûts réels non mesurés, CI et pratiques PC à confirmer ; REC-005/007/010 restent ouvertes ; RTE-14 console privée reste P2.
- **Aucune action** sur main, comptes, poste, secrets ni fichiers artistiques.
- **Sources** : [DEV](../../backlog/01-DEVELOPPEMENT.md), [DoD](../../backlog/DEFINITION_OF_DONE.md), [état](../../handbook/BRANCH_STATE.md), [journal](../CHANGELOG.md).

- **Réglage de mesure** : `JADE_LATENCY_LOG=1` dans la configuration privée. Les jalons sont désactivés par défaut ; pas de première trame audible ni de coûts réels garantis.
