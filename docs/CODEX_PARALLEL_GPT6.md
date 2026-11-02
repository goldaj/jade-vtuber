# Coordination Jade : GPT-6 Chat / Codex (2026-10-24)

> **État courant au 2 novembre 2026 :** la PR #1 est fermée sans fusion et son
> historique est entièrement inclus dans la PR #2, toujours en brouillon.
> La branche consolidée est `research/gpt6-jade-publication-readiness-20261028`.
> Lire [la migration préparée](migration/2026-11-02/README.md) avant de reprendre.
> Le texte ci-dessous est conservé comme historique du 24 octobre.

GPT-6 Chat travaille en parallèle sur la branche isolée
[`codex/chat-gpt6-jade-rebuild`](https://github.com/goldaj/jade-ai-vtuber/tree/codex/chat-gpt6-jade-rebuild).
La **[PR #1 en brouillon](https://github.com/goldaj/jade-ai-vtuber/pull/1)**
regroupe les modifications de code, la CI et les rapports, sans fusion ni déploiement.
**Ne pas fusionner cette branche ni utiliser ses fonctions en direct sans revue.**

## Décisions du propriétaire
- Refonte Python du runtime Jade autorisée dans la branche GPT-6, par étapes,
  avec tests et CR. Ne toucher à `develop` que pour la coordination.
- **STT et TTS exclusivement OpenAI** dans le nouveau runtime ; priorité à la
  faible latence plutôt qu'à la fidélité maximale. ElevenLabs et les autres
  fournisseurs de synthèse/transcription doivent disparaître du chemin actif.
- LLM interchangeable : OpenAI utilisable tout de suite, exécution locale
  optionnelle à terme, sans reconcevoir les entrées/sorties.
- Conserver les assets Git LFS, jalons Cubism r21 v30, candidat r02 et export
  VTube Studio r20 ; ne pas effectuer de modification aveugle de la modélisation.
- Historique du dépôt sensible : **ne pas rendre public**, pas de suppression de
  branches ou de réécriture historique ; aucune API payante dans les tests.

## Lors du passage de Codex
1. Lire les documents de `docs/gpt6-jade/` sur la branche parallèle :
   `HANDOFF.md`, `TASKS.md`, `DECISIONS.md`, `CONVERSATIONS.md`.
2. Relire les tests et vérifier les intégrations sur le matériel de l'utilisateur ;
   aucune simulation ne prouve le fonctionnement réel des API/audio/Discord/Twitch.
3. Vérifier les dépendances Git LFS / Cubism indépendamment du runtime Python.
4. Ne pas exécuter de double refonte concurrente des mêmes fichiers sans comparer
   les deux branches et avertir le propriétaire.

Ce fichier est une note de coordination, pas une validation technique.
