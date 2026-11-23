# Pilotage distant PyCharm Run et démarrage automatique Windows

**Statut :** implémentation expérimentale sur la branche feat/jade-pycharm-remote-control-20261123 ; pas de merge vers develop et aucune recette physique PC/Android revendiquée.

## Architecture

- Une seule instance Jade : la configuration PyCharm « Jade - Discord mobile (test) » appelle toujours tools/jade_pycharm_runner.py, lequel garde la session Run ouverte, mais démarre le moteur en processus enfant avec les mêmes options Discord et mobile. Les points d'arrêt Debug dans le moteur ne sont plus conservés.
- Le parent écoute uniquement sur 127.0.0.1:8772, authentifié par JADE_DEPLOY_SUPERVISOR_TOKEN. Le redémarrage se fait dans la même session Run de PyCharm. Sous Windows, un Job Object rattache le moteur au parent pour éviter les orphelins après fermeture brutale de PyCharm.
- Mise à jour : **develop seulement**, sans choix de branche dans l'application. Vérification dépôt propre et fast-forward, fetch avant arrêt, puis arrêt propre, merge fast-forward, git lfs pull et relancement. Aucun reset ni changement de branche. Si pyproject.toml ou poetry.lock change, le parent lance automatiquement une synchronisation Poetry après l'arrêt et avant la relance. Le succès du redémarrage est confirmé seulement après l'ouverture de la passerelle mobile ; pas de rollback automatique garanti si migration SQLite.
- Les sorties standard de Jade sont dupliquées dans PyCharm et dans le fichier privé jade-pycharm-console.log, avec rotation. Les journaux détaillés par session existants restent disponibles.
- Un contrôleur indépendant écoute sur 127.0.0.1:8771. Il propose statut, logs et deux commandes strictes. Avec Tailscale Serve, il est disponible à l'URL privée /control, même lorsque Jade est arrêtée. Il n'exécute pas de commandes shell transmises par le téléphone.
- Dans Profil, l'application Android affiche le statut PyCharm Run, le commit develop et les logs filtrables, avec deux boutons. L'ancienne route API de déploiement par branche n'est plus exposée par Jade.

## Installation prévue sur le PC

1. Sauvegarder les changements locaux. Vérifier l'absence de toute autre instance Jade, en particulier l'ancien superviseur autonome. Ne pas déclencher une mise à jour si Codex ou un autre agent travaille actuellement sur le checkout PyCharm.
2. Après validation et intégration du code, double-cliquer sur **Installer-Jade-Control.cmd** depuis le clone officiel, avec le venv Python/Poetry et la configuration privée déjà en place.
3. L'installateur place uniquement des chemins (aucun jeton) dans D:\Jade\control\control.json, enregistre une tâche utilisateur « Jade Remote Control » déclenchée **à l'ouverture de session Windows**, sans durée maximum, avec reprise après plantage, et crée le raccourci bureau Jade Control.lnk. Le processus est lancé par pythonw.exe, sans console visible. Un double-clic sur le raccourci le relance manuellement.
4. L'installateur tente également la route privée Tailscale Serve /control vers 127.0.0.1:8771, sans supprimer la route / de la PWA actuelle. **Sous Windows, la commande Tailscale peut exiger un terminal administrateur** ; si l'opération échoue, l'installateur l'annonce. Ne pas utiliser Funnel.
5. Vérifier la tâche Windows (« En cours »), le port 8771 et la route HTTPS Tailscale. Sur le téléphone, ouvrir l'URL Tailscale existante suivie de /control ; saisir le même jeton que dans Jade. La page indépendante est accessible même si le moteur Jade est fermé.
6. Dans PyCharm, utiliser **Run**, et non Debug, sur « Jade - Discord mobile (test) ». Vérifier qu'après un redémarrage mobile la même console Run est toujours ouverte, que le nouveau PID correspond à un seul moteur et que les logs y continuent.
7. Tester redémarrage sans mise à jour, mise à jour fast-forward develop, erreur Git, arrêt propre, crash, accès aux logs quand Jade est éteinte, verrouillage de session Windows et reconnexion complète. Un arrêt explicite de session Windows arrête les processus utilisateur ; le contrôleur revient à l'ouverture suivante.

## Limites importantes

- **Recette avant merge :** le profil Run exige develop par défaut. Pour tester cette branche isolée sans l'intégrer, sélectionner localement feat/jade-pycharm-remote-control-20261123 dans PyCharm, définir temporairement JADE_PYCHARM_TEST_BRANCH=feat/jade-pycharm-remote-control-20261123 dans l'environnement Run puis lancer normalement. Le bouton « Mettre à jour develop » reste désactivé sur cette branche, mais le redémarrage et les logs peuvent être éprouvés. Supprimer la variable après la recette et revenir sur develop. Ne jamais lancer deux instances simultanément.
- Le contrôleur ne démarre pas Jade lui-même ; il exige la session Run PyCharm. Cliquer sur le raccourci ne crée aucune connexion IA/Discord.
- Le filtre de secrets sur les logs est imparfait : l'accès doit rester privé et les journaux ne doivent jamais être publiés.
- Une mise à jour qui change profondément les dépendances Python, les assets ou le schéma de données peut encore exiger une intervention locale si la synchronisation échoue. La procédure ne promet pas de rollback automatique.
- La recette PC, Android, Tailscale, PowerShell, PyCharm et la santé réelle des connecteurs reste à réaliser avant toute validation fonctionnelle.

## Désinstallation du contrôleur

Exécuter `scripts/uninstall-jade-control.ps1` depuis PowerShell. Le script arrête/supprime la tâche planifiée et supprime le raccourci bureau créé par l'installateur. Le dépôt, les logs et les secrets ne sont pas supprimés ; inspecter séparément `tailscale serve status` avant de retirer une route `/control` éventuellement partagée.
