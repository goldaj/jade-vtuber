# Reprise du Live mobile après une fermeture non confirmée

- Branche `fix/mobile-live-closure-recovery-20261127`, depuis `develop@8e6eacc`. Recettes concernées REC-044, REC-045 et REC-050.
- Le registre local et le point d’accès privé ont confirmé une session mobile connue en `close_unconfirmed` après une désactivation. Elle était la seule ligne sans terminal. La préférence était bien Live. Une tentative d’attachement à cette ancienne session a reçu HTTP 503. Le bouton Réessayer lisait la disponibilité et gardait le blocage du micro.
- Lors d’une fermeture en cours, le client rafraîchit l’état pendant un temps borné. Si l’ancienne session connue a perdu son bail, a été invalidée et que la tentative de fermeture est terminée, une demande explicite peut la retirer du parcours actif. L’usage final reste indéterminé et l’historique reste durable. Les anciennes générations ne peuvent pas interrompre la suivante. Une création ambiguë sans identifiant reste bloquante.
- Le retrait n’arme pas le micro et ne crée pas de session fournisseur. L’utilisateur reprend avec un appui sur le micro après le retour de disponibilité. [Récupération après perte de connexion GPT-Live](https://developers.openai.com/api/docs/guides/live-conversations#recover-from-a-failed-connection)

## Échanges accessibles

- **Propriétaire** (signalement du 27 novembre) La case Mode Live se laisse difficilement activer et l’appui sur le micro semble sans effet. Les captures affichent le message de fermeture précédente et une scène avec le mode Live sélectionné.
- **Assistant** (synthèse) Vérifie le registre et la disponibilité via le service privé. Le diagnostic porte sur la fermeture de session. L’enregistrement ne reprend qu’après une action distincte.

Les heures individuelles de la conversation ne sont pas disponibles. Les vérifications sont consignées sans identifiants de session ni contenu de conversation.
