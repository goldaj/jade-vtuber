# Guide utilisateur de toutes les fonctions : develop

**Documentation correspondant au runtime de develop.** [Installation](INSTALLATION.md), [démo Express](DEMO.md) et [état exact de cette branche](BRANCH_STATE.md). Le produit ne demande **jamais à l'utilisateur de choisir le support à activer** : le launcher démarre tous les canaux ensemble, Jade choisit l'ordre de traitement. Les drapeaux de services individuels demeurent dans le CLI pour les diagnostics, pas comme profils du launcher.

## 1. Démonstration immédiate, sans compte

Installer `Installer-Demo-Express.cmd` sur Windows, puis menu Démarrer → **Jade Demo Express**. Interface graphique, portrait dessiné et dialogues **simulés** ; aucun coût, voix, connexion ni données persistantes. Utilisation directe : `Lancer-Demo-Express.cmd`. Pour la simulation interne du vrai runtime, installer Python/Poetry et lancer `poetry run python main.py` (message « Mode démo »). Ces options sont des **démos**, pas une désactivation du multi-support dans le produit opérationnel.

## 2. Démarrer la vraie Jade sur Windows

Après préparation de tous les connecteurs et validation locale, ouvrir `D:\Jade\launcher\Lancer-Jade.cmd`, choisir **la branche Git**, cliquer **« Mettre à jour et lancer toute Jade »**. Le launcher fait fetch/fast-forward, LFS, vérification Poetry, préflight puis démarre **une instance** de `poetry run python main.py --all-channels`. Pas de profils Discord/micro/mobile, pas de priorité accordée à un canal. Utiliser **Ctrl+C** dans la console pour arrêter proprement. Si Jade refuse de démarrer, relever le préflight et réparer le connecteur indiqué, pas sélectionner un mode partiel.

Un launcher installé hors Git ne se met pas à jour tout seul : réinstaller une fois via `Installer-Launcher-Jade.cmd` après modification de ses scripts. Il cible le disque **D:** du PC propriétaire ; un clone tiers peut utiliser la Démo Express ou une installation Python sans launcher.

## 3. Dialoguer sur Discord écrit

Ajouter le bot sur un serveur avec permissions/intents appropriés, configurer le token privé, activer le moteur complet. Jade reçoit et traite les messages écrits accessibles, répond dans le canal source quand c'est pertinent. Le comportement spontané Discord textuel est réglable via `JADE_DISCORD_TEXT_AUTO_RATE` (défaut 20 %) et `JADE_DISCORD_TEXT_COOLDOWN_SECONDS` (défaut 180 s). Mention, appel direct, contenu et politique interviennent. Le taux d'intervention n'est **pas une priorité d'ordonnancement sur le mobile ou le micro**.

Vérifier dans Discord que les messages privés ne sont pas diffusés oralement dans un canal public. La connexion n'est pas une preuve d'autorisation de lire ou diffuser tout contenu.

## 4. Converser sur Discord vocal

Configurer un salon vocal initial `DISCORD_VOICE_CHANNEL`, les droits du bot, le transport Discord et FFmpeg. Depuis le 27/11, **un seul paramètre dans `src/jade_runtime/discord_config.py`** contrôle Discord : `DISCORD_ENABLED = True` active le texte et la voix dans le lancement habituel, avec choix automatique du moteur vocal ; `False` désactive complètement Discord. Redémarrer Jade après ce changement. `--all-channels` respecte aussi cet interrupteur.

Le vocal utilise Live tant que les dépenses API mensuelles globales restent sous le seuil : **50 EUR si le suivi est complet et suffisamment à jour, sinon 40 EUR avec un suivi estimé exploitable**. Les relevés standard conduisent normalement au seuil de 40 EUR. Au seuil, Jade revient au parcours classique STT → dialogue → TTS pour le reste du mois. Sans données essentielles de coûts, elle reste en classique et indique la raison dans les journaux. La collecte OpenAI emploie la clé d'administration déjà prévue par `JADE_OPENAI_ADMIN_KEY` ; la clé normale du dialogue seule ne suffit pas à lire ces dépenses. Le mobile garde son propre choix Live/classique et n'a aucun budget financier.

Dans l’application, ouvre **Config → Suivi Discord** pour voir les minutes GPT-Live relevées ce mois-ci sur Discord. Décoche **Activer GPT-Live sur Discord** pour fermer le Live et reprendre en voix classique à la prochaine prise de parole. Recoche pour laisser les règles de dépense et de disponibilité décider. Jade attend une interaction dans le salon vocal sans saluer automatiquement les arrivées.

En tête-à-tête, la parole peut être transmise directement au Live. En groupe, Jade conserve ses règles de participation et transcrit d'abord pour décider si elle doit intervenir ; ce parcours a donc une latence supérieure. Il n'est pas nécessaire de prononcer systématiquement « Jade » si les politiques du dialogue et du pont vocal autorisent la participation. Vérifier sur un vrai serveur la capture, les changements de canal, la lecture et le comportement à la déconnexion. Les canaux audio/écrit Discord partagent une identité contrôlée par le compte et la session ; un pseudo seul ne prouve pas cette identité. [Détails et recette restante](../architecture/DISCORD_LIVE.md).

## 5. Twitch : lecture et réponse écrite

Configurer `TWITCH_CHANNEL`, `TWITCH_TOKEN`, éventuellement `TWITCH_BOT_LOGIN`, et **`JADE_TWITCH_ENABLED=1`, `JADE_TWITCH_SEND=1`**. Jade lit les messages IRC du salon, sélectionne les messages auxquels répondre et envoie ses réponses avec une limitation de débit. L'activation d'un client IRC ne garantit pas l'envoi : vérifier OAuth, scope, token, profil du bot et ses droits réels. L'autorenouvellement est une configuration distincte documentée dans `docs/operations/reference/TWITCH-AUTH.md`.

## 6. Microphone et voix du PC

Le microphone local est considéré comme l'entrée du propriétaire Goldaj, à condition d'être employé dans l'environnement privé de son PC. Jade écoute et transcrit en OpenAI STT ; la synthèse vocale utilise OpenAI TTS avec sortie `JADE_AUDIO_OUTPUT=ffplay` pour le retour local. Vérifier le périphérique par défaut, les permissions Windows, les boucles d'écho et les droits du micro. La capture attend la fin de **sa propre réponse**, pas l'épuisement de toutes les conversations Twitch/Discord/mobile.

Un son entendu dans un canal privé ne doit pas être lu publiquement sur Discord ni injecté dans les sous-titres OBS en raison de l'activation simultanée des sorties.

## 7. Application Android privée Jade

**Pas d'APK.** Installer Tailscale sur Android, rejoindre le même tailnet privé que le PC. Sur le PC, Codex doit configurer Tailscale Serve HTTPS vers le service mobile `127.0.0.1:8766`, l'identité propriétaire `JADE_MOBILE_OWNER_LOGIN`, l'origine HTTPS `JADE_MOBILE_PUBLIC_ORIGIN` et le token différent `JADE_MOBILE_TOKEN` (32-256 caractères). Ouvrir l'adresse Serve **réellement affichée** dans Chrome, saisir le jeton dans l'écran d'accès, menu `⋮` → **Installer l'application** ou **Ajouter à l'écran d'accueil**. Le jeton n'est pas conservé après rechargement complet. Il ne doit pas figurer dans l'URL.

La PWA permet :
- **Texte** : rédiger/envoyer un message et voir la réponse ; session de discussion conservée pendant l'usage de la page.
- **Voix.** Le Live est sélectionné par défaut. Sur **Accueil** ou en **plein écran**, touche le micro pour l’activer ou le couper. La pastille de la scène est bleu clair quand le micro est coupé, bleu foncé quand Jade attend ta voix et rouge pendant la connexion ou l’échange. Elle affiche aussi « Live » sur Accueil. Dans **Config → Paramètres**, décocher **Mode Live** rétablit l’enregistrement pendant l’appui puis l’envoi au relâchement. Ton choix est enregistré.
- **Reprise du Live**. Si la fermeture précédente reste non confirmée, utilise **Réessayer** dans Config ou touche le micro sur Accueil. Quand Jade est disponible, touche le micro pour démarrer la capture.
- **Synthèse vocale** : case **Voix activée** dans Config, cochée au premier lancement. Couper la voix évite un TTS mobile inutile ; ce choix reste conservé après fermeture.
- **Réglages** : modèle, décor, voix, animations, secousses, notifications et filtre des logs sont sauvegardés automatiquement sur ce téléphone. Le choix Live est conservé par Jade. Rouvrir l’application ne réactive jamais le micro. Le bouton Décor et Recentrer occupent un bandeau au-dessus de la scène de l’Accueil.
- **Avatar.** Jade r21 s’affiche par défaut, debout en Chambre, Cuisine et Salon. Les décors Cuisine et Salon sont statiques. Le SDK Web compatible et les assets Git LFS permettent le rendu Live2D. Si le modèle ne charge pas, la conversation reste utilisable.
- **Nouveau fil / plein écran** : nouveau contexte de dialogue mobile ou affichage agrandi.
- **Sécurité** : réseau privé Tailscale, identité utilisateur vérifiée et jeton Bearer ; sans ces deux éléments, refus 403/401. Ne pas activer Funnel ni modifier le VPS Hyperliquid.

La PWA n'utilise pas le VPS de trading. **PC arrêté ou Jade non exécutée = application indisponible**, même si Tailscale Android est actif. Le guide pas-à-pas complet pour Codex sur le PC est `docs/history/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md`.

## 8. Avatar Live2D Windows et affichage VTube Studio

L'avatar autonome r20 Windows est lancé par `--all-channels`, dépend du modèle local restauré par `git lfs pull`, de `live2d-py`, Pygame/OpenGL et du GPU. Les mouvements sont liés aux événements audio. **VTube Studio est une autre sortie** : si `JADE_VTS_ENABLED=1` et `JADE_VTS_TOKEN` sont configurés et que son application est déjà ouverte, Jade peut piloter ses hotkeys. Ne pas installer VTube Studio juste pour faire fonctionner l'avatar autonome.

Le r21 mobile joue les dix-huit mouvements d’intention. Son raccordement automatique à l’avatar Win32 reste suivi dans DEV-001. [État du code](BRANCH_STATE.md)

## 9. Voix et intonations

Sur mobile et Discord en GPT-Live, Jade suit les consignes de prosodie associées à la session. Le propriétaire a choisi **Friponne rapide** pour son installation. Un nouveau profil Live utilise Brise par défaut. Le chemin vocal classique utilise `shimmer` à 1,25×, avec pitch +2 demi-tons si FFmpeg dispose de Rubber Band.

Le dialogue classique produit une intention avant le texte, enlevée avant l’affichage, la voix et la mémorisation. L’intention aide le moteur de synthèse à jouer le ton. Écouter les répliques reste la façon de comparer le rendu effectif de chaque moteur.

## 10. Mémoire persistante et Core Memories

### Demander à Jade de retenir un souvenir (DEV-011)

Depuis le microphone, la PWA ou un canal de discussion autorisé, on peut demander en **langage naturel** à Jade de mémoriser un fait. Exemples, à dire ou écrire :

- « Jade, retiens que notre projet a commencé aujourd’hui. »
- « Jade, souviens-toi que nous avons trouvé une bonne idée. »
- « Jade, garde ce souvenir : nous avons terminé le prototype. »
- Même « Jade, ajoute à tes Core Memories : notre première conversation » crée **uniquement un souvenir ordinaire** ; Jade répond clairement qu’elle choisit elle-même ses Core Memories.

**Règle fondamentale :** une demande humaine, y compris celle de Goldaj, ne crée **jamais** une Core Memory profonde (`core_self` ou `core_relationship`). Jade seule en décide au travers de son mécanisme de curation autonome, selon la valeur réelle du dialogue, indépendamment de toute consigne de l’interlocuteur. Une demande de souvenir reconnue est enregistrée en SQLite dans `memories` avec `kind=ordinary`, **durée de conservation de 365 jours par défaut** et isolement selon le profil et le salon. L’opération est déterministe et ne dépend pas du modèle de conversation ; Jade ne confirme que si l’écriture en base réussit, avec signalement des doublons ou des échecs. Le contenu secret ou manifestement sensible à l’accès est refusé.

La mémoire du compte doit être active. Sur Discord, en serveur comme en message privé, elle s'active automatiquement lors des interactions admissibles pour les comptes identifiés ; sur Twitch il faut utiliser `!jade-memoire activer`. Le micro local et la PWA propriétaire partagent leur profil authentifié. Aucun surnom ne prouve une identité. Il n'existe plus de commande d'oubli global ni de blocage de réinscription Discord ; la suppression ciblée des Core Memories reste disponible.

**Consultation et suppression.** Jade peut consulter et restituer les souvenirs L1/L2/L3 avec leur provenance sur tous ses canaux. Les commandes `!jade-memoire autobiographie` et `!jade-memoire lister-core` consultent les Core existantes. Le propriétaire, identifié via le micro ou la PWA, peut les corriger avec `!jade-memoire supprimer-self <identifiant>` et `!jade-memoire supprimer-core <identifiant>`. Jade reste seule décisionnaire de la création d’une Core Memory.

Cette fonctionnalité suppose `JADE_MEMORY_ENABLED=1`. Toute valeur privée explicite `0` continue de désactiver la mémoire jusqu’à modification et redémarrage de Jade.


En mode réel, la mémoire SQLite **et sa curation** sont activées par défaut. Le fichier privé est placé hors du dépôt : `D:\\Jade\\private\\jade-memory.sqlite3` sous Windows si D: existe, sinon `~/.jade/jade-memory.sqlite3`. Le chemin est personnalisable avec `JADE_MEMORY_DB_PATH`. **Les valeurs explicites `0` dans le `.env` privé ou les variables du processus restent prioritaires** ; les retirer ou les changer pour retrouver les valeurs par défaut, puis redémarrer Jade. Le mode démo hors ligne ne crée pas de base. Les souvenirs ordinaires expirent après **365 jours**, contrairement aux Core Memories du niveau 3 qui ne subissent aucune purge temporelle. Le niveau 1 en base est purgé après **7 jours** et les reprises chargent intégralement les **24 dernières heures** par profil/salon. La première ouverture de l'ancienne base SQLite étend les expirations ordinaires existantes à 365 jours depuis leur date de création (sans restaurer les souvenirs déjà supprimés). Sur **Discord (serveur, vocal ou message privé)**, les comptes identifiés sont inscrits à la mémoire dès leur première interaction effectivement traitée : aucune commande d'activation nécessaire. Cette politique suppose que les participants, y compris les correspondants en MP, ont été informés de la conservation des échanges. **Twitch** conserve l'activation explicite via `!jade-memoire activer`. Tout compte vérifié peut utiliser `!jade-memoire etat`. La commande d'oubli global et le blocage de réinscription Discord ont été retirés. Le simple pseudo affiché ne vaut jamais preuve d'identité.

La lecture globale des souvenirs couvre tous les comptes et tous les salons. Jade peut se référer à un souvenir d’un autre canal et en préciser l’origine. La reprise automatique de l’historique d’une session sélectionne les tours récents de son compte et de son salon.

Pour **associer un compte Discord/Twitch au mobile**, envoyer `!jade-memoire identite` depuis le compte Discord à associer (MP ou serveur) ; sur Twitch, envoyer d'abord `!jade-memoire activer`, puis `!jade-memoire identite`. Dans la PWA privée, choisir la plateforme et coller l'ID numérique indiqué. Le mobile génère une commande `!jade-memoire confirmer [code]` à envoyer **depuis le compte Discord/Twitch correspondant**, dans les **5 minutes**. C'est le **code** qui expire, pas l'association confirmée : elle dure jusqu'à `!jade-memoire delier`. La liaison rapproche les profils d’écriture. La consultation globale reste disponible indépendamment de cette liaison.

Le microphone local et le client Android propriétaire authentifié peuvent retrouver le profil Goldaj commun. Le curation optionnelle par LLM peut générer un **appel supplémentaire** pour décider si un fait devient un souvenir ordinaire ou fondateur. Les souvenirs ne constituent pas une preuve objective que Jade a réellement « vécu » un événement. La sauvegarde/restauration SQLite se fait via `memory_transfer.py`, sans écraser un fichier existant. Plus d'informations dans `docs/history/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md`.

## 11. Conversations unifiées et autobiographie

Discord vocal et son chat textuel natif partagent le contexte de la même session vérifiée. Une nouvelle session peut avoir une autre clé. Cette continuité de dialogue s’ajoute à la recherche globale de souvenirs par Jade.

## 12. Arbitrage autonome entre tous les canaux

Tous les supports partagent une **file bornée**. Quand plusieurs conversations indépendantes attendent, Jade choisit l'identifiant du prochain tour selon contenu, attente et urgence **sans poids fixe pour Discord/Twitch/mobile/PC**. Elle préserve l'ordre d'un même fil et applique un repli FIFO si le modèle d'arbitrage échoue ou dépasse son délai, ainsi qu'une règle anti-attente trop longue. Cet arbitrage peut entraîner un coût API supplémentaire. Il ne génère pas plusieurs réponses en parallèle : le moteur exécute un tour à la fois et ne coupe pas un tour déjà commencé. La probabilité de réponse sur Discord n'est pas une priorité de service.

## 13. API HTTP locale et interface PC

Une API textuelle locale authentifiée existe distinctement de la PWA. Elle écoute `127.0.0.1:8765` par défaut, exige `JADE_HTTP_ENABLED=1` et `JADE_HTTP_TOKEN` (32+ caractères), avec endpoint `POST /message` et `Authorization: Bearer`. Le client HTML local peut servir au diagnostic sans ouvrir un port public. Le token HTTP **ne doit pas** être identique au token PWA. La réponse est dirigée vers l'appelant local et n'a pas à être diffusée automatiquement sur Discord.

## 14. Sous-titres OBS, supervision, arrêt et diagnostic

Les sous-titres temporaires sont écrits sur `JADE_SUBTITLE_PATH` et effacés à la fin de la lecture ; ne pas les confondre avec un archivage des conversations. Les réponses micro/HTTP privées ne doivent pas y être affichées lors d'une diffusion publique. Les journaux de conversation structurés peuvent contenir de la provenance et du texte : configurer leur accès et durée de conservation avec prudence.

En cas de panne : contrôler la console de lancement, les erreurs `--preflight --all-channels`, les connexions réelles, les périphériques et les tokens privés **sans les coller dans un ticket**. Sur Android, 403 signifie typiquement identité Serve, 401 jeton Bearer ; un rendu absent évoque SDK Web ou modèle LFS. Arrêter par `Ctrl+C`, pas par suppression forcée de toutes les tâches du PC. Voir [INSTALLATION.md](INSTALLATION.md) et [TECHNICAL.md](TECHNICAL.md).

## 15. Réactions émotionnelles du modèle r21

Le r21 joue neuf intentions, chacune avec deux mouvements et deux libellés. Jade tire une seule variante A ou B par réponse, y compris en texte seul. En vocal, le son pilote la bouche puis le visage et le corps retrouvent la pose de repos. Les intentions Triste et Colère complètent Neutre, Enjouée, Enthousiaste, Curieuse, Tendre, Rassurante et Sérieuse. [Recette r21](../operations/handoffs/2026-11-27-chatgpt-intentions-r21-implementation.md)

Pour couper les réactions visuelles, régler `JADE_AVATAR_INTENT_ENABLED=0` dans la configuration privée. Redémarrer Jade, puis recharger la PWA. La prosodie, l’Idle et le mouvement de bouche continuent.

## Dialogue et fréquence des réponses

Le fichier `prompt_chat.txt` fournit la personnalité. Le modèle et ses réglages sont configurables. Le dialogue classique utilise par défaut GPT-6 Luna avec effort `low` et plafond de 2 048 tokens de complétion.

**Conversation individuelle :** Jade répond aux messages valides du propriétaire sur le micro PC, le mobile privé et l'API locale. Sur Discord texte/vocal et Twitch, le tête-à-tête est déterminé par les participants **observés** ; seul un participant humain actif -> réponse systématique. **En groupe :** sélection probabiliste des tours spontanés admissibles : 20 % sur Discord et 30 % sur Twitch, avec exceptions pour les interpellations explicites et les règles de commande, de suivi, de silence, de cooldown et de saturation. Twitch ne voit pas ses spectateurs silencieux via IRC. Le texte Discord maintient un historique des participants actifs du salon sur dix minutes.

**Conservation :** l'inscription est automatique pour les membres identifiés d'un serveur Discord qui échangent avec Jade, sans commande préalable ; Twitch requiert toujours `!jade-memoire activer` ; les MP Discord vérifiés sont inscrits automatiquement. La mémoire et sa curation sont activées par défaut sur le runtime réel, sauf paramètres privés contraires. Les réponses livrées sont conservées avec le message utilisateur **en texte intégral**, et non résumées, dans la base SQLite privée. Tous les échanges des **dernières 24 heures** d'un même profil et salon sont rechargés à la reprise d'une session, **sans plafond de nombre**. Les échanges complets sont supprimés de SQLite après **7 jours** ; l'historique éphémère hors SQLite reste borné. La purge se déclenche au démarrage et toutes les heures pendant le fonctionnement réel. La quantité de texte réinjectée peut toutefois dépasser les limites de contexte du modèle conversationnel lors de journées très chargées. Les messages publics auxquels Jade n'a pas répondu ne sont pas automatiquement archivés par cette fonction. La commande d'effacement global a été supprimée. Les commandes de suppression individuelle des Core Memories restent disponibles. `!jade-memoire delier` sépare les profils **sans effacer les données**. Les cas anciens où plusieurs comptes d'un même service sont liés peuvent nécessiter une séparation manuelle ; la suppression ne couvre pas les journaux console séparés.



## Sauvegardes et incidents (15/11/2026)

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Les versions de schéma mémoire 1 à 8 sont prises en charge par la fonction d'export/import portable, sous réserve des tests du SHA exécuté. L'export ZIP est en clair et peut conserver des données même après leur suppression de Jade : garder les archives hors Git, appliquer une durée de conservation et vérifier les restaurations en environnement isolé. En cas de CI rouge, ne pas considérer la simple présence d'un fichier ou de sa documentation comme une fonctionnalité validée.

Les travaux futurs, sans doublon avec ce guide utilisateur, sont centralisés dans le [catalogue](../ameliorations/README.md).


## Association de comptes à la mémoire personnelle

Lorsque la mémoire est active (par défaut sur le runtime réel), le compte Discord de serveur est automatiquement inscrit lors de sa première interaction traitée ; pour Twitch, utiliser `!jade-memoire activer` ; les MP Discord sont automatiques. Demander ensuite son ID numérique avec `!jade-memoire identite`. Depuis **la PWA privée de Goldaj**, ouvrir « Associer un compte Discord / Twitch », saisir l'**ID numérique** du compte, puis copier la commande `!jade-memoire confirmer <code>` vers le chat **de ce même compte** dans les cinq minutes. La confirmation est à usage unique et liée à cet ID ; elle ne fusionne pas les historiques de salons indépendants. Sur un compte lié, `!jade-memoire delier` conserve les souvenirs mais sépare les profils ; la suppression individuelle des Core Memories demeure possible. Les données du propriétaire et des autres comptes restent distinctes. Voir [la passation technique du 16 novembre](../operations/handoffs/2026-11-16-chatgpt-pcm-memoire-mobile.md).


## REC-039 (ancienne DEV-032) : documents téléchargeables (mobile et Discord)

Sur demande explicite d'un utilisateur autorisé, Jade peut produire jusqu'à quatre fichiers par tour. Par défaut, **tous les utilisateurs Discord disposant d'un identifiant de transport vérifié** peuvent créer un document en MP, en salon écrit et dans un salon vocal, sans liaison de compte préalable. Le mode `JADE_DOCUMENT_ACCESS_MODE=all` est le défaut ; `owner` (Goldaj et comptes liés) et `allowlist` sont disponibles si une restriction est souhaitée, avec `JADE_DOCUMENT_ALLOWED_DISCORD_IDS` pour les identifiants autorisés. **Si l'environnement privé définit déjà une valeur explicite, elle prime sur ce défaut.** L'application mobile conserve son authentification privée. Aucun mécanisme de reconnaissance vocale supplémentaire n'est requis.

Par défaut : PDF pour lire, DOCX pour modifier, CSV/XLSX pour les tableaux, HTML pour du code/site sans langage précisé ; extensions explicites `.py`, `.js`, `.css`, `.json`, `.md` ou autres fichiers texte, et ZIP pour un site à plusieurs fichiers. Les pièces jointes sont de vrais fichiers ; leurs noms et boutons de téléchargement apparaissent dans la conversation écrite. En vocal PWA, Jade parle et affiche aussi la pièce jointe ; en vocal Discord, elle parle et poste le fichier dans le chat textuel du salon vocal. En MP Discord et salon écrit, le fichier est joint au message de réponse.

Les fichiers sont enregistrés dans un dossier privé hors Git (`JADE_DOCUMENT_DIR`, par défaut voisin de `JADE_MEMORY_DB_PATH`) et ne sont plus téléchargeables via Jade après **24 h**. Discord supprime automatiquement ses messages porteurs de fichiers au terme de leur conservation, si la connexion et ses permissions le permettent ; les copies déjà téléchargées ne peuvent pas être révoquées. Les pièces jointes mobile sont accessibles uniquement à travers la PWA Tailscale privée et un jeton Bearer. Pas de publication automatique d'informations privées dans les documents des salons publics. Ne pas soumettre des fichiers à exécuter directement depuis Jade.

**État :** implémentation achevée sur `develop`, [CI Linux/Windows verte](https://github.com/goldaj/jade-vtuber/actions/runs/45043574769), **recette réelle Android/Discord à valider**. La taille bornée par le budget de sortie du modèle est voulue ; le PDF minimal sans Unicode complet est accepté pour cette version. [REC-039](../backlog/02-RECETTE.md) et [passation](../operations/handoffs/2026-11-22-chatgpt-dev032-documents.md).
