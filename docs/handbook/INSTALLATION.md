# Installation complète depuis un poste vierge : branche feat/turn-conversation-logs-20261115

**Branche divergente : feat/turn-conversation-logs-20261115.** Journalisation des tours de conversation (messages, intentions et modalités de réponse), avec module turn_logging.py, adaptation de l'orchestrateur et tests de journalisation. Les dix commits propres recensés face à develop demandent une revue de contenu avant suppression. Pas de PWA mobile, de mémoire SQLite ou de launcher unifié. Les guides sont spécifiques à cette branche et ne doivent pas être confondus avec ceux de develop.

## Préalable : choisir le bon parcours

- **Découvrir Jade sans prérequis externes (Windows 10/11) :** utiliser la [Démo Express](DEMO.md). C'est une simulation hors ligne.
- **Développer/essayer le vrai moteur modulaire :** installer Python 3.11, Poetry 2.2.1 et Git. Aucune clé API nécessaire pour la démo console hors ligne.
- **Exécuter la véritable IA, la voix ou un connecteur :** configurer le service concerné et une clé OpenAI. Ces appels peuvent être facturés.
- **Voir le modèle Live2D r20 :** Git LFS, carte graphique/pilote, modèle et extras d'avatar, puis validation physique.
- **Démo Windows animée installable existante :** voir `demo/reelle/GUIDE-DEMO.md` et `demo/reelle/README-BUILD.md`. Elle est distincte de la Démo Express.

La branche `feat/turn-conversation-logs-20261115` ne contient pas le launcher unifié `--all-channels` et la PWA Android privée de `develop`. Ne pas lancer ces commandes ici.

## Préparation d'une machine Windows neuve

1. Installer **Git for Windows** depuis git-scm.com et **Git LFS** depuis git-lfs.com. Exécuter `git lfs install`. Git LFS est surtout indispensable pour les ressources graphiques ; la simple console de simulation peut fonctionner sans télécharger les modèles.
2. Installer **Python 3.11 64 bits** depuis python.org. Vérifier dans PowerShell : `py -3.11 --version`. Installer une version récente de **Poetry**, la version CI de référence étant **2.2.1** : `py -3.11 -m pip install poetry==2.2.1` (ou l'installateur Poetry officiel). Vérifier `poetry --version` et son accès dans PATH.
3. Installer éventuellement **FFmpeg** et rendre `ffmpeg` et `ffplay` accessibles depuis PATH pour la voix, ainsi que les pilotes de capture audio. **Non requis** pour la démo console hors ligne.
4. Choisir un dossier de travail sans secrets, par exemple `D:\Jade\jade-vtuber` si D: existe, ou un emplacement utilisateur. Éviter de mélanger le dépôt public avec les fichiers privés.

~~~powershell
git clone https://github.com/goldaj/jade-vtuber.git
cd jade-vtuber
git switch feat/turn-conversation-logs-20261115
git lfs pull
poetry sync --only main
poetry run python main.py --preflight
poetry run python main.py
~~~

Écrire `Bonjour Jade` puis `/exit`. Le texte commencera par « Mode démo », **sans aucun appel OpenAI**. `git lfs pull` peut prendre du temps/du stockage et peut être omis pour la seule console.

### Linux et autres systèmes

La console Python est portable sur les systèmes où les dépendances sont disponibles. Installer Git, Python 3.11, Poetry et éventuellement Git LFS ; exécuter les mêmes commandes shell sans `py -3.11`. **L'installateur Démo Express Windows** dépend de Windows PowerShell 5.1 et WinForms et **n'est pas compatible Linux/macOS**. Les connecteurs GPU/audio et le Live2D exigent une validation propre à l'OS.

## Tests hors ligne après le clone

~~~powershell
poetry run python -m compileall -q src main.py
poetry run python -m unittest discover -s tests -v
poetry run python main.py --preflight
~~~

Ces contrôles ne requièrent ni token, ni serveur Discord, ni microphone. Ils ne prouvent pas qu'un pilote audio, une autorisation Twitch ou une session Live2D réelle marchent sur le PC.

## Activer un service réel (optionnel, opt-in)

Créer un fichier privé **hors Git** avec accès limité à l'utilisateur et configurer la variable `JADE_SECRETS_FILE` vers son chemin. Exemple Windows : `$env:JADE_SECRETS_FILE = 'D:\Jade\private\jade.env'`. Les variables d'environnement du processus priment sur ce fichier. Ne jamais placer les vrais secrets dans des commandes partagées, captures, logs ou commits. Voir `src/utility/private_config.py`, `src/jade_runtime/config.py` et [USER_GUIDE.md](USER_GUIDE.md).

La simple IA texte utilise `OPENAI_API_KEY` puis :

~~~powershell
poetry run python main.py --preflight --live
poetry run python main.py --live
~~~

Pour les canaux optionnels, installer d'abord les extras requis :

~~~powershell
poetry sync --only main -E all
poetry run python main.py --preflight --live --discord --voice --discord-voice
~~~

Cette dernière ligne est **un contrôle local**, pas une commande de lancement obligatoire : elle échouera tant que Discord vocal, ffmpeg, clés et salon ne sont pas configurés. Choisir **seulement** les canaux que l'on a réellement configurés, car `main` utilise encore des drapeaux explicites. Voir l'inventaire [USER_GUIDE.md](USER_GUIDE.md).

## Sécurité, coûts et dépannage

- Les connecteurs n'écoutent pas un port public automatiquement ; l'API HTTP locale est liée à `127.0.0.1`. Ne pas remplacer par un bind public pour dépanner.
- `--preflight` vérifie des dépendances et des formats **sans connexion aux fournisseurs**. `--live` autorise de vrais appels potentiellement facturés.
- Si `poetry` est introuvable, corriger son installation/PATH. Si `python` est incompatible, sélectionner Python 3.11 pour Poetry. Si le modèle Live2D manque, exécuter `git lfs pull` et `poetry run python jade-modeling/verify_assets.py`.
- Si l'authentification Discord/Twitch échoue, vérifier **hors journaux publics** les accès, autorisations et tokens exacts. Une connexion réelle ne se déduit jamais du simple préflight.
- Arrêter le moteur console par `/exit`; les connecteurs qui tournent sans console s'arrêtent avec `Ctrl+C`. Ne pas forcer le retrait des processus sans vérifier les données en cours.
