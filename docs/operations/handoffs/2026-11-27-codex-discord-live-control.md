# Commande du Live Discord et indicateurs mobiles

- Branche `fix/discord-live-control-20261127`, depuis `develop@919ecaf`. Recettes concernées REC-049, REC-050 et REC-051. REC-028 est classée sans suite après le retrait décidé par le propriétaire.
- Le traitement d’une arrivée dans le salon continue de mettre à jour la présence et la mémoire. Il ne lance plus de demande de bienvenue. La sortie Discord accepte l’audio du moteur qui détient la session, du début de l’ouverture à la libération de la lecture. La bascule ne rejoue pas un énoncé déjà envoyé.
- **Config → Suivi Discord** lit les minutes observées de GPT-Live sur Discord pour le mois Europe/Paris. Le serveur déduplique les compteurs cumulatifs de durée et les conserve indépendamment de la réconciliation financière. Un relevé incomplet est signalé. L’activation est enregistrée dans la base privée, avec ON par défaut. OFF retire l’admission et ferme la session en cours. ON réapplique les seuils, le verrou mensuel et la disponibilité courante.
- L’indicateur mobile montre le rouge dès la parole captée ou la lecture de la réponse, même si le fournisseur signale encore la veille. La coupure ramène la couleur au bleu. Les états sont envoyés à l’interface sur changement de l’activité, sans rendu supplémentaire à chaque trame audio.
- Les tests hors réseau exercent l’arrivée en vocal, la propriété de la sortie, la bascule et le compteur Discord, l’accès au panneau et deux tours mobiles dans la même session. Recette sur téléphone et Discord réels à mener avec une réponse en cours lors du passage OFF, puis une nouvelle phrase après réactivation.

## Échanges accessibles

- **Propriétaire** (synthèse du 27 novembre) Demande le retrait du salut Discord classique lorsqu’un membre rejoint, un moteur unique par session, une mesure des minutes et une case de désactivation de GPT-Live sur Discord. Signale que les indicateurs mobiles restent bleus au deuxième échange malgré une conversation audible. Approuve la réalisation et la publication sur `develop`.
- **Assistant** (synthèse) Identifie le trajet de bienvenue qui contourne l’arbitrage et propose le mois Europe/Paris pour le compteur. Corrige l’indicateur à partir de la parole captée et de la lecture distante. Les heures individuelles ne sont pas disponibles.

[Architecture Discord](../../architecture/DISCORD_LIVE.md) · [Guide utilisateur](../../handbook/USER_GUIDE.md) · [Recettes](../../backlog/02-RECETTE.md)
