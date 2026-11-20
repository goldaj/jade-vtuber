# Dépenses OpenAI dans l’espace privé Jade

Le panneau **Suivi OpenAI** de l’application mobile affiche les dépenses API de l’organisation pour le jour et le mois en cours (UTC), par devise. Il indique l’heure de la dernière consultation ; OpenAI peut publier les coûts avec un délai. Les dépenses couvrent l’organisation, pas uniquement Jade. Le bouton Actualiser demande une nouvelle consultation, au plus une fois toutes les 30 secondes ; une consultation ordinaire est mise en cache 5 minutes. En cas d’erreur, la dernière valeur connue est conservée et signalée.

Le solde prépayé restant n’est pas disponible via cette intégration : aucune alerte sur seuil de solde ne peut donc être déclenchée. Il faut le consulter dans la [facturation OpenAI](https://platform.openai.com/settings/organization/billing/overview). Le montant dépensé ne permet pas de déduire ce solde sans connaître les paiements, crédits et ajustements.

## Configuration

1. Dans l’organisation OpenAI utilisée par Jade, créer une clé d’administration disposant de l’accès aux coûts. Cette clé est distincte de la clé API habituelle et exige les droits administrateur de l’organisation.
2. Sur le PC de Jade uniquement, ajouter `JADE_OPENAI_ADMIN_KEY` au fichier d’environnement privé utilisé pour son lancement ; ne pas la mettre dans le dépôt ou sur le téléphone. Redémarrer Jade pour charger la variable.
3. Dans l’application mobile privée, ouvrir **Suivi OpenAI**. Si le panneau indique un accès refusé, vérifier l’organisation et les droits de la clé ; sans clé, les autres fonctions restent disponibles.

Les requêtes utilisent le point officiel [Costs de l’API d’administration](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs). La clé reste côté PC ; l’accès mobile conserve les contrôles Tailscale et jeton de l’application.
