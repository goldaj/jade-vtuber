# Branches et stratégie d’intégration

Relevé du 2 novembre 2026, par lecture de GitHub et calcul local sur le clone d’audit. Le dépôt courant est [jade-ai-vtuber](https://github.com/goldaj/jade-ai-vtuber), privé. Sa branche par défaut est `develop`. **Le propriétaire confirme qu’aucune production n’est active.** La cible proposée pour réunir le code est `develop` ; aucun renommage ou déplacement de `master` n’est préparé implicitement.

## Graphe utile

| Référence | SHA | Commits propres à `develop` / à la branche | Traitement prévu |
| --- | --- | ---: | --- |
| `develop` | `6420e249c3cb006cd71cdfcc3f59966e4a74477f` | — | Cible d’intégration et conservation des nouveaux documents |
| `research/gpt6-jade-publication-readiness-20261028` | `df544ed78976096c522912a56ef9086c554e52ac` | 6 / 48 | Source consolidée à corriger, puis une seule intégration |
| `codex/chat-gpt6-jade-rebuild` | `410404a39fbbdecdcb7a6befc5aac47bff598ab6` | 21 / 34 | Entièrement ancêtre de research ; pas de seconde fusion |
| `master` | `b24e4181deeff31444e8c4f713b63e0f3c2f8c2a` | 26 / 0 | Ancêtre historique, conserver la référence |
| `handle_stream` | `b24e4181deeff31444e8c4f713b63e0f3c2f8c2a` | 26 / 0 | Ancêtre, aucun code exclusif |
| `elevenlabs-stream` | `5f3494be2f5f262e3ebfcfe2e1d9cdf351e7eaa2` | 27 / 0 | Ancêtre, aucun code exclusif ; ne pas réintroduire l’ancien fournisseur |
| `refacto` | `dbc0a09b1b661fcbf9b13ee882f50cbd8eed90cd` | 48 / 0 | Ancêtre, aucun code exclusif |
| `stream_chat` | `fda4b8168b67a90f0ca3cc93aee4d9629bc32a4b` | 60 / 0 | Ancêtre, aucun code exclusif |
| `speechtotext-discord` | `78c158eafccf887883794e4a4e0f642b90e43897` | 27 / 7 | Réconcilier les intentions ; aucune fusion brute |

La PR [#1](https://github.com/goldaj/jade-ai-vtuber/pull/1) est fermée **sans fusion**. La PR [#2](https://github.com/goldaj/jade-ai-vtuber/pull/2) est ouverte en brouillon, vers `develop`. Rebuild est ancêtre de research : comparaison `rebuild...research = 0 / 29`. La base commune de research et develop est `fe4b7f4f7eee97d0a3b535e1919949daab46bfed`.

Le diff de la branche research depuis cette base commune touche 83 fichiers, avec 3 933 ajouts et 4 722 suppressions, dont le retrait du vieux verrou et de seize modules legacy. Aucun fichier `jade-modeling/**` n’y change. Il s’agit d’une refonte, pas d’une petite mise à jour interchangeable avec le lancement de 2025.

## Les six commits de develop à préserver

| Commit | Contenu |
| --- | --- |
| `f81dfb7` | Audit contradictoire et passation du 30 octobre |
| `3455263` | Complément sur les échecs CI |
| `d53a1e5` | Inventaire GitHub et consignes de reprise |
| `01fa3b8` | Divergence actualisée dans l’audit |
| `3a69f11` | Audit branches et passation |
| `6420e24` | Migration des pistes Notepad le 1er novembre |

Ils ajoutent ou complètent seulement quatre documents, 271 lignes :

- `docs/AUDIT_BRANCHES_PASSATION_2026-10-30.md`
- `docs/AUDIT_PASSATION_2026-10-30.md`
- `docs/GITHUB_BRANCH_AUDIT_20261030.md`
- `docs/NOTEPAD_IDEAS_MIGRATION_2026-11-01.md`

Aucun de ces chemins n’est modifié sur research depuis la base commune. Aucun conflit textuel n’est donc anticipé à ces SHA, **sans avoir exécuté de merge ni de simulation de merge**. Les contradictions de dates et de workflow exigent néanmoins une réconciliation documentaire : garder les textes historiques, ajouter un état courant clairement daté.

Les pistes du 1er novembre comprennent speech-to-speech, Showrunner, Smart Chat, MoodSync, Control Room et Rehearsal Lab. Elles sont conservées comme **idées à réévaluer**, pas comme fonctionnalités livrées ou mandat d’extension de cette migration. MoodSync et les validations visuelles restent hors périmètre actuel.

## Réconciliation des sept commits Discord

Les sept commits exclusifs comprennent le WIP final et six commits de merge. Leur delta net concerne neuf fichiers. Les intentions utiles ont déjà des équivalents :

| Intention historique | Équivalent de la refonte | Décision |
| --- | --- | --- |
| Rejoindre un canal vocal configuré | `DiscordText.on_ready` et `DiscordVoiceBridge.connect` | Corriger et tester l’implémentation actuelle |
| Recevoir PCM, convertir WAV, transcrire | `receive_pcm`, `pcm_48k_stereo_wav`, `_consume` | Conserver OpenAI ; segmentation fixe 2 s encore expérimentale |
| Parler dans Discord | `SpeechOutput.secondary_player`, `DiscordVoiceBridge.play` | Conserver OpenAI, vérifier arrêt et lecture |
| Orchestrer micro/chat/vocal | Queue `Runtime`, `VoiceInput`, bridge injecté | Corriger concurrence et fermeture |
| Globals partagés et ancien consumer | Injection runtime/services/bridge | Obsolète, aucun portage |
| Voix ElevenLabs et outil affichant les jetons | OpenAI et configuration privée | Ne pas réintroduire |

Les sept commits restent préservés dans leur branche. Une conclusion « intentions reprises, code non fusionné pour les raisons ci-dessus » constitue la clôture d’intégration de cette branche. Faire une fusion factice avec la stratégie `ours` ou réimporter son code pour obtenir un graphe artificiellement complet ne prouverait aucune reprise fonctionnelle.

## Environnements existants

Le dossier de chat contient surtout les travaux 2D, avec des jonctions d’assets/reports vers D:. Son dépôt englobant n’a aucun commit et ne doit pas être confondu avec le dépôt applicatif. Le clone applicatif historique est propre, mais ses références locales sont antérieures au distant. Il n’a été ni actualisé ni changé de branche par cet audit.

La copie d’audit sur D: est partielle (`--filter=blob:none`, LFS non matérialisé) : elle convient au code et à la documentation, **pas à une sauvegarde complète**. Préserver les anciens clones et les sources ; si une sauvegarde de migration est nécessaire, inclure séparément les objets Git, LFS et les fichiers privés, avec accès protégé et restauration vérifiée.
