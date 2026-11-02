# Configuration privée

Le dépôt de Jade ne doit contenir aucun secret. Les clés API, jetons et mots de passe sont conservés dans une configuration séparée. Le fichier `.env.example` documente les noms des variables sans contenir leurs valeurs.

Pour utiliser une configuration privée, définir `JADE_SECRETS_FILE` avec le chemin du fichier sur le poste. Les variables d’environnement du processus prennent priorité sur ce fichier. Si aucune configuration externe n’est sélectionnée, le chargeur peut aussi utiliser un fichier `.env` local ignoré par Git. Ne jamais ajouter ce fichier au dépôt, aux journaux, aux captures ou aux messages.

Les jetons Twitch actualisés sont enregistrés dans le fichier privé sélectionné, sans modifier le code versionné. Les valeurs de configuration ne doivent pas être imprimées par les diagnostics.

Une sauvegarde des informations privées peut être conservée séparément dans un emplacement privé contrôlé par le propriétaire. Le choix du propriétaire concernant les identifiants existants est documenté dans l’index des conversations ; les échanges historiques ne doivent jamais inclure leurs valeurs.

Avant tout partage ou changement du dépôt, contrôler les fichiers suivis et les éventuelles ressources binaires. Un scanner automatise une partie de ce contrôle, mais ne garantit pas à lui seul l’absence de données sensibles.
