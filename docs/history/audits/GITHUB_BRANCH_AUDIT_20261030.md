# Audit de branches et passation — 2026-10-30

**Vérifié :** branches et PR ouvertes sur GitHub. **À compléter :** revue exhaustive des diffs et tests. Ne pas supprimer une branche à partir de son nom.

- Dépôt : `goldaj/jade-ai-vtuber` ; branche par défaut : `develop`.
- PR ouvertes : [#2](https://github.com/goldaj/jade-ai-vtuber/pull/2) (brouillon : oui).

## Branches (9)
- `codex/chat-gpt6-jade-rebuild`
- `develop` (défaut)
- `elevenlabs-stream`
- `handle_stream`
- `master`
- `refacto`
- `research/gpt6-jade-publication-readiness-20261028`
- `speechtotext-discord`
- `stream_chat`

## Contre-audit et reprise
- **PR #2 : ne pas fusionner ni déployer sans accord du propriétaire.** La PR #1 est incluse par ascendance dans #2 ; cette dernière est la PR de passation unique.
- Vérifier secrets, sources Cubism/Live2D, Git LFS, TTS/STT OpenAI et tests de runtime ; conserver les anciennes branches de prototypes vocaux pour audit avant suppression.
- Comparer individuellement SHA, ascendance et fichiers de chaque branche à sa cible réelle ; relire les PR clôturées.
- Protéger les branches de déploiement, les assets et les données privées. Exécuter CI et tests avant toute intégration.

**Statut :** inventaire et risques documentés ; validation fonctionnelle restant à effectuer.

## Vérification supplémentaire du graphe Git

- **Comparaison actualisée :** `develop...research/gpt6-jade-publication-readiness-20261028` = divergence, 48 commits propres à la recherche et 3 commits nouveaux sur `develop` (83 fichiers dans le diff). Rebaser/merger prudemment les 3 commits de develop dans la branche de PR, sans déployer.
