# Audit critique Jade : branches et passation — 30/10/2026

**Attention :** aucune publication, aucun merge ou déploiement décidé par cette passe. Le projet contient des sources 2D/Cubism et un runtime vocal privé ; préserver secrets, assets et état Live2D. Aucun test vocal, rig, animation, PC ni API OpenAI exécuté dans cet audit.

## Branches (cible `develop`)
- `develop` : `01fa3b80f337c8e692158df1fd2e1dc41571abe9` (branche de travail de référence).
- `codex/chat-gpt6-jade-rebuild` (`410404a39fbbdecdcb7a6befc5aac47bff598ab6`) : diverged, ahead 34, behind 19. Historique de la PR #1 contenu dans #2, sans raison de rouvrir #1.
- `elevenlabs-stream` (`5f3494be2f5f262e3ebfcfe2e1d9cdf351e7eaa2`) : ascendance non recalculée dans ce lot ; préserver jusqu'à comparaison dédiée. 
- `handle_stream` (`b24e4181deeff31444e8c4f713b63e0f3c2f8c2a`) : ascendance non recalculée dans ce lot ; préserver jusqu'à comparaison dédiée. 
- `master` (`b24e4181deeff31444e8c4f713b63e0f3c2f8c2a`) : ascendance non recalculée dans ce lot ; préserver jusqu'à comparaison dédiée. 
- `refacto` (`dbc0a09b1b661fcbf9b13ee882f50cbd8eed90cd`) : ascendance non recalculée dans ce lot ; préserver jusqu'à comparaison dédiée. 
- `research/gpt6-jade-publication-readiness-20261028` (`df544ed78976096c522912a56ef9086c554e52ac`) : diverged, ahead 48, behind 4. **PR active #2 à conserver ; ne pas fusionner avant accord.**
- `speechtotext-discord` (`78c158eafccf887883794e4a4e0f642b90e43897`) : diverged, ahead 7, behind 25. Code ancien divergent de voix non-OpenAI : ne pas recycler sans revue.
- `stream_chat` (`fda4b8168b67a90f0ca3cc93aee4d9629bc32a4b`) : ascendance non recalculée dans ce lot ; préserver jusqu'à comparaison dédiée. 

## PR
- [#2](https://github.com/goldaj/jade-ai-vtuber/pull/2) : **ouverte**, brouillon, `research/gpt6-jade-publication-readiness-20261028` → `develop`.
- [#1](https://github.com/goldaj/jade-ai-vtuber/pull/1) : clôturée sans fusion, brouillon, `codex/chat-gpt6-jade-rebuild` → `develop`.

## Challenge du travail
- **Runtime** : la PR #2 couvre de nombreux fichiers et refonte asynchrone ; vérifier queues, annulations, latence bout en bout, erreurs STT/TTS, interruptions vocales, résilience Discord/Twitch, redémarrage et secrets. Remplacer les moteurs voix non-OpenAI ; orienter les appels API sur la vitesse, mais ne pas promettre de latence sans mesure.
- **Modèle 2D** : lire `jade-modeling/MODEL2D_CODEX_PLAYBOOK.md` et `MODEL2D_CODEX_STATE.md`. Tera 6.1 exécute par défaut dessin/rig/animations/physique sur poste ; demande manuelle à Astra sur doute ou jalon, pas de switch automatique. Conserver fichiers natifs et preuves visuelles ; aucun rig/test VTube Studio validé ici.
- **Publication future** : inspecter secrets/LFS, historiques et permissions ; **PR #2 DRAFT non fusionnable sans accord explicite**. La PR #1 fermée ne doit pas être assimilée à une publication ou à du code intégré dans `develop`.
- **Ancien code** : ne pas réintroduire ElevenLabs ni anciennes routines Discord concurrentes depuis `speechtotext-discord` ; comparer le besoin fonctionnel à l'architecture cible.

## Passation reproductible
Lire `AGENTS.md`, `docs/CODEX_PARALLEL_GPT6.md`, `docs/CHATGPT_PROJECT_HISTORY.md`, le README (« # Jade — VTuber IA, voix et modèle Live2D ») et tous les guides PR #2. Monter un environnement local secret-free avec mocks ; mesurer erreurs et performances, vérifier les assets LFS puis préparer une revue humaine. Ne toucher à aucune prod, stream, compte ou modèle natif pendant un audit documentaire.

**Sources vérifiées :** branches, comparaisons ciblées, état PR GitHub au 30/10/2026. Les branches non comparées sont explicitement à recontrôler, pas présumées inutiles. Aucun test exécuté, seul ce document est ajouté.
