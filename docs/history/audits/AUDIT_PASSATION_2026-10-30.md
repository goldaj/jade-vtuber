# Contre-audit GitHub et passation Jade — 2026-10-30

9 branches et 2 PR vérifiées via API GitHub. Le runtime, VTube Studio, Cubism, les voix et les API **n'ont pas été exécutés**. **La PR #2 indique explicitement qu'aucune fusion/déploiement n'est autorisé sans accord du propriétaire : restriction conservée.**

## Branche de référence et branches secondaires
- `develop`: `fe4b7f4f7eee97d0a3b535e1919949daab46bfed`. Ne pas fusionner la PR #2 pendant cet audit.
- `research/gpt6-jade-publication-readiness-20261028`: `df544ed78976096c522912a56ef9086c554e52ac` : **ahead de 48 commits** / 0 behind contre develop. Branche de la **PR #2 ouverte en brouillon** ; à conserver.
- `codex/chat-gpt6-jade-rebuild`: `410404a39fbbdecdcb7a6befc5aac47bff598ab6` : diverged vs develop (+34 / −15), mais **behind, 0 commit exclusif** comparée à la PR #2. Les commits de la PR #1 sont absorbés dans la PR #2 : candidate nettoyage avec maintien des références.
- `speechtotext-discord`: `78c158eafccf887883794e4a4e0f642b90e43897` : diverged vs develop (+7 / −21). **Ne pas réintroduire de STT/TTS tiers** : comparer l'histoire et archiver uniquement ce qui répond à un besoin actuel.
- `elevenlabs-stream` : behind, 0 commit exclusif ; ancien fournisseur interdit par la politique OpenAI-only, candidate nettoyage.
- `handle_stream` : behind, 0 exclusif ; candidate nettoyage sous réserve de dépendances.
- `refacto` : behind, 0 exclusif ; candidate nettoyage sous réserve de dépendances.
- `stream_chat` : behind, 0 exclusif ; candidate nettoyage sous réserve de dépendances.
- `master` : behind, 0 exclusif ; **branche historique de référence : ne pas supprimer sans examen des clones et automatisations**.

## PR
- [#1](https://github.com/goldaj/jade-ai-vtuber/pull/1) fermée sans fusion explicite : contenue dans PR #2 ; ne pas rouvrir.
- [#2](https://github.com/goldaj/jade-ai-vtuber/pull/2) ouverte, draft : branche unique de passation. Conserver et auditer les tests, la revue secrets et assets avant toute proposition de merge.

## Structure consultée
Racine : `.editorconfig`, `.env.example`, `.flake8`, `.gitattributes`, `.gitignore`, `.idea`, `AGENTS.md`, `PRIVATE_CONFIGURATION.md`, `README.md`, `docs`, `jade-modeling`, `main.py`, `mypy.ini`, `poetry.lock`, `prompt_chat.txt`, `pyproject.toml`, `src`, `tests`.

README (extrait) : # Jade — VTuber IA, voix et modèle Live2D

Jade est un projet de personnage animé qui combine un bot Python, des interactions
Twitch/Discord, un modèle de langage, de la synthèse vocale et un modèle Live2D.
Ce dépôt privé rassemble le développement applicatif, les sources artistiques,
le rig, les animations, les exports VTube Studio et les documents de suivi.

## État du projet

- Application : code Python 3.11 pour OpenAI, Twitch, Discord et ElevenLabs ;
  intégration à configurer avec ses propres comptes et périphériques.
- Modèle de travail : r21, dernier jalon natif conservé **v30** ; un candidat
  `v30.TEST_hair_leaves_r02` est également sauvegardé. La finition reste en cours.
- Export animé utilisable comme point de reprise : package VTube Studio
  `Jade_professional_r20_idle_complete`, avec textures, physique, expressions et
  mouvements. Il correspond à une génération antérieure au rig r21 en cours.
- Les validations de configuration sont automatisées ; aucun démarrage en direct
  ni appel aux services payants n'est effectué par ces tests.

## Contenu

| Emplacement | Rôle |
| --- | --- |
| `main.py`, `src/` | Bot, dialogue, audio et connexions aux services |
| `prompt_chat.txt` | Personnalité du personnage |
| `jade-modeling/assets/` | Dernières sources pertinentes Cubism/Krita/PSD et composants artistiques r21 |
| `jad

AGENTS (extrait) : # AGENTS.md — Jade

> **Coordination en cours** : avant toute modification par Codex, lire
> [`docs/CODEX_PARALLEL_GPT6.md`](docs/CODEX_PARALLEL_GPT6.md) : GPT-6 Chat
> développe sur `codex/chat-gpt6-jade-rebuild` (branche séparée).
> Aucun merge ou déploiement implicite.

## Protocole validé de production du modèle 2D de Jade — 28 octobre 2026

**OBLIGATOIRE dès la prochaine session de travail consacrée au personnage 2D** (dessin, calques/assets, rig, physique, animations, expressions, export et tests VTube Studio). Le propriétaire a expressément approuvé le protocole général et son extension à l'ensemble du modèle 2D. Ce n'est **pas** l'approbation d'un plan technique encore inexistant.

1. Lire [`jade-modeling/MODEL2D_CODEX_PLAYBOOK.md`](jade-modeling/MODEL2D_CODEX_PLAYBOOK.md) pour les rôles Astra/Terra/Sol, l'organisation et les changements manuels de modèle.
2. Lire [`jade-modeling/MODEL2D_CODEX_STATE.md`](jade-modeling/MODEL2D_CODEX_STATE.md) pour la prochaine action, le modèle recommandé, les preuves et la reprise.
3. Lire `jade-modeling/MODEL2D_MASTER_PLAN.md` **seulement s'il existe et a été validé**. Sinon demander le passage manuel à **GPT-6 Astra** pour produire le plan détaillé de toute la chaîne 2D ; puis faire valider ce plan avant exécution.
4. Codex **ne change jamais de modèle automatiquement**. Au besoin, s'a

## Challenge technique à fournir au prochain agent
1. Retirer ou désactiver tous chemins TTS/STT non OpenAI, sans laisser de fallback silencieux ; viser les modèles API orientés faible latence, avec preuves de bout-en-bout et dégradations contrôlées.
2. Runtime async : file bornée, backpressure, gestion des interruptions, reconnexion Twitch/Discord, erreurs d'API, limites de coût et protection des secrets.
3. Vérifier sources Live2D/Cubism et Git LFS, pas seulement PNG d'aperçu ; l'agent sur PC doit contrôler rig, couches, expressions, animations et physique réellement modifiables.
4. Orchestration des outils : **Tera 6.1 par défaut** pour dessin/rig/animation/physique, sollicitation explicite d'un passage humain à Astra sur doute majeur, sans auto-validation fictive.
5. Préparer tests simulés sans clés, test réel de latence et revue de publication/sécurité **avant** toute fusion sur develop. Préserver la consigne de non-déploiement de la PR.

Aucun changement autre que ce document sur `develop` pendant la présente passe.


## Constat complémentaire : workflows GitHub Actions (30 octobre 2026)
- [Jade rebuild offline tests PR #2](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40924327854) : **failure** ; [publication hygiene](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40924327803) : **failure** ; [private runner diagnostic](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40924316318) : **failure**.

Le connecteur a renvoyé des jobs en échec, mais aucune étape détaillée ; le téléchargement des logs échoue côté GitHub (`BlobNotFound`). **Cause non établie** : ne pas attribuer l'échec aux tests applicatifs ni aux runners sans logs. Priorité : obtenir les diagnostics des jobs, relancer une exécution contrôlée et consigner la preuve CI avant merge/release. Le présent constat ne modifie aucun code.
