# Passation Codex : mémoire persistante et Core Memories, lot distant (15 novembre 2026)

**État courant :** mémoire SQLite v3 et autobiographie intégrées sur `develop`. Cette passation conserve le contexte des PR historiques ; voir [l'état du code](../handbook/BRANCH_STATE.md) pour l'inventaire actuel.

## Arbitrage technique : SQLite plutôt que MongoDB

SQLite est un fichier portable, inclus dans Python, transactionnel et léger pour un seul processus Jade sur le PC. MongoDB imposerait un service, un processus de maintenance, des volumes et des sauvegardes supplémentaires alors que les profils, identités et souvenirs sont naturellement relationnels. Aucun serveur ni moteur vectoriel, aucun coût d'hébergement.

Les tableaux sont dans `src/jade_runtime/memory_store.py` : profils opt-in, correspondances de comptes Discord/Twitch, souvenirs ordinaires avec expiration et Core Memories sans TTL, dédoublonnage, provenance, suppression et demandes de liaison de comptes. SQLite peut être exportée sur un autre poste.

## Fonctionnalités réellement codées dans ce lot

- `Incoming.account_id` est propagé depuis les métadonnées de Discord écrit et les tags IRC `user-id` de Twitch. Discord vocal possède déjà `speaker_id` ; le même namespace `discord` relie voix et écrit sur un compte identique, et le **chat natif du même vocal** pour une session Discord autorisée ; les autres salons restent isolés.
- Le micro local reçoit `author="Goldaj"` et un rappel de contexte **créateur/père** dans le système de dialogue. L'origine `microphone` a une identité locale réservée `("microphone","goldaj")` ; le propriétaire confirme qu'il est l'unique utilisateur de ce périphérique. Un pseudonyme Goldaj sur un réseau ne donne jamais cette identité.
- **Identité propriétaire mobile/PC :** `identity_of` mappe les entrées PWA privées authentifiées et le micro PC vers `('microphone','goldaj')`. La configuration `main.py` active ce profil lorsque la mémoire et l'entrée propriétaire sont utilisées. Ce raccordement est **intégré à develop**.
- `MemoryStore` persiste les souvenirs attribués à un compte fiable et **consentant**. À l'expiration des souvenirs ordinaires, seul ce type est purgé ; Core ne possède pas de date d'expiration (contrainte en base). Un compte peut demander sa suppression explicite.
- `MemoryService` expose `!jade-memoire activer`, `!jade-memoire etat`, `!jade-memoire oublier` depuis un message de plateforme identifiable. Sur micro, en cas d'activation mémoire du runtime, le compte local Goldaj est activé automatiquement suivant la décision explicite du propriétaire.
- `Dialogue.respond` reçoit un bref contexte mémoriel non fiable en rôle utilisateur, sans remplacer le prompt de personnalité ni le contrat `[INTENT:...]`. Les souvenirs du même compte sont isolés par salon (Discord/Twitch) ou par identité locale pour le micro, afin de ne pas raconter en public une mémoire d'un autre canal.
- `MemoryService` lance, quand autorisé, un **second appel facultatif au modèle après la réponse**, sans bloquer le TTS. C'est Jade qui choisit `none`, `ordinary`, `core_self` ou `core_relationship` selon le sens de l'événement. Une justification et une citation de preuve dans le tour sont demandées ; si la sortie est invalide, aucune écriture. Protection contre doubles exacts et chaînes évoquant des secrets. **Cela n'est pas un détecteur universel de données sensibles.** Le choix est libre et peut produire des erreurs : recette humaine requise.
- Liaison Discord/Twitch : API de défi court à usage unique, à remettre **privément** puis confirmer depuis le second compte authentifié ; **pas encore de commandes publiques de liaison**. Déliaison par API, avec mémoires séparées suivant leur origine.
- Tests offline spécifiques dans `tests/test_jade_persistent_memory.py`.

### Configuration privée du PC Jade

La configuration est **off par défaut**. Mettre dans la configuration privée, jamais dans Git :

```dotenv
JADE_MEMORY_ENABLED=1
JADE_MEMORY_DB_PATH=D:\\Jade\\data\\jade-memory.sqlite3
JADE_MEMORY_CURATOR_ENABLED=1
```

Le chemin est un exemple de dossier sur le disque D:, pas une affirmation qu'il existe. Il doit être absolu, hors dépôt Git, sur un dossier privé de l'utilisateur qui lance Jade. Le processus crée les tables au premier démarrage. Le curator désactivé mémorise les faits enregistrés manuellement mais ne crée aucun nouveau souvenir ; pour la sélection autonome il faut activer `JADE_MEMORY_CURATOR_ENABLED=1`, ce qui déclenche jusqu'à **un appel LLM additionnel par réponse éligible**. Aucune requête payante n'a été réalisée pour ce développement. Démarrer avec un petit budget et mesurer la dépense réelle.

Sur un serveur Discord/Twitch, la mémoire personnelle nécessite la commande `!jade-memoire activer` émise **par le compte concerné** ; pas d'inscription automatique de spectateurs. `oublier` efface les souvenirs et le profil lié (y compris les identités associées au même profil). Une demande de personne via la parole du micro bénéficie du profil propriétaire attribué localement. **Ne pas déplacer la base sous le dépôt public.**

### Sauvegarde / migration vers un nouveau PC

Le module `src/jade_runtime/memory_transfer.py` fournit deux commandes hors ligne. L'export utilise `sqlite3.Connection.backup()` pour obtenir une image transactionnellement cohérente, même si un journal WAL est actif ; il ajoute un manifeste de version et une empreinte SHA-256. L'import vérifie l'intégrité SQLite et SHA-256, l'absence de fichier de destination et le numéro de schéma. **Il ne fusionne jamais deux bases** et ne remplace jamais une base existante.

Sur l'ancien PC, depuis la racine du dépôt :

```powershell
python -m src.jade_runtime.memory_transfer export --db "D:\Jade\data\jade-memory.sqlite3" --out "D:\Jade\transfert\jade-memory-backup.zip"
```

Copier `jade-memory-backup.zip` sur un support chiffré. **L'archive elle-même n'est pas chiffrée** ; elle contient des données privées. Sur le nouveau PC, installer le même projet ou une version sachant lire le schéma, puis :

```powershell
python -m src.jade_runtime.memory_transfer import --archive "D:\Jade\transfert\jade-memory-backup.zip" --db "D:\Jade\data\jade-memory.sqlite3"
```

Adapter les chemins et définir ensuite `JADE_MEMORY_DB_PATH` sur le nouveau PC. Faire l'import **avant** d'initialiser une nouvelle base ; la commande refuse explicitement d'écraser le fichier destination. Vérifier un petit échantillon de souvenirs par l'API de la mémoire sur le nouveau PC avant de retirer l'ancien. Pour garantir que les derniers souvenirs du PC initial figurent dans l'export final, **arrêter Jade puis refaire un export final sous un nouveau nom** avant transfert. En cas de fichiers déjà créés : garder le fichier existant et choisir un autre chemin, sans écraser.

Le contenu de la base n'est pas synchronisé en temps réel entre PC, et n'inclut ni les fichiers de configuration secrets ni les logs stdout/stderr ; les déplacer séparément si nécessaire. L'archive est limitée à 256 Mio dans cette version, sans streaming ; Codex doit élargir cette limite avant qu'elle soit atteinte.

## Reprise Codex : limites importantes restantes

1. **Validation réelle du poste :** récupérer la PR sans écraser le travail local de Terra/Codex, contrôler la branche courante, les variables de configuration, le volume D: et les droits d'accès, puis tests `python -m compileall -q src main.py` et `python -m unittest discover -s tests -v` ; comparer les résultats CI de la PR. Tester une connexion Discord/Twitch réelle uniquement avec l'accord propriétaire et sans coût non autorisé.
2. **Autobiographie :** la table séparée `jade_self_core` est intégrée ; son rappel est **owner_only** pour Goldaj. Une éventuelle autobiographie publique de Jade nécessiterait un nouveau contrat de visibilité. Voir [l'état actuel](../handbook/BRANCH_STATE.md).
3. **Conversations croisées :** le partage **voix / chat textuel natif du même vocal Discord** est implémenté, à identité et session égales. L'association avec d'autres salons, MP ou chronologies indépendantes reste un projet, détaillé dans le [catalogue](../ameliorations/02-MEMOIRE-PRESENCE.md).
4. **Curation IA :** évaluer qualité réelle des Core, collisions sémantiques, faits contradictoires, effets de coût/latence, disponibilité du modèle et sortie JSON valide. Les refus/retries ne doivent jamais empêcher une réponse. Le moteur autorise au plus quatre tâches concurrentes ; des événements en surcharge peuvent ne pas être mémorisés, à observer.
5. **Droits utilisateur :** compléter les commandes de consultation/export, correction ciblée, désactivation future et déliaison. Actuellement l'effacement global est implémenté, mais pas la correction conversationnelle d'une Core. Réviser une Core ne veut pas dire la purger automatiquement.
6. **Liaison sûre :** brancher la génération/réception du défi d'identité à des interfaces privées **authentifiées**, pas une commande IRC publique ; empêcher code affiché sur un stream, vérifier comptes/source.
7. **Sauvegardes et effacement :** définir politique des archives et procédure de révocation des sauvegardes après `oublier`, ainsi qu'une protection par chiffrement du support ; SQLite par défaut n'est pas chiffré. Evaluer sauvegarde périodique locale hors Git.
8. **Récupération sémantique :** la recherche initiale est simplement chronologique et bornée (8 souvenirs). Plus tard, ajouter pertinence/contradictions/provenance, sans devoir installer un serveur MongoDB.
9. **Mode groupé Discord :** conserver l'isolation des personnes/permissions vocales. Des souvenirs personnels sortant dans un salon public peuvent divulguer des détails ; limiter les rappels à des données appropriées au salon et faire recetter le ton.
10. **Revue des coûts :** `curator_enabled` peut ajouter une génération par tour. Tester charge et pertinence, puis proposer si utile un déclencheur moins coûteux ou une curation par lots sans imposer la demande de validation à l'utilisateur.
11. **Journal :** les logs `jade.conversation` contiennent parfois les transcriptions et ne sont **pas** la base de mémoire, ni un canal de synchronisation. Un retrait d'une personne de la base n'efface pas rétroactivement les fichiers de logs locaux, à traiter opérationnellement.

**Statut actuel :** modules mémoire et PWA intégrés dans `develop`. Cette page garde des actions opérationnelles et des réflexions historiques, sans rouvrir les anciennes PR comme chantiers à fusionner.

**Principes de conservation** : ne pas faire migrer les données privées vers GitHub ; `main` inchangée ; aucun stockage permanent de PCM/WAV ni de transcriptions brutes.
