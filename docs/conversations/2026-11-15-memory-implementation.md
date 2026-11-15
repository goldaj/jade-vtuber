# Développement de la mémoire Jade et précisions d'architecture (15 novembre 2026)

**Demande utilisateur (résumé fidèle) :** créer une PR séparée et coder les éléments réalisables à distance du système de mémoire persistante/personnes/Core Memories, choisir SQLite ou MongoDB selon pertinence, documenter les choix et la passation Codex. Le propriétaire insiste sur une base facilement migrable lors du remplacement de son PC.

**Précision utilisateur, verbatim :** « Petite info sur le microphone local, ça sera toujours moi, son créateur et son père, Goldaj, qui parlera. Personne d'autre n'utilise le microphone local. Elle pourra toujours considérer que c'est moi. Intègre ça là où il faut dans le code ».

**Idée utilisateur réservée à Codex, résumé :** Jade devra reconnaître qu'elle discute simultanément à l'oral et à l'écrit sur Discord avec un même compte, et unifier le contexte conversationnel grâce notamment aux horodatages. L'utilisateur a expressément demandé de **documenter l'idée sans la coder pour le moment**, puis de poursuivre prioritairement le chantier de mémoire déjà engagé.

**Actions de l'assistant :** branche de développement indépendante `feat/jade-persistent-memory-core-20261115` vers `develop`, SQLite local opt-in, identité stable, règle micro Goldaj, curateur de souvenirs asynchrone optionnel, export/import portable, tests hors ligne et passation à Codex. La fusion temps réel des historiques Discord texte/vocal demeure une **idée documentée uniquement**.

**Références :**
- [Passation du développement mémoire pour Codex](../gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md)
- [Concept de conversation Discord unifiée pour Codex](../gpt6-jade/IDEE-CONVERSATION-UNIFIEE-20261115.md)
- [Plan produit antérieur de mémoire persistante](../gpt6-jade/PLAN-MEMOIRE-PERSISTANTE-IDENTITES-CORE-20261115.md)

Ne pas considérer cette note comme une recette sur le poste local, un test matériel, ou une transcription intégrale du chat. Ne jamais y publier de journaux réels ou de fichiers de mémoire.
