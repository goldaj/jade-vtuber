# Expérience produit, client mobile et poste local

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| UX-10 | P2 / P | Panne réseau/mobile : affichage d'indisponibilité, reconnexion sans double génération payante, reprise du contexte autorisé, annulation lorsque client quitte l'écran. |
| UX-14 | P3 / D | Étudier un client mobile plus riche ou natif seulement après validation PWA, dépendances SDK Live2D et comparaison latence/batterie ; ne pas créer un APK par principe. |
| UX-17 | P1 / P | **Connexion mobile autonome par application Authenticator** : remplacer, dans l'interface propriétaire PWA, la nécessité de récupérer/coller manuellement le jeton privé depuis le PC par un parcours d'authentification compatible Google/Microsoft Authenticator (TOTP standard ou alternative équivalente étudiée), avec enrôlement initial sécurisé, code de secours/récupération, protection anti-bruteforce et révocation. Après connexion, conserver une session mobile sécurisée renouvelable pour ne pas ressaisir un code à chaque lancement ; ne jamais stocker ni afficher de secret longue durée en clair dans le client, les logs ou le dépôt. Préserver l'accès privé Tailscale Serve et l'authentification des API non interactives si nécessaires. Recetter reconnexion, expiration, perte du téléphone, nouveau navigateur et usage en réseau mobile. |
| UX-18 | P1 / P | **Compléter le suivi de crédit API OpenAI de la PWA :** l'affichage des dépenses organisationnelles et de leur actualisation existe déjà ; la **valeur exacte du crédit prépayé** reste indisponible tant qu'aucune source officielle autorisée ne la fournit. Prévoir si possible un indicateur exact clairement identifié, une alerte seuil de crédit bas configurable et une distinction solde/budget/dépenses ; si impossible, afficher explicitement « solde indisponible » sans inventer un solde ni scraper la console. Accès uniquement via le backend privé/authentifié, cache raisonnable et aucune nouvelle dépense API superflue. |


**UX-19 a été transférée dans la backlog en [DEV-032](../backlog/01-DEVELOPPEMENT.md) au statut « À qualifier ».** La génération et la transmission de fichiers téléchargeables depuis la PWA restent entièrement à cadrer avec le propriétaire ; aucun développement autorisé pour le moment.

**État consolidé (22/11/2026) :** le rendu Live2D Android r20 est développé et accepté (DEV-002, REC-019) et une première chambre animée est intégrée. Le défaut précis de fenêtre/rideau est suivi dans **DEV-010** ; aucune seconde idée « recréer le décor complet » n'est entretenue ici. La connexion mobile autonome via Authenticator **UX-17** reste à concevoir. Le PC peut rester hébergeur allumé ; Authenticator ne rend pas Jade disponible si le processus est arrêté.

### UX-18 — solde prépayé indisponible

Les coûts d'usage existants sont suivis dans le backend ; seule l'obtention autorisée d'un **solde prépayé exact** et l'alerte de seuil restent prospectives. Aucun montant estimé ne doit être présenté comme un solde réel.
