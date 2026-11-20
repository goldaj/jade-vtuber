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

Configurer un salon vocal initial `DISCORD_VOICE_CHANNEL`, les droits du bot, le transport Discord et FFmpeg ; la voix de l'utilisateur est envoyée à STT OpenAI, la réponse suit le moteur puis TTS. Il n'est pas nécessaire de prononcer systématiquement « Jade » si les politiques du dialogue et du pont vocal autorisent la participation. Vérifier sur un vrai serveur la capture, les changements de canal, la lecture et le comportement à la déconnexion. Les canaux audio/écrit Discord peuvent partager une identité de conversation contrôlée par la session ; le pont ne prouve pas l'identité d'une personne par son pseudo seul.

## 5. Twitch : lecture et réponse écrite

Configurer `TWITCH_CHANNEL`, `TWITCH_TOKEN`, éventuellement `TWITCH_BOT_LOGIN`, et **`JADE_TWITCH_ENABLED=1`, `JADE_TWITCH_SEND=1`**. Jade lit les messages IRC du salon, sélectionne les messages auxquels répondre et envoie ses réponses avec une limitation de débit. L'activation d'un client IRC ne garantit pas l'envoi : vérifier OAuth, scope, token, profil du bot et ses droits réels. L'autorenouvellement est une configuration distincte documentée dans `docs/operations/reference/TWITCH-AUTH.md`.

## 6. Microphone et voix du PC

Le microphone local est considéré comme l'entrée du propriétaire Goldaj, à condition d'être employé dans l'environnement privé de son PC. Jade écoute et transcrit en OpenAI STT ; la synthèse vocale utilise OpenAI TTS avec sortie `JADE_AUDIO_OUTPUT=ffplay` pour le retour local. Vérifier le périphérique par défaut, les permissions Windows, les boucles d'écho et les droits du micro. La capture attend la fin de **sa propre réponse**, pas l'épuisement de toutes les conversations Twitch/Discord/mobile.

Un son entendu dans un canal privé ne doit pas être lu publiquement sur Discord ni injecté dans les sous-titres OBS en raison de l'activation simultanée des sorties.

## 7. Application Android privée Jade

**Pas d'APK.** Installer Tailscale sur Android, rejoindre le même tailnet privé que le PC. Sur le PC, Codex doit configurer Tailscale Serve HTTPS vers le service mobile `127.0.0.1:8766`, l'identité propriétaire `JADE_MOBILE_OWNER_LOGIN`, l'origine HTTPS `JADE_MOBILE_PUBLIC_ORIGIN` et le token différent `JADE_MOBILE_TOKEN` (32-256 caractères). Ouvrir l'adresse Serve **réellement affichée** dans Chrome, saisir le jeton dans l'écran d'accès, menu `⋮` → **Installer l'application** ou **Ajouter à l'écran d'accueil**. Le jeton n'est pas conservé après rechargement complet. Il ne doit pas figurer dans l'URL.

La PWA permet :
- **Texte** : rédiger/envoyer un message et voir la réponse ; session de discussion conservée pendant l'usage de la page.
- **Voix** : appuyer pour enregistrer, toucher à nouveau pour envoyer, durée maximale 20 s ; permission microphone Chrome/Android obligatoire ; STT et TTS exécutés par le PC. **Pas d'écoute continue/interruptions WebRTC**.
- **Synthèse vocale** : bouton « Voix activée / Voix coupée ». Couper la voix évite un TTS mobile inutile.
- **Avatar** : visage r20 sur fond transparent avec décor illustré et animé, expressions et bouche approximativement animées par l'audio **si le SDK Web compatible est installé sur D:**. Si le SDK manque ou n'est pas compatible, le chat peut rester accessible mais l'avatar sera absent.
- **Nouveau fil / plein écran** : nouveau contexte de dialogue mobile ou affichage agrandi.
- **Sécurité** : réseau privé Tailscale, identité utilisateur vérifiée et jeton Bearer ; sans ces deux éléments, refus 403/401. Ne pas activer Funnel ni modifier le VPS Hyperliquid.

La PWA n'utilise pas le VPS de trading. **PC arrêté ou Jade non exécutée = application indisponible**, même si Tailscale Android est actif. Le guide pas-à-pas complet pour Codex sur le PC est `docs/history/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md`.

## 8. Avatar Live2D Windows et affichage VTube Studio

L'avatar autonome r20 Windows est lancé par `--all-channels`, dépend du modèle local restauré par `git lfs pull`, de `live2d-py`, Pygame/OpenGL et du GPU. Les mouvements sont liés aux événements audio. **VTube Studio est une autre sortie** : si `JADE_VTS_ENABLED=1` et `JADE_VTS_TOKEN` sont configurés et que son application est déjà ouverte, Jade peut piloter ses hotkeys. Ne pas installer VTube Studio juste pour faire fonctionner l'avatar autonome.

Le modèle r21 et certains assets artistiques en cours ne doivent pas être présentés comme un r20 validé en production.

## 9. Voix Étincelle, intentions et rendu émotionnel

La branche contient un moteur `intent_engine.py` : Jade émet un préfixe strict `[INTENT:label]` qui est retiré avant affichage, prononciation et mémorisation. Une intention reconnue guide la prosodie de façon encadrée. La voix publique par défaut documentée est **Étincelle** avec `shimmer` et vitesse 1,25× ; le pitch +2 demi-tons est produit en traitement audio DSP lorsque FFmpeg prend en charge `rubberband`. Ne pas confondre pitch DSP avec un paramètre magique de l'API OpenAI. Des alternatives vocales Friponne/Rosée existent dans la documentation, pas forcément accessibles par un sélecteur utilisateur.

Les nuances émotionnelles et la qualité sonore exigent un **test d'écoute réel**. Elles peuvent varier selon la réponse, le moteur TTS et la latence.

## 10. Mémoire persistante et Core Memories

### Enregistrer une Core Memory à la demande de Goldaj (DEV-011)

Sur le runtime réel, Jade reconnaît une instruction **explicite** du créateur, sans utiliser la curation automatique. Exemples à dicter ou écrire :

- « Jade, ajoute à tes Core Memories : Goldaj est ton créateur. » (souvenir relationnel)
- « Jade, enregistre dans tes souvenirs autobiographiques : notre première conversation sur Discord. » (autobiographie privée de Jade)
- « Jade, je veux que tu gardes ceci dans tes Core Memories : notre première conversation sur Discord. »

La demande doit commencer par un verbe clair (« ajoute », « enregistre », « garde », « mémorise »...) et mentionner les **Core Memories** ou un équivalent explicite (« mémoires fondatrices », « souvenirs autobiographiques »). Jade accepte aussi les formulations STT séparées par « que » au lieu d'un deux-points. **Ce n'est pas une promesse implicite du LLM** : l'opération passe directement par SQLite. Jade confirme uniquement une écriture réussie ; un doublon est signalé, une demande vide, trop longue (> 400 caractères), sensible ou non autorisée est refusée. Aucun appel au LLM n'est nécessaire à cette opération.

Le micro local et la PWA mobile authentifiée sont Goldaj ; les comptes Discord ou Twitch doivent être **préalablement liés au même profil par vérification**, une simple déclaration orale ou un pseudonyme « Goldaj » ne suffit jamais. Les Core Memories autobiographiques sont conservées dans `jade_self_core` (privées au propriétaire), les Core Memories relationnelles dans `memories` avec `kind=core_relationship` et `scope=person`. Elles ne sont jamais injectées dans le contexte de salons Discord/Twitch publics. Le stockage est persistant sans expiration automatique et sans duplication entre canaux. Les commandes privées `!jade-memoire autobiographie` et `!jade-memoire supprimer-self <identifiant>` restent réservées au propriétaire ; les souvenirs relationnels sont supprimables via les fonctions d'effacement existantes. L'effacement d'un compte lié supprime ses souvenirs Core d'origine sans effacer ceux des autres comptes.

Cette commande exige une mémoire active. Si une configuration privée force `JADE_MEMORY_ENABLED=0`, réactiver la mémoire et redémarrer Jade avant l'essai.



En mode réel, la mémoire SQLite **et sa curation** sont activées par défaut. Le fichier privé est placé hors du dépôt : `D:\\Jade\\private\\jade-memory.sqlite3` sous Windows si D: existe, sinon `~/.jade/jade-memory.sqlite3`. Le chemin est personnalisable avec `JADE_MEMORY_DB_PATH`. **Les valeurs explicites `0` dans le `.env` privé ou les variables du processus restent prioritaires** ; les retirer ou les changer pour retrouver les valeurs par défaut, puis redémarrer Jade. Le mode démo hors ligne ne crée pas de base. Les souvenirs ordinaires expirent, contrairement aux Core Memories. Sur un **serveur Discord**, les intervenants identifiés sont inscrits à la mémoire dès leur première interaction effectivement traitée : aucune commande d'activation nécessaire. Cette politique suppose que les membres ont été informés de la conservation des échanges avant de participer. Les MP Discord et Twitch conservent l'activation explicite via `!jade-memoire activer`. Tout compte peut utiliser `!jade-memoire etat` et `!jade-memoire oublier` : sur Discord, l'effacement bloque durablement la réinscription automatique, jusqu'à un nouvel `!jade-memoire activer`. Le simple pseudo affiché ne vaut jamais preuve d'identité.

Le microphone local et le client Android propriétaire authentifié peuvent retrouver le profil Goldaj commun. Le curation optionnelle par LLM peut générer un **appel supplémentaire** pour décider si un fait devient un souvenir ordinaire ou fondateur. Les souvenirs ne constituent pas une preuve objective que Jade a réellement « vécu » un événement. La sauvegarde/restauration SQLite se fait via `memory_transfer.py`, sans écraser un fichier existant. Plus d'informations dans `docs/history/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md`.

## 11. Conversations unifiées et autobiographie

Les améliorations de `develop` font correspondre certaines interventions Discord écrites/orales à un même contexte de session validé, sans ouvrir automatiquement l'historique privé à tous les canaux. Une déconnexion ou un changement de session peut créer une nouvelle clé. Des mécanismes d'autobiographie et de mémoire de Jade ont été intégrés, mais leur niveau de curation, origine et confidentialité doivent être vérifiés au code. Une discussion privée du propriétaire ne doit pas devenir une anecdote publique.

## 12. Arbitrage autonome entre tous les canaux

Tous les supports partagent une **file bornée**. Quand plusieurs conversations indépendantes attendent, Jade choisit l'identifiant du prochain tour selon contenu, attente et urgence **sans poids fixe pour Discord/Twitch/mobile/PC**. Elle préserve l'ordre d'un même fil et applique un repli FIFO si le modèle d'arbitrage échoue ou dépasse son délai, ainsi qu'une règle anti-attente trop longue. Cet arbitrage peut entraîner un coût API supplémentaire. Il ne génère pas plusieurs réponses en parallèle : le moteur exécute un tour à la fois et ne coupe pas un tour déjà commencé. La probabilité de réponse sur Discord n'est pas une priorité de service.

## 13. API HTTP locale et interface PC

Une API textuelle locale authentifiée existe distinctement de la PWA. Elle écoute `127.0.0.1:8765` par défaut, exige `JADE_HTTP_ENABLED=1` et `JADE_HTTP_TOKEN` (32+ caractères), avec endpoint `POST /message` et `Authorization: Bearer`. Le client HTML local peut servir au diagnostic sans ouvrir un port public. Le token HTTP **ne doit pas** être identique au token PWA. La réponse est dirigée vers l'appelant local et n'a pas à être diffusée automatiquement sur Discord.

## 14. Sous-titres OBS, supervision, arrêt et diagnostic

Les sous-titres temporaires sont écrits sur `JADE_SUBTITLE_PATH` et effacés à la fin de la lecture ; ne pas les confondre avec un archivage des conversations. Les réponses micro/HTTP privées ne doivent pas y être affichées lors d'une diffusion publique. Les journaux de conversation structurés peuvent contenir de la provenance et du texte : configurer leur accès et durée de conservation avec prudence.

En cas de panne : contrôler la console de lancement, les erreurs `--preflight --all-channels`, les connexions réelles, les périphériques et les tokens privés **sans les coller dans un ticket**. Sur Android, 403 signifie typiquement identité Serve, 401 jeton Bearer ; un rendu absent évoque SDK Web ou modèle LFS. Arrêter par `Ctrl+C`, pas par suppression forcée de toutes les tâches du PC. Voir [INSTALLATION.md](INSTALLATION.md) et [TECHNICAL.md](TECHNICAL.md).

## 15. Réactions émotionnelles du modèle 2D (nouveau sur develop)

Quand Jade renvoie une intention valide `neutral`, `playful`, `excited`, `curious`, `tender`, `reassuring` ou `serious`, le modèle 2D Windows reçoit une commande d'expression ; la PWA propriétaire affiche une expression (si Live2D Web est compatible) et une **courte indication textuelle d'humeur**. Deux variantes A/B tournent entre deux réponses successives de même intention. C'est un complément visuel : la phrase réellement dite ou écrite par Jade reste inchangée. Le rendu fonctionne aussi en réponse **écrite sans voix** ; la bouche continue d'être synchronisée sur le son quand il y en a. La réaction s'efface après la fin de lecture ou 12 secondes sans son pour revenir à l'Idle neutre. Les sept expressions de premier choix sont distinctes, mais la palette r20 limitée implique des réutilisations pour la variante B.

**Activation :** `JADE_AVATAR_INTENT_ENABLED=1` dans la configuration privée sur le PC (défaut). Pour couper les réactions émotionnelles sans toucher à la voix ni au lip-sync : `JADE_AVATAR_INTENT_ENABLED=0`. Redémarrer Jade, recharger la PWA ; il n'existe pas encore de bouton ON/OFF à chaud sur l'application mobile. En mode coupé, la détection vocale des intentions continue pour le TTS. Les 14 textes sont de simples libellés sur la PWA, jamais envoyés à Discord/Twitch ou prononcés. En cas d'échec du rendu, la conversation doit continuer. **Les 14 véritables animations propres (deux par intention) sont le prochain chantier de création de motions Live2D, pas un résultat déjà livré.** Voir la [passation Codex](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md) et prévoir un test visuel PC/Android.

## Dialogue, mémoire et fréquence des réponses — develop, 15 novembre 2026

La personnalité active de Jade est le texte exact approuvé par Goldaj dans `prompt_chat.txt`. La génération utilise par défaut GPT-6 Luna en `low`, plafond 320 tokens de complétion (incluant le raisonnement interne). Le moteur d'intentions existant ajoute puis masque son tag séparément ; rien ne change à la syntaxe `[INTENT:...]`.

**Conversation individuelle :** Jade répond aux messages valides du propriétaire sur le micro PC, le mobile privé et l'API locale. Sur Discord texte/vocal et Twitch, le tête-à-tête est déterminé par les participants **observés** ; seul un participant humain actif -> réponse systématique. **En groupe :** sélection probabiliste des tours spontanés admissibles : 20 % sur Discord et 30 % sur Twitch, avec exceptions pour les interpellations explicites et les règles de commande, de suivi, de silence, de cooldown et de saturation. Twitch ne voit pas ses spectateurs silencieux via IRC. Le texte Discord maintient un historique des participants actifs du salon sur dix minutes.

**Conservation :** l'inscription est automatique pour les membres identifiés d'un serveur Discord qui échangent avec Jade, sans commande préalable ; Twitch et les MP Discord requièrent toujours `!jade-memoire activer`. La mémoire et sa curation sont activées par défaut sur le runtime réel, sauf paramètres privés contraires. Les réponses livrées sont conservées avec le message utilisateur **en texte intégral**, et non résumées, dans la base SQLite privée. 48 messages récents maximum peuvent être réinjectés à la reprise d'une session. Les messages publics auxquels Jade n'a pas répondu ne sont pas automatiquement archivés par cette fonction. `!jade-memoire oublier` efface uniquement les données issues du compte vérifié qui l'invoque : si ce compte est lié, les autres comptes et leurs souvenirs sont conservés. `!jade-memoire delier` sépare les profils **sans effacer les données**. Les cas anciens où plusieurs comptes d'un même service sont liés peuvent nécessiter une séparation manuelle ; la suppression ne couvre pas les journaux console séparés.

Les **deux variantes faciales et textuelles par intention** sont présentes dans le code r20/PWA. Les **14 motions corporelles originales** restent un projet artistique : [contrat Live2D](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).

## Sauvegardes et incidents (15/11/2026)

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Les versions de schéma mémoire 1, 2 et 3 sont prises en charge par la fonction d'export/import portable, sous réserve des tests du SHA exécuté. L'export ZIP est en clair et peut conserver des données même après leur suppression de Jade : garder les archives hors Git, appliquer une durée de conservation et vérifier les restaurations en environnement isolé. En cas de CI rouge, ne pas considérer la simple présence d'un fichier ou de sa documentation comme une fonctionnalité validée.

Les travaux futurs, sans doublon avec ce guide utilisateur, sont centralisés dans le [catalogue](../ameliorations/README.md).


## Association de comptes à la mémoire personnelle

Lorsque la mémoire est active (par défaut sur le runtime réel), le compte Discord de serveur est automatiquement inscrit lors de sa première interaction traitée ; pour Twitch ou les MP Discord, utiliser `!jade-memoire activer`. Demander ensuite son ID numérique avec `!jade-memoire identite`. Depuis **la PWA privée de Goldaj**, ouvrir « Associer un compte Discord / Twitch », saisir l'**ID numérique** du compte, puis copier la commande `!jade-memoire confirmer <code>` vers le chat **de ce même compte** dans les cinq minutes. La confirmation est à usage unique et liée à cet ID ; elle ne fusionne pas les historiques de salons indépendants. Sur un compte lié, `!jade-memoire oublier` efface uniquement **les données de ce compte**, et `!jade-memoire delier` conserve ses souvenirs mais les sépare. Les données du propriétaire et des autres comptes restent distinctes. Voir [la passation technique du 16 novembre](../operations/handoffs/2026-11-16-chatgpt-pcm-memoire-mobile.md).
