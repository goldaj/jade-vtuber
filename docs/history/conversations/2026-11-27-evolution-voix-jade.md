# Évolution de la voix de Jade

Extraits du chat accessible le 27 novembre 2026, avec rôles. Les heures individuelles et les enregistrements ne sont pas repris. Les réponses de l’assistant sont résumées. Les identifiants du projet et des voix, les liens privés et les résultats bruts des outils sont exclus.

- **Utilisateur** · Demande une voix GPT-Live créée à partir d’un prompt décrivant Jade, plusieurs essais ensemble et le développement après le choix.
- **Assistant** · Confirme le chemin de création OpenAI à partir d’une description et propose trois registres sur une même base vocale française.
- **Utilisateur** · Autorise les frais d’audition jusqu’à 1 USD si nécessaire, demande d’utiliser son navigateur Brave et rappelle que la voix doit parler français avec un accent français.
- **Assistant** · Crée Complice, Pétillante puis Posée avec le même texte d’essai. À la demande d’une direction plus aiguë et manga, crée Électrique. Rouvre ensuite uniquement Pétillante et Électrique à la demande du propriétaire.
- **Utilisateur** · Écarte la variante plus dynamique et demande de repartir du prompt de Pétillante.
- **Assistant** · Restitue le prompt initial de Pétillante, dont le registre d’origine était médium, légèrement plus haut.
- **Utilisateur** · Communique la consigne plus aiguë qu’il a saisie et demande « Tu peux valider ça et le mettre sur develop ? J'aimerais tester avec le modèle de Jade qui s'anime sur cette voix ».
- **Assistant** · Vérifie dans Brave que Pétillante reste la voix sélectionnée, que le nouveau texte figure dans la consigne de session et qu’une réplique a été transcrite lors d’une session de 21 secondes. Le test avec le modèle fait l’objet de la [passation opérationnelle](../../operations/handoffs/2026-11-27-codex-voix-petillante.md).
- **Utilisateur** · Précise que le lot consiste uniquement à appliquer la nouvelle Pétillante avec son prompt sur develop, le reste étant déjà réalisé.

## Nouvelle audition et choix de Friponne

- **Utilisateur** · Après avoir comparé Pétillante dans l’application et dans le Playground, confirme que la bonne voix est chargée mais apprécie peu le rendu. Demande des exemples de prompts pour une voix de personnage.
- **Assistant** · Recherche des exemples OpenAI et prépare deux nouvelles voix françaises, Légère et Ronde.
- **Utilisateur** · Préfère repartir de Pétillante et cite Ironmouse comme repère pour une voix originale. Il demande si des banques de voix existent et si une voix américaine peut parler avec un accent français de France.
- **Assistant** · Fait entendre dans Brave des essais de Pétillante, de Gleam et d’Aerisita, cette dernière provenant d’un catalogue extérieur à OpenAI.
- **Utilisateur** · Apprécie le timbre d’Aerisita mais perçoit un accent québécois. Il limite le projet aux API OpenAI et demande un registre plus aigu, davantage d’énergie et un accent de France.
- **Assistant** · Fait entendre Pétillante dans un registre plus aigu, puis Jade G · Friponne, une voix originale du Playground OpenAI, créée pour un registre parlé très haut et un phrasé francilien.
- **Utilisateur** (verbatim) · « ok on part sur friponne. Par contre il faut légèrement accélérer encore la vitesse de parole »
- **Assistant** (synthèse) · Retient la voix enregistrée et ajuste légèrement le débit des phrases. [Passation Friponne](../../operations/handoffs/2026-11-27-codex-voix-friponne.md)
- **Assistant** (synthèse) · Fait entendre le nouveau débit sur la même voix. La session de 25 secondes joue le passage jusqu’à la fin.
- **Utilisateur** (verbatim) · « ok pour la nouvelle friponne. On valide et on mets sur develop »
