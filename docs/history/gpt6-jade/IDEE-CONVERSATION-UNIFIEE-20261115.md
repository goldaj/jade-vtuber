# Conversation Discord unifiée — conception d'origine et extensions

**Code actuel dans develop :** un même compte partage déjà son historique volatil entre **vocal et chat textuel natif du même salon vocal**, tant que la session est ouverte et autorisée. Sources : `discord_text.py`, `discord_voice.py`, `messages.py`.

## Scénario de référence

Alice parle de son roman dans le vocal de Jade, écrit un titre dans **le chat natif de ce vocal**, puis reprend à l'oral. Jade dispose de ce texte dans la conversation logique commune, même si le message écrit ne déclenche pas une réponse. Les autres salons, DM et comptes ne sont **jamais** fusionnés implicitement.

## Pistes futures, non codées

- Étendre la conversation à un salon textuel **distinct** seulement si l'association des salons et leurs permissions sont explicites, vérifiables et maintenues.
- Mettre en place un `ConversationManager` pour ordonner des événements audio STT et texte presque simultanés, sans reconstruire de faux ordre chronologique.
- Préserver les identités fiables, le consentement, l'isolation des MP et l'annulation lors d'une déconnexion/changement de session.
- Conserver le texte passive seulement dans le contexte autorisé ; ne pas transformer tout message en souvenir durable.

Ces évolutions figurent dans [MEM-13 et le catalogue](../ameliorations/02-MEMOIRE-PRESENCE.md). Le présent fichier n'est plus une instruction de créer à nouveau le partage vocal/chat déjà implémenté.
