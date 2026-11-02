# Jade : branche unique d'intégration Codex, 29 octobre 2026

**PR #2 :** https://github.com/goldaj/jade-ai-vtuber/pull/2, cible `develop`.

La PR existante regroupait déjà la refonte du runtime Python, la séparation des configurations locales/publiques, les connecteurs OpenAI voix (STT/TTS), Discord, Twitch, VTube Studio, les tests hors ligne, ainsi que le protocole de publication. Les changements Codex du 28/10 sur les procédures de production du modèle 2D étaient apparus ensuite sur `develop` et provoquaient **un conflit Git** sur les consignes.

Le 29/10, un **véritable merge Git à deux parents** a intégré le dernier `develop` à la PR #2. Les quatre documents `jade-modeling/MODEL2D_CODEX_*` et `RIG_CODEX_*` ont été conservés. Les journaux ont été réunis, et l'ancien `AGENTS.md` Codex archivé. `AGENTS.md` actif conserve la règle propriétaire plus récente : **Tera 6.1 par défaut**, demande de passage manuel à Astra initiée par Tera en cas de doute, revue Astra selon choix du propriétaire. Les anciens documents n'autorisent pas à imposer Astra par défaut.

**État :** comparaison Git `develop...PR #2` maintenant `ahead` (plus aucun commit de `develop` manquant), PR devenue mergeable. **Ne pas fusionner automatiquement** : les changements de runtime nécessitent un vrai essai utilisateur, les workflows privés ont échoué sans logs/étapes exploitables, et aucune validation réelle STT/TTS/Twitch/Discord/Live2D n'a été exécutée pendant cette consolidation.

**Pour Codex :** relire les docs `docs/gpt6-jade/`, les nouveaux documents MODE L2D, et la politique modèle active. Vérifier la branche, refaire les tests hors ligne sur un runner disponible, inspecter les assets LFS sans publier de secrets, puis réaliser les tests d'intégration sur la machine autorisée. La PR #2 est l'unique branche d'évolution à intégrer ; les autres branches de travail restent des ancêtres historiques.


## Preuve de blocage Actions privé (29/10)

L'action `Private runner diagnostic` [#40924249395](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40924249395) se limite à un `echo` et échoue, comme les workflows de tests, **avant toute étape enregistrée**. Le provisionnement des runners pour ce dépôt privé est à vérifier côté paramètres/budget GitHub Actions avant de conclure à un défaut du runtime. Aucun test Jade réel n'a été validé sur cette nouvelle tête.
