# DEV-036 — Transfert de NEW-16 : rappels et notifications (22 novembre 2026)

## Décision du propriétaire
Déplacer **NEW-16 (P2)** du catalogue actif des idées vers la backlog de développement **DEV-036 (P2, À qualifier)**. Ne pas commencer l'implémentation. L'ancienne identité NEW-16 reste une référence historique, sans deuxième carte active.

## Périmètre repris sans préjuger du cadrage
- Enregistrer un événement ou un rappel demandé explicitement, avec objet, échéance, fuseau horaire, destinataire et portée autorisée.
- Émettre le rappel au bon moment sur le MP ou salon Discord expressément autorisé ; étudier les notifications mobiles consenties sans garantir une livraison lorsque l'appareil est hors ligne ou l'application fermée.
- Pouvoir retrouver, modifier et annuler un rappel, gérer redémarrages, échéances manquées, répétitions et état d'envoi, sans doublon.
- Pas de boucle LLM permanente ni de nouvel appel IA payant nécessaire pour livrer une notification simple ; aucune diffusion dans un autre canal. Distinct de REC-028.

## Points à qualifier avant développement
- Calendrier interne à Jade ou synchronisation avec un fournisseur externe (Google Calendar/Outlook) : seul le premier a été recommandé lors de l'échange, **aucune décision arrêtée**.
- Rappels uniques ou récurrents ; politique de rappel des événements manqués.
- Qui peut programmer, pour qui et sur quel canal ; permission d'utiliser des notifications mobiles.
- Robustesse et test réel du mécanisme de notification mobile selon navigateur, OS et permissions.

## Exécution et contrôle
**Branche :** `develop`. **Action :** documentation et backlog uniquement ; aucun code, test de fonctionnement, changement de configuration privée ni déploiement effectué. Une seule carte active DEV-036. La recette finale de DEV-032 / REC-039 reste Done et n'est pas réouverte par cette demande.
