# Jade — un personnage virtuel capable de dialoguer

Jade est un projet expérimental de VTuber IA : un personnage 2D conçu pour
interagir par texte et par voix. Ce dépôt présente le moteur Python qui reçoit
les messages, prépare une réponse et peut la transmettre à des outils de
streaming. Le travail sur le personnage et son animation est mené séparément.

> **État : prototype en cours de développement.** Le mode de démonstration
> fonctionne hors ligne. Les connexions aux plateformes et les appareils audio
> demandent encore une validation réelle. Cette version est un aperçu privé à
> relire avant toute publication.

## Ce que fait le moteur

- Reçoit du texte depuis une console et propose des connecteurs optionnels
  pour Twitch, Discord et une interface HTTP locale.
- Met les demandes dans une file bornée, maintient un historique limité par
  conversation et produit des réponses via une interface de dialogue modulaire.
- Utilise **OpenAI exclusivement pour la transcription et la synthèse vocale** ;
  le modèle de dialogue OpenAI est configurable. Une réponse de démonstration
  remplace l’appel réseau en mode hors ligne.
- Prépare la lecture vocale, les sous-titres OBS et les interactions avec l’API
  locale de VTube Studio. Ces intégrations sont désactivées par défaut.

```text
Console / Twitch / Discord / HTTP ─────────┐
Microphone → transcription OpenAI ─────────┤
                                           ↓
                                  File → Dialogue
                                           ↓
                   Texte / synthèse vocale / sous-titres
```

Le dialogue dispose d’une interface backend interchangeable dans le code ; seul
le backend OpenAI et le backend de démonstration sont fournis actuellement.

## Essayer la démo sans clé API

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
| Chaîne micro → STT → dialogue → TTS | Testée avec audio synthétique et services simulés ; micro et API vocales réels à vérifier |
| Twitch, Discord et Discord vocal | Connecteurs et tests simulés ; comptes, permissions et audio réel à vérifier. Discord vocal est expérimental |
| Sous-titres et VTube Studio | Interfaces et tests simulés ; configuration OBS et interactions VTube Studio réelles à vérifier |
| Personnage 2D | Visuel et animation en cours ; aucun asset 2D n’est inclus dans cet aperçu de code |

La simulation vérifie des comportements logiciels et ne remplace pas un essai
matériel, une recette de diffusion ou une mesure de latence et de coût.

## Options et configuration privée

Le modèle, les connecteurs et les limites se configurent par environnement ou
par fichier privé sélectionné avec `JADE_SECRETS_FILE`. Les réglages non secrets
peuvent utiliser un profil de `config/profiles/`. Le prompt du personnage peut
être fourni séparément via `JADE_PROMPT_FILE` ou `JADE_ASSETS_ROOT` ; le prompt
inclus dans cet aperçu est un exemple générique.

Le passage en mode réel exige explicitement `--live`, une configuration valide
et peut générer des frais. Le microphone, Twitch, Discord, VTube Studio et
l’interface HTTP s’activent séparément par leurs options ; l’envoi vers les
chats Twitch/Discord demande en plus son réglage dédié. Les extras Poetry
disponibles sont `mic`, `discord`, `discord-voice` et `vts`.

La lecture locale nécessite ffplay. Avant un essai vocal, vérifier les appareils
et avertir les participants : les segments vocaux destinés à la transcription
sont envoyés au fournisseur. L’interface HTTP reste liée à `127.0.0.1` ; un accès
depuis un autre appareil nécessite une solution sécurisée distincte.

Ne pas committer de clé API, jeton, enregistrement ou transcription privée.
