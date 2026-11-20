# Reconnexion du vocal Discord — 20 novembre 2026

- **REC-023** · Jade tournait encore après près de quatre heures, mais l'API Discord ne lui attribuait plus de salon vocal. Le serveur ne définit aucun salon AFK. Windows n'a signalé aucun événement de veille ou de reprise depuis le démarrage du processus. La cause de la coupure initiale reste inconnue.
- **Défaut logiciel** · La perte de l'état vocal propre du bot révoquait sa session audio. La reconnexion n'était lancée que lors du démarrage ou de la reprise de la connexion Discord principale. Une coupure limitée au vocal laissait donc Jade déconnectée.
- **Correction** · Quand le bot quitte le vocal et que la connexion principale est encore active, une seule tâche fait jusqu'à six tentatives espacées pour recréer la session. Les anciens tours sont invalidés. Une perte de la connexion principale ou l'arrêt de Jade annule la tâche. Une ligne technique sans contenu indique la reprise programmée.
- **Recette restante** · Observer une session de plusieurs heures et consigner la première coupure et les tentatives si elle se reproduit. La recette REC-023 reste ouverte.
