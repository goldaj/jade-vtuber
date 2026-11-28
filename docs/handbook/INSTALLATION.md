# Installation de Jade depuis un ordinateur neuf : branche develop

## 0. Choisir son objectif

**Démo immédiate pour un visiteur Windows :** Git suffit à cloner (ou télécharger l'archive source), puis double-clic sur `Installer-Demo-Express.cmd`. Aucun Python, Poetry, OpenAI, Discord, Twitch, Live2D ou compte requis ; réponses simulées. Voir [DEMO.md](DEMO.md).

**Exécuter Jade.** Installer Python 3.11, Poetry 2.2.1, Git LFS et FFmpeg/ffplay. Préparer les secrets des connecteurs utilisés et le paquet graphique. Le r21 anime la PWA. Le renderer autonome Windows lancé par `--all-channels` demande encore le paquet r20. Le préflight vérifie les prérequis du parcours sélectionné.

**Installer la PWA Android :** Tailscale sur le **PC Windows Jade** et Android, Tailscale Serve privé sur le PC vers `127.0.0.1:8766`, configuration de Goldaj et SDK Web Live2D acquis selon sa licence. Aucune route publique ni dépendance au VPS trading.

## 1. Poste Windows neuf

Installer : Git for Windows, Git LFS (`git lfs install`), Python 3.11 64 bits, Poetry 2.2.1, FFmpeg incluant `ffmpeg` et `ffplay` sur PATH. Pour le produit réel vocal, vérifier les périphériques micro/audio et les pilotes graphiques. Le rendu r20 Python requiert OpenGL et les extras Live2D, le rendu **Web** Android requiert séparément les SDK JS propriétaires (voir section 4).

~~~powershell
git clone https://github.com/goldaj/jade-vtuber.git
cd jade-vtuber
git switch develop
git lfs pull
py -3.11 -m pip install poetry==2.2.1
poetry --version
poetry sync --only main -E all
poetry run python jade-modeling/verify_assets.py
poetry run python main.py --preflight
poetry run python main.py
~~~

La dernière ligne **est la simulation du moteur en console** : écrire « Bonjour Jade », puis `/exit`. Aucun token ni achat requis pour cette étape. Les ressources Git LFS peuvent être volumineuses ; pour la démo Express seule, les étapes Git LFS/Poetry ne sont pas nécessaires. Sur une machine Linux, la partie console Python peut fonctionner avec les paquets correspondants, mais **le launcher WinForms, la Démo Express et le rendu GPU Windows ne sont pas garantis**.

### Recherche web Tavily, facultative

1. Créer un compte sur [Tavily](https://app.tavily.com/) ; le forfait gratuit suffit pour commencer. Créer une clé de développement dédiée à Jade, conserver sa valeur privée.
2. Dans le **fichier privé** désigné par `JADE_SECRETS_FILE` (jamais dans Git) :

~~~dotenv
JADE_WEB_ENABLED=1
JADE_WEB_PROVIDER=tavily
TAVILY_API_KEY=tvly-VOTRE_CLE_PRIVEE
# Facultatif :
# JADE_WEB_LOG_DIR=D:/Jade/private/jade-web-search
# JADE_WEB_TIMEOUT_SECONDS=8
# JADE_WEB_MAX_PER_TURN=10
~~~

3. Exécuter `poetry run python main.py --preflight` (sans appel Tavily), puis redémarrer Jade. Avec le web activé, **chaque démarrage live** crée immédiatement un fichier `jade-web-search_YYYY-MM-DD_HH-MM-SS_microsecondes+fuseau_pid-XXXX.jsonl` dans `D:/Jade/private/jade-web-search/` (ou `JADE_WEB_LOG_DIR`), même sans recherche. Le chemin exact s'affiche via `web_search_journal_started` dans la console et les logs principaux.
4. Chaque fichier commence par `session_started` puis les appels `started` et leur résultat (`success`/`failed`/`rejected`). Les anciens fichiers sont conservés. Le dossier **n'est jamais envoyé à GitHub** : requêtes, raisons, URL et extraits restent privés. Si `JADE_WEB_LOG_PATH=D:/Jade/private/jade-web-search.jsonl` existe encore dans la configuration, il reste accepté : sa valeur désigne le répertoire voisin `D:/Jade/private/jade-web-search/`, sans écraser ni migrer l'ancien fichier unique.
5. Pour désactiver le web, mettre `JADE_WEB_ENABLED=0` et redémarrer. Pour changer de fournisseur plus tard, ajouter un adaptateur conforme à `SearchProvider` et le déclarer dans `build_web_search_service`, sans modifier l'orchestrateur ni l'outil LLM.

**Aucun paiement ni test externe n'est lancé par le préflight ou la suite de tests.** Le coût des crédits Tavily et celui de la continuation OpenAI ne sont pas confondus. `include_usage` fait remonter les crédits quand Tavily les renvoie.

## 2. Installer le launcher utilisateur Windows

Sur le clone `develop` à jour, double-cliquer `Installer-Launcher-Jade.cmd`. Il installe `D:\Jade\launcher\Lancer-Jade.cmd` **hors du clone Git** (disque D: requis pour ce programme personnalisé). Après une mise à jour du code du launcher, **relancer cet installateur**. Faire un raccourci bureau si souhaité.

Le launcher peut changer de branche distante, fait `git fetch --prune`, refuse un arbre de travail local modifié, récupère les derniers commits seulement en fast-forward, prépare Poetry `-E all` et Git LFS, lance le préflight puis le vrai moteur dans une console séparée. Il n'a plus de menu « mode micro », « mode Discord », etc. Il démarre **`main.py --all-channels`** en une instance. Son démarrage réel est impossible si une dépendance obligatoire échoue au préflight : ne pas désactiver un canal pour contourner cela.

## 3. Préparer les fichiers privés et les services externes

Le programme lit `src/utility/private_config.py` : variables d'environnement prioritaires, puis fichier `JADE_SECRETS_FILE`. Localiser les secrets existants avant de créer quoi que ce soit. Pour un PC **neuf**, créer un dossier privé hors Git, avec permissions utilisateur, par exemple `D:\Jade\private\jade.env`, et l'indiquer dans le champ du launcher. Ne jamais committer les clés.

Exemple de **noms à renseigner** (les marqueurs entre chevrons ne sont pas des valeurs valides) :

~~~dotenv
OPENAI_API_KEY=<cle_api_openai>
DISCORD_TOKEN=<token_discord>
DISCORD_VOICE_CHANNEL=<identifiant_numerique_du_salon>
JADE_TWITCH_ENABLED=1
JADE_TWITCH_SEND=1
TWITCH_CHANNEL=<salon_twitch>
TWITCH_TOKEN=<token_twitch>
TWITCH_BOT_LOGIN=<compte_bot_si_necessaire>
JADE_AUDIO_OUTPUT=ffplay
JADE_HTTP_ENABLED=1
JADE_HTTP_TOKEN=<secret_http_32_caracteres_minimum>
JADE_MOBILE_ENABLED=1
JADE_MOBILE_TOKEN=<secret_mobile_different_de_32_a_256_caracteres>
JADE_MOBILE_OWNER_LOGIN=<identite_tailscale_exacte>
JADE_MOBILE_PUBLIC_ORIGIN=https://<nom_reel_pc>.<nom_reel_tailnet>.ts.net
JADE_MOBILE_PORT=8766
JADE_MOBILE_VENDOR_DIR=D:\Jade\private\mobile-sdk
~~~

Les valeurs ci-dessus proviennent des champs de `Settings.load()` et du contrat de démarrage global. Les secrets HTTP et mobile **doivent être différents**. VTube Studio est **facultatif** et ne remplace pas l'avatar autonome ; pour l'activer, configurer `JADE_VTS_ENABLED=1` et son jeton local. La mémoire SQLite et sa curation sont activées par défaut en mode réel ; sans `JADE_MEMORY_DB_PATH`, Jade utilise `D:\\Jade\\private\\jade-memory.sqlite3` si le lecteur D: Windows est présent, sinon `~/.jade/jade-memory.sqlite3`. Les dossiers et tables sont créés au lancement réel, jamais pendant la démo hors ligne. `JADE_MEMORY_ENABLED=0` ou `JADE_MEMORY_CURATOR_ENABLED=0` dans un fichier privé restent prioritaires. Conserver le chemin d'une éventuelle ancienne base pour éviter une mémoire apparemment vide. Informer les membres Discord de la conservation avant leur participation et de la commande `!jade-memoire oublier`.

## 4. Configurer Android privé et le Live2D Web

Installer **Tailscale sur le PC et sur le téléphone Android**, les connecter au même tailnet et vérifier les règles d'accès. Sur le **PC** uniquement :

~~~powershell
tailscale status
tailscale serve status
tailscale serve --help
# Seulement si aucune route HTTPS existante n'est écrasée :
tailscale serve --bg 8766
tailscale serve status
~~~

Lire **l'adresse réelle** HTTPS du PC retournée par Serve, la copier dans `JADE_MOBILE_PUBLIC_ORIGIN` sans slash final. Le serveur Python mobile écoute `127.0.0.1:8766` et exige l'identité `Tailscale-User-Login` plus le token Bearer. **Ne jamais activer Tailscale Funnel, ouvrir de port public, ou déplacer Jade sur le VPS Hyperliquid.** Une URL fictive ne fonctionnera pas.

Les modèles sont distribués par Git LFS. Le r21 s’affiche par défaut sur la PWA, avec ses ressources mobiles v49.1. Installer les quatre fichiers du SDK Web dans un répertoire privé sur D:. Utiliser PixiJS 6.5.10 (`pixi.min.js`), le bundle navigateur `@pixi/unsafe-eval` 6.5.10 (renommé `pixi-unsafe-eval.min.js`), le Core du ZIP Cubism SDK Web 5-r.5 (`live2dcubismcore.min.js`) et pixi-live2d-display 0.4.0 (`cubism4.min.js`). Le bundle Pixi évite la compilation JavaScript dynamique. Le script `scripts/setup-jade-mobile-sdk.ps1` reçoit le bundle Pixi supplémentaire avec `-PixiCspJs`. Sur une installation existante, ajouter ce fichier au dossier SDK configuré.

## 5. Vérifications avant démarrage réel

~~~powershell
# Remplacer par le chemin réel du PC, sans afficher le contenu du fichier :
$env:JADE_SECRETS_FILE = 'D:\Jade\private\jade.env'
poetry run python -m compileall -q src main.py
poetry run python -m unittest discover -s tests -v
poetry run python main.py --preflight --all-channels
~~~

Le préflight ne fait **aucune connexion OpenAI/Discord/Twitch**, ne capte pas le micro et ne démontre pas l'accessibilité réelle de la PWA ; il contrôle les prérequis logiciels et la validité statique. **Si un composant obligatoire échoue, réparer la configuration au lieu de retirer sa présence du lancement global.**

Après accord explicite pour les appels API potentiellement facturés : lancer `D:\Jade\launcher\Lancer-Jade.cmd` et sélectionner `develop`. Sur Android, avec Tailscale actif, ouvrir l'URL HTTPS Serve réelle dans Chrome, saisir le jeton mobile dans l'interface puis menu `⋮` → « Installer l'application » / « Ajouter à l'écran d'accueil ». Une icône est créée ; **aucun APK nécessaire**. Le jeton n'est pas sauvegardé par la PWA et doit être ressaisi après rechargement complet.

Tester la conversation écrite et vocale, le Live par appui sur le micro, la voix classique par maintien, le rendu r21 et la reprise réseau sur Wi-Fi et données mobiles. Le navigateur Android peut demander la permission du microphone. La PWA dépend du PC Windows où Jade tourne.

## 6. Dépannage et déploiement fiable

| Problème | Diagnostic |
| --- | --- |
| Launcher refuse de démarrer | Lire `--preflight --all-channels` : fichier de secrets, ffplay, SDK et droits ; ne pas sélectionner un sous-ensemble |
| PWA 403 dès l'ouverture | Identité propriétaire Tailscale manquante/différente, mauvais compte/route ou accès direct sans Serve |
| PWA 401 sur un message | Token Bearer mobile invalide/oublié, différent du token HTTP |
| Page visible, avatar absent | Git LFS, `.moc3`, JS Web locaux, licences et compatibilité Cubism |
| Serve inaccessible | Jade non lancée, proxy Serve vers mauvais port, PC/Android hors tailnet |
| Twitch reçoit mais ne répond pas | Vérifier `JADE_TWITCH_SEND=1` et autorisations réelles |
| Voix muette sur PC | `JADE_AUDIO_OUTPUT=ffplay`, `ffplay`, pilote et micro/permissions |

Pour une **intervention sur le PC réel avec Codex**, suivre impérativement [la procédure complète de passation](../history/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md) : inventaire d'abord, aucune destruction des données existantes, détails d'authentification et recette humaine. **Aucune installation matérielle ne peut être déduite d'une CI verte**.

## Rendu émotionnel et réglages du dialogue

`JADE_AVATAR_INTENT_ENABLED=1` autorise les réactions visuelles par défaut. Avec `0`, la voix, le mouvement de bouche et l’Idle restent actifs. Redémarrer Jade puis recharger la PWA après une modification de la configuration privée. Sur l’URL Tailscale privée, `/assets/intent-visuals.json` expose le statut dans `enabled`. Le r21 de la PWA joue deux mouvements par intention pour neuf intentions. La recette graphique et vocale est suivie dans REC-053. [Rendu r21](BRANCH_STATE.md#intentions-triste-et-colère-sur-r21-27112026)

Les réglages usuels sont `JADE_LLM_MODEL=gpt-6-luna`, `JADE_LLM_REASONING_EFFORT=low`, `JADE_MAX_COMPLETION_TOKENS=2048` et `JADE_HISTORY_LIMIT=48`. Le dernier borne l’historique volatil. La mémoire SQLite et la curation s’activent par défaut en mode réel. Discord inscrit automatiquement les comptes vérifiés en serveur, en vocal et en message privé, à la première interaction traitée. Twitch conserve son activation par commande. [Utilisation de la mémoire](USER_GUIDE.md#10-mémoire-persistante-et-core-memories)

Sauvegarder la base privée avant une mise à niveau. Le schéma SQLite courant est v8. Les échanges bruts expirent après 7 jours, les souvenirs ordinaires après 365 jours. Les Core Memories sont conservées jusqu’à une suppression. Jade reprend les 24 dernières heures d’une conversation vérifiée et sélectionne les éléments utiles au modèle. La recherche de souvenirs couvre tous ses comptes et canaux. [Contrat mémoire](TECHNICAL.md#4-mémoire-persistante-identité-et-autobiographie)

## Contrôle DevOps avant utilisation réelle (15/11/2026)

La sauvegarde SQLite accepte les schémas 1 à 8. Conserver le ZIP en clair sur un stockage privé chiffré et éprouver la restauration sur une base de test. Réinstaller le launcher dans `D:\Jade\launcher` après une modification de ses scripts. Utiliser le préflight local puis la recette adaptée au poste. [Revue DevOps historique](../history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md)

Les corrections historiques de CI sont conservées dans [l'audit DevOps](../history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Pour l'état actuel des fonctions codées : [BRANCH_STATE.md](BRANCH_STATE.md).

## Suivi des dépenses OpenAI sur mobile

Configuration et limites : [guide des dépenses OpenAI](../operations/reference/OPENAI-COSTS.md).


## DEV-036 · Rappels persistants et push Android (22/11/2026)

**Architecture :** les rappels sont stockés côté PC dans le fichier privé jade-reminders.sqlite3 (voisin du chemin JADE_MEMORY_DB_PATH). Un ordonnanceur léger fonctionne tant que Jade est lancée avec le connecteur mobile/Discord ; aucun token OpenAI n'est utilisé pour déclencher une échéance. L'application Android ne reste pas active : le Service Worker est réveillé ponctuellement par les notifications push.

**Préparation unique sur le PC :** dans le même environnement Poetry que Jade, installer la bibliothèque de transport Web Push maintenue (module Python pywebpush, avec py-vapid). Elle n'est pas intégrée au verrou Poetry actuel : un environnement neuf exige donc cette installation facultative explicite avant que push soit déclaré prêt.

~~~powershell
poetry run python -m pip install pywebpush
poetry run python scripts/setup_web_push.py --directory D:/Jade/private
~~~

Le script refuse d'écraser une clé privée déjà existante. Il affiche **la clé publique** et le chemin du PEM privé, mais jamais le contenu de la clé privée. Dans JADE_SECRETS_FILE, renseigner exactement JADE_PUSH_VAPID_PUBLIC_KEY (clé retournée), JADE_PUSH_VAPID_PRIVATE_KEY (chemin absolu du PEM) et JADE_PUSH_VAPID_SUBJECT (un contact valide du type mailto:adresse@example.com). **Ne jamais committer ce PEM ni publier les subscriptions push.** Garder la même paire VAPID pendant toute la durée d'utilisation des abonnements ; une rotation exige une nouvelle inscription des téléphones.

**Activation Android :** redémarrer Jade avec --live --mobile ou --all-channels, vérifier le VPN Tailscale et la PWA installée sur son URL HTTPS privée, puis ouvrir « Rappels et notifications » et toucher « Activer les notifications ». Accepter la permission Android/navigateur. La PWA transmet au PC la subscription chiffrée par le navigateur via l'API authentifiée ; la réception à écran fermé est assurée par l'OS et le fournisseur push compatible, non par un socket/timer vivant dans la page. Toucher la notification ouvre/focalise Jade, puis nécessite à nouveau le jeton privé pour lire le titre.

**Recette sur le vrai téléphone :** créer un rappel à deux minutes via le panneau ou la conversation. Tester (a) PWA ouverte, (b) PWA quittée normalement, (c) téléphone verrouillé ; vérifier l'affichage système, l'ouverture du bon rappel, puis reporter et annuler. Redémarrer Jade avant une échéance et après une échéance ; contrôler les statuts. Tester également un rappel Discord dans le canal autorisé après association du compte, et la révocation des permissions. Ne jamais appeler un succès de transport « affiché sur l'écran » sans observation réelle.

**Limites :** PC arrêté = aucun envoi jusqu'à sa reprise ; hors ligne/économiseur Android/arrêt forcé/permissions désactivées peuvent empêcher l'affichage. Les retries du serveur sont limités à 12 tentatives, et un succès signifie acceptation par un fournisseur push, pas preuve de lecture. Les notifications sont génériques, ne contiennent aucun texte privé dans le payload et ne nécessitent pas de micro ou de LLM actif. Pas de connexion Google Calendar/Outlook ni de récurrence pour DEV-036.
