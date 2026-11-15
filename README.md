# Jade — un personnage virtuel capable de dialoguer

**Documentation complète et spécifique à cette branche develop :** [installation depuis un poste neuf](docs/handbook/INSTALLATION.md), [Démo Express sans installation Python](docs/handbook/DEMO.md), [guide utilisateur de toutes les fonctions](docs/handbook/USER_GUIDE.md), [architecture et algorithmes](docs/handbook/TECHNICAL.md), [passation agents IA](docs/handbook/AI_HANDOFF.md), [état précis de develop](docs/handbook/BRANCH_STATE.md).

**Démo immédiate Windows :** double-cliquer `Installer-Demo-Express.cmd` ou `Lancer-Demo-Express.cmd`. Démo **simulée** : aucune IA, aucune clé, aucun canal ni Live2D requis. **Produit réel :** installer/configurer tous les canaux puis utiliser le launcher unique `--all-channels`, voir les guides. 

![Portrait de Jade](jade-modeling/assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png)

Jade est un projet expérimental de VTuber IA : un personnage 2D conçu pour
interagir par texte et par voix. Ce dépôt présente le moteur Python qui reçoit
les messages, prépare une réponse et peut la transmettre à des outils de
streaming. Le travail sur le personnage et son animation est mené séparément.

> **État : prototype en cours de développement.** Le mode de démonstration
> fonctionne hors ligne. Les connexions aux plateformes et les appareils audio
> demandent encore une validation réelle.

## Ce que fait le moteur

- Reçoit les messages depuis Discord écrit/vocal, Twitch, micro Windows,
  API HTTP locale et PWA Android privée. Le launcher active tous ces canaux
  simultanément via --all-channels, sans choix de mode.
- Met les demandes dans une file bornée, maintient un historique limité par
  conversation et produit des réponses via une interface de dialogue modulaire.
- Utilise **OpenAI exclusivement pour la transcription et la synthèse vocale** ;
  le modèle de dialogue OpenAI est configurable. Une réponse de démonstration
  remplace l’appel réseau en mode hors ligne.
- Prépare la lecture vocale, les sous-titres OBS et les interactions avec l’API
  locale de VTube Studio. Ces intégrations sont désactivées par défaut.

```text
Discord / Twitch / HTTP / Android PWA ─────┐
Microphone / vocal → STT OpenAI ───────────┤
                                            ↓
                               File → Arbitre Jade
                                            ↓
                                  Dialogue + mémoire
                                            ↓
                      Réponse routée / TTS / avatar
```

Le dialogue dispose d’une interface backend interchangeable dans le code ; seul
le backend OpenAI et le backend de démonstration sont fournis actuellement.

## Essayer la démo sans clé API

Une démo Windows animée est préparée avec le modèle Live2D r20, dialogue et
voix OpenAI : consultez son [guide](demo/reelle/GUIDE-DEMO.md) et sa
[notice de construction](demo/reelle/README-BUILD.md). Elle demande une clé
OpenAI personnelle et une connexion Internet pour les échanges réels.

Une [ancienne démo statique hors ligne](demo/windows/README.md) reste disponible :
elle utilise un portrait et un dialogue simulé, sans IA ni animation Live2D.

Prérequis : Python 3.11 et Poetry 2.2.1. Depuis la racine de cette copie :

```bash
poetry sync --only main
poetry run python main.py
```

Saisissez un message puis `/exit` pour quitter. La réponse porte le préfixe
« Mode démo » : c’est un comportement simulé, sans appel à un modèle distant.
Aucun microphone ni compte de service n’est nécessaire.

Pour lancer les vérifications hors ligne :

```bash
poetry run python -m unittest discover -s tests -v
poetry run python main.py --preflight
```

Le projet fournit un fichier de dépendances verrouillé `poetry.lock`. Installer
Poetry et les dépendances nécessite un accès au registre de paquets ; une fois
installées, la démo et les tests n’appellent pas de service IA distant.

## Fonctionnalités et niveau de validation

| Élément | État de la preuve |
| --- | --- |
| Console, file de messages et historique | Tests automatisés hors ligne ; démo locale disponible |
| Texte OpenAI | Un essai réel court a réussi ; ce n’est pas une mesure de performance généralisable |
| Chaîne micro → STT → dialogue → TTS | Services simulés et courts essais STT/TTS OpenAI sur audio synthétique ; micro réel non testé |
| Twitch, Discord et Discord vocal | Authentification Twitch et connexion Discord vérifiées sans message ; vocal Discord réel non testé et expérimental |
| Sous-titres et VTube Studio | Interfaces et tests simulés ; configuration OBS et interactions VTube Studio réelles à vérifier |
| Personnage 2D | Sources et portrait inclus ; intégration et animation en cours |

La simulation vérifie des comportements logiciels et ne remplace pas un essai
matériel, une recette de diffusion ou une mesure de latence et de coût.

## Options et configuration privée

Le modèle, les connecteurs et les limites se configurent par environnement ou
par fichier privé sélectionné avec `JADE_SECRETS_FILE`. Les réglages non secrets
peuvent utiliser un profil de `config/profiles/`. Le prompt du personnage peut
être fourni séparément via `JADE_PROMPT_FILE` ou `JADE_ASSETS_ROOT` ; le prompt
du projet est inclus dans ce dépôt.

La démo console reste hors ligne. Pour le vrai fonctionnement sur Windows,
le launcher utilise `--all-channels` et active ensemble tous les supports
configurés ; le préflight bloque le démarrage si l'un des services obligatoires
manque. Cette exécution peut entraîner des frais OpenAI. Les anciens drapeaux
individuels restent disponibles pour le diagnostic et le développement, mais
ne constituent pas des profils de lancement utilisateur. Les extras Poetry
s'installent avec `poetry sync --only main -E all`. L'envoi Twitch requiert
`JADE_TWITCH_SEND=1` en plus du jeton et du salon.

Pour Twitch, un jeton utilisateur valide et le canal sont requis ; le nom du
bot est déduit du jeton si `TWITCH_BOT_LOGIN` est vide. La procédure pour obtenir
un jeton sans exposer les secrets est décrite dans [l'aide Twitch](docs/gpt6-jade/TWITCH-AUTH.md).
Le renouvellement automatique est facultatif et exige une sauvegarde GitHub
privée configurée ; ses garanties et limites sont détaillées dans cette aide.
Lorsque Discord vocal est connecté, certaines réponses vocales issues
d'autres sources peuvent être diffusées dans le salon actif. **Les réponses
locales privées (microphone du PC et API HTTP privée) ne doivent pas être
diffusées automatiquement dans Discord ou les sous-titres OBS publics.**
Le vocal ne demande ni liste de participants ni confirmation supplémentaire :
toute source entendue peut interagir, y compris un autre bot. Jade ignore sa
propre voix pour limiter les boucles. Le canal indiqué sert au raccordement
initial ; Jade peut être déplacée vers un autre salon. Une connexion vocale
Discord ne couvre qu'un salon à la fois par serveur. En texte, Jade traite
les messages reçus d'autres bots et de tous les salons, y compris les messages
privés ; elle ignore ses propres messages.

La lecture locale nécessite ffplay. Les segments vocaux destinés à la transcription
sont envoyés au fournisseur. L’interface HTTP reste liée à `127.0.0.1` ; un accès
depuis un autre appareil nécessite une solution sécurisée distincte.

Ne pas committer de clé API, jeton, enregistrement ou transcription privée.

## Sources 2D et Git LFS

Les sources du personnage sont dans `jade-modeling/`. Après clonage, installer
Git LFS puis lancer `git lfs pull` pour récupérer les ressources volumineuses.
Le contrôle d’intégrité s’exécute avec `python jade-modeling/verify_assets.py`.
Les documents de suivi du projet et l’index des conversations sont dans `docs/`.

## Launcher local pour Windows

Un [launcher Windows personnel](docs/gpt6-jade/LAUNCHER-WINDOWS-20261115.md) permet de choisir une branche et de lancer **tous les supports simultanément, sans choix de profil** : Discord vocal et écrit, Twitch, microphone local, HTTP local, application mobile privée, voix et avatar. Le moteur Jade arbitre les messages en attente, sans priorité fixe par support. Depuis le clone sur D:, exécuter `Installer-Launcher-Jade.cmd`, puis `D:\Jade\launcher\Lancer-Jade.cmd`. Il faut configurer tous les connecteurs dans la configuration privée ; un préflight incomplet bloque le démarrage plutôt que lancer un sous-ensemble invisible. Le démarrage peut facturer OpenAI. **Pour installer l'application Android avec l'aide de Codex : consulter le [guide opérationnel Windows + Android](docs/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md)**. Il couvre Tailscale Serve sur le PC, les secrets privés, le SDK Web Live2D, la PWA Chrome, le diagnostic et les tests réels.
