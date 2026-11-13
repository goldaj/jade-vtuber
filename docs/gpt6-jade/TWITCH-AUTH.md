# Autorisation Twitch initiale

La connexion IRC utilise un jeton utilisateur Twitch, avec `chat:read` pour lire
le chat et `chat:edit` seulement si l'envoi de messages est explicitement activé.
Le démarrage Twitch vérifie le jeton existant, ses permissions et son compte sans
le renouveler, puis déduit le nom de connexion si nécessaire.

Les jetons Twitch précédemment sauvegardés ont répondu non valides à la validation
réelle. Il faut une nouvelle autorisation pour effectuer une connexion réelle ;
aucun jeton existant n'est modifié automatiquement. Ce parcours ne doit être
exécuté que lorsque le propriétaire souhaite effectivement créer de nouveaux
identifiants. Il s'appuie sur le [flux officiel Twitch Device Code](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#device-code-grant-flow).

1. Configurer une application Twitch compatible et placer son identifiant dans
   `TWITCH_CLIENT_ID` de la configuration privée existante. L'application doit
   être compatible avec le flux device ; si Twitch la refuse, vérifier son type
   et sa configuration dans la console développeur.
2. Choisir un **nouveau** fichier dans un dossier privé existant, hors de tout
   dépôt Git. Dans un terminal local, exécuter par exemple :

   ```powershell
   poetry run python tools/jade_twitch_authorize.py --output D:\Codex\private\jade-20261102\twitch-nouveau.env
   ```

   Ajouter `--allow-send` uniquement si Jade doit aussi envoyer des messages.
   L'outil crée le fichier de manière exclusive, avec des permissions privées ;
   il refuse d'écraser un fichier existant et ne remplace aucune configuration.
3. Ouvrir l'adresse Twitch indiquée et entrer le code temporaire. Le terminal
   n'affiche ni jeton, ni identifiant client, ni réponse complète du serveur.
4. Le nouveau fichier ne contient que les réglages Twitch. Après vérification,
   recopier ses valeurs vers la configuration privée complète choisie par le
   propriétaire, sans les coller dans un chat ni dans le dépôt public. Le fichier
   initial contenant les autres clés reste nécessaire ; ne pas simplement le
   remplacer par le fichier Twitch partiel.
5. Tester la connexion en lecture avant tout envoi. Une fois la configuration
   privée mise à jour, mettre à jour aussi sa sauvegarde dans le dépôt GitHub
   **privé** dédié : cette sauvegarde n'est pas synchronisée automatiquement.

Le flux et les tests automatisés sont séparés : les tests utilisent des réponses
simulées et ne créent aucun jeton. L'autorisation interactive réelle requiert la
présence du propriétaire.

## Renouvellement et sauvegarde privée

Le renouvellement automatique est facultatif : `JADE_TWITCH_AUTO_REFRESH=1` le
demande pour une connexion Twitch explicitement activée. Il vérifie le jeton au
démarrage et au moins toutes les heures. Les permissions et le compte sont
contrôlés ; les jetons ne sont jamais affichés. Le fonctionnement manuel reste
possible en laissant ce réglage à `0`.

Pour l'activer, utiliser un fichier privé complet sélectionné par
`JADE_SECRETS_FILE`, hors de Git, et y définir `JADE_BACKUP_REPOSITORY` (nom
`propriétaire/dépôt` du dépôt privé), `JADE_BACKUP_REPOSITORY_ID` (identifiant
numérique vérifié sur GitHub) et `JADE_BACKUP_FILE` (nom du fichier actif dans
ce dépôt). Le fichier correspondant doit déjà exister à l'identique dans la
branche `main` du dépôt privé. GitHub CLI doit être installé et authentifié avec
accès à ce seul dépôt. Initialiser la référence de sauvegarde par un appel local
à `sync_private_backup` avant le premier renouvellement ; aucune valeur ne doit
être copiée dans le dépôt public ou dans une discussion.

Avant chaque rotation, Jade vérifie l'identité et la confidentialité du dépôt et
la version sauvegardée. Elle écrit la nouvelle paire localement avant de la
sauvegarder ; si la sauvegarde échoue ou si l'état distant a changé, un avertissement
est émis et aucune nouvelle rotation ne sera tentée avant synchronisation. Un
résultat Twitch ambigu laisse un marqueur de récupération et bloque les nouveaux
essais : ne pas le supprimer sans examiner la configuration privée.

Une panne entre la réponse Twitch et l'écriture locale peut tout de même imposer
une nouvelle autorisation. GitHub et le disque ne forment pas une transaction
unique ; la confidentialité du dépôt doit rester sous le contrôle du propriétaire.
La mise à jour par API crée des commits distants : avant de modifier une copie Git
locale de la sauvegarde, vérifier qu'elle est propre puis la mettre à jour en
avance rapide. Les tests automatisés du renouvellement utilisent des fournisseurs
simulés ; aucun renouvellement réel n'est lancé par les tests.
