# Jade : conversation Discord unifiée (15 novembre 2026)

## Statut courant sur develop

**Intégré au runtime** : les conversations du même compte Discord entre vocal et **chat natif de ce même vocal** partagent une clé `conversation_id` liée à la session autorisée. Cette page décrit le comportement existant et les extensions possibles ; les mentions de PR empilées du 15 novembre sont historiques.

## Comportement développé
- Un même interlocuteur **authentifié par son compte Discord** et participant au vocal actif partage une histoire courte entre vocal et **chat textuel natif du même salon vocal**. Il n'est pas suffisant d'avoir un pseudo identique.
- Les écritures textuelles non sélectionnées par la politique des 30 % sont ajoutées à l'historique *seulement* si le compte est encore dans le vocal autorisé et si le chat est celui du même salon. Aucun appel LLM supplémentaire. Les réponses textuelles continuent d'obéir à la politique existante.
- `Incoming.session` reste le **transport** (donc les permissions Discord, le dédoublonnage et le routage audio sont inchangés), `history_key` désigne la conversation logique. La clé opaque SHA-256 inclut serveur, salon vocal, identifiant de session vocal aléatoire et compte Discord. Elle change à toute reconnexion.
- Les messages mémorisés par SQLite restent limités à leurs scopes d'origine ; pas de mélange entre souvenir durable, conversation active, identité et historique technique.
- DMs, salon textuel différent, autre serveur, autre personne, session révoquée et usagers absents du vocal : **aucune fusion**. Pas de route automatique par horodatage seul.
- La session d'historique volatile conserve la borne et l'expiration de `Dialogue` (1800 secondes par défaut). Les échanges passifs écrits sont gardés sans audio ni persistance.

## Limites honnêtes
- Les salons texte `#general` distincts du vocal ne sont pas fusionnés, même si un humain les appelle « associés ». Il faudra une association explicite et une vérification de confidentialité avant d'étendre cette règle.
- La politique de choix des médias de sortie n'a **pas** été remplacée : une réponse à un écrit peut déjà déclencher le TTS existant si activé ; une réponse à une parole reste orale.
- L'horodatage cross-media et l'ordonnancement STT simultané ne sont pas totalement déterministes dans cette V1. Les interactions déjà traitées sont sérialisées par la queue Runtime, pas réordonnées après coup.
- La **session volatile commune** ne survit pas au redémarrage ; les échanges complets **persistés par identité opt-in et scope** restent dans SQLite v3 et peuvent être restaurés dans leur périmètre. La fusion des salons distincts n'existe pas.
- Le même chat natif peut être lisible par d'autres détenteurs du droit d'accès au salon. Aucune fusion entre canaux aux permissions différentes n'est autorisée par ce lot.

## Scénarios de contrôle du comportement existant
1. Utiliser le HEAD de develop et vérifier les cas de confidentialité avec les tests Discord correspondants.
2. En vocal, envoyer dans le **chat du vocal** « Le personnage s'appelle Akira » puis demander oralement « Comment s'appelle le personnage ? » sans répéter son nom.
3. Tester autre participant, membre sorti du vocal, reconnexion, changement de salon, DM, deux messages quasi simultanés, absence de doublon.
4. Vérifier que les sorties Discord écrites et audio restent envoyées à leur destination habituelle et que la mémoire SQLite ne récupère pas un DM dans le vocal.
5. Recetter sur le matériel de Goldaj et relever latence/usage OpenAI. Aucun résultat de cette recette n'est revendiqué ici.

## Suite
La table autobiographique `jade_self_core` **owner_only** est intégrée. Une autobiographie globale accessible au public demeure une nouvelle évolution nécessitant un contrôle de visibilité. Les enregistrements globaux ne doivent contenir aucune donnée privée de tiers récupérée à travers le chat d'un canal.
