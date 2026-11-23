# Tester Jade dans PyCharm sur le PC Windows

Ces configurations servent aux tests et au débogage ; le lancement autonome existant reste la méthode de production. Ne lancer qu'une seule instance de Jade à la fois : fermer la production avant un test PyCharm, et inversement.

1. Ouvrir dans PyCharm le clone officiel `D:\Codex\projects\jade-officiel-public-20261102`, sur `develop`. Les configurations visent l'interpréteur `D:\Codex\caches\venvs\jade-runtime-d-20261114\Scripts\python.exe` ; si PyCharm ne le reconnaît pas, l'ajouter comme interpréteur existant dans les paramètres du projet et le sélectionner.
2. Choisir **Jade - verification locale (sans connexion)** et cliquer sur Exécuter. Le préflight vérifie les dépendances et la configuration, sans appel réseau ni connexion Discord. Il utilise le même verrou que la production.
3. Pour l'essai réel, arrêter toute instance Jade, puis choisir **Jade - Discord mobile (test)** et Exécuter ou Déboguer. L'onglet Run/Debug affiche la conversation et les messages techniques ; les points d'arrêt fonctionnent dans le processus principal. Un onglet **Jade - erreurs** est prévu pour les avertissements/erreurs Python dans `D:\Codex\private\jade-runtime\logs\jade-pycharm-diagnostics.log`. Ces essais utilisent Discord et OpenAI et peuvent facturer les appels.
4. Arrêter l'exécution avec le bouton Stop de PyCharm avant de relancer la production autonome.

Le lanceur [jade_pycharm_runner.py](../../../tools/jade_pycharm_runner.py) retrouve uniquement sur ce PC les fichiers privés déjà utilisés par le lanceur autonome pour les identifiants, Tailscale et le mobile. Aucun mot de passe ni jeton ne figure dans les configurations `.run`. Si les fichiers privés ont changé d'emplacement, configurer localement `JADE_SECRETS_FILE` et/ou `JADE_PYCHARM_PRIVATE_DIR` dans la configuration personnelle PyCharm, sans enregistrer de secret dans le projet. `JADE_FFMPEG_DIR`, `JADE_TAILSCALE_DIR` et `JADE_MOBILE_VENDOR_DIR` permettent aussi d'adapter les dossiers installés.

Les configurations partagées ont été préparées pour le format Python de PyCharm ; leur reconnaissance par la version installée doit encore être vérifiée dans l'interface. Le mutex et le contrôle des anciens processus protègent les méthodes de lancement connues, sans garantir la détection d'un programme tiers lancé avec des arguments différents.

Le journal technique est limité à trois fichiers d'environ 5 Mo et exclut les événements du logger de conversation ; les exceptions peuvent néanmoins contenir des informations sensibles. Il n'intercepte pas les sorties natives qui n'utilisent pas le module Python `logging` ; elles restent visibles dans la console Run/Debug. Si l'onglet dédié n'apparaît pas sur PyCharm 2022.3, l'ajouter dans les options de logs de la configuration en indiquant le chemin ci-dessus.


## Changement expérimental du 23 novembre 2026 (hors develop)

Sur la branche feat/jade-pycharm-remote-control-20261123, le profil PyCharm « Jade - Discord mobile (test) » ouvre une session Run **persistante** propriétaire du moteur. Le moteur est exécuté comme enfant de cette session et peut être relancé par le contrôleur Windows depuis Android, mais le débogage Python direct de cet enfant n'est plus disponible. Le profil préflight reste indépendant.

Le contrôleur est lancé par une tâche utilisateur au logon Windows via pythonw.exe, sans console, avec raccourci manuel. Son port privé 8771 et la route Tailscale /control restent accessibles même si Jade est en cours de redémarrage. L'ancien superviseur de clone distinct n'est plus utilisé depuis l'application. [Procédure complète](REMOTE-PYCHARM-CONTROL-20261123.md). **Tests PC à réaliser avant merge.**
