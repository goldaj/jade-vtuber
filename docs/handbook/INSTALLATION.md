# Installation de Jade depuis un ordinateur neuf : branche develop

## 0. Choisir son objectif

**Démo immédiate pour un visiteur Windows :** Git suffit à cloner (ou télécharger l'archive source), puis double-clic sur `Installer-Demo-Express.cmd`. Aucun Python, Poetry, OpenAI, Discord, Twitch, Live2D ou compte requis ; réponses simulées. Voir [DEMO.md](DEMO.md).

**Exécuter le produit Jade complet :** nécessite Python 3.11 + Poetry 2.2.1, Git LFS, FFmpeg/ffplay, une configuration privée de **tous les connecteurs**, les ressources graphiques r20 et un accès aux services externes. Ne pas comparer l'installation d'une démo Express avec le déploiement réel, qui est forcément plus exigeant.

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
2. Dans le **fichier privé** désigné par \`JADE_SECRETS_FILE\` (jamais dans Git) :

~~~dotenv
JADE_WEB_ENABLED=1
JADE_WEB_PROVIDER=tavily
TAVILY_API_KEY=tvly-VOTRE_CLE_PRIVEE
# Facultatif :
# JADE_WEB_LOG_PATH=D:/Jade/private/jade-web-search.jsonl
# JADE_WEB_TIMEOUT_SECONDS=8
# JADE_WEB_MAX_PER_TURN=3
~~~

3. Exécuter \`poetry run python main.py --preflight\` (vérification locale **sans requête** Tavily), puis redémarrer le runtime réel. Pour une recherche réellement confirmée, demander en Discord ou dans la PWA un fait d'actualité et regarder \`D:\Jade\private\jade-web-search.jsonl\` ou le chemin \`JADE_WEB_LOG_PATH\`.
4. Le journal n'est **jamais envoyé à GitHub**. Chaque recherche possède une ligne \`started\` puis une ligne \`success\` ou \`failed\`. Un \`started\` isolé indique notamment un éventuel arrêt brutal. Les résultats contenus dans le fichier peuvent contenir du texte protégé ou sensible issu des pages : le conserver privé.
5. Pour désactiver le web, mettre \`JADE_WEB_ENABLED=0\` et redémarrer. Pour changer de fournisseur plus tard, ajouter un adaptateur conforme à \`SearchProvider\` et le déclarer dans \`build_web_search_service\`, sans modifier l'orchestrateur ni l'outil LLM.

**Aucun paiement ni test externe n'est lancé par le préflight ou la suite de tests.** Le coût des crédits Tavily et celui de la continuation OpenAI ne sont pas confondus. \`include_usage\` fait remonter les crédits quand Tavily les renvoie.

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

Le modèle r20 fournit le .moc3 et les textures via Git LFS. Installer quatre fichiers dans le dossier privé du SDK Web sur D:. Utiliser PixiJS 6.5.10 (pixi.min.js), le bundle navigateur @pixi/unsafe-eval 6.5.10 (à renommer pixi-unsafe-eval.min.js), le Core du ZIP Cubism SDK Web 5-r.5 (live2dcubismcore.min.js) et pixi-live2d-display 0.4.0 (cubism4.min.js). Le bundle Pixi remplace la compilation JavaScript dynamique. Le client Jade raccorde l'ordre de rendu Core 6 pour le modèle r20. Les bibliothèques restent hors Git. Pour une installation neuve, scripts/setup-jade-mobile-sdk.ps1 prend le bundle Pixi supplémentaire avec -PixiCspJs. Sur une installation existante, ajouter ce seul fichier au dossier du SDK déjà configuré.

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

Tester Wi-Fi et données mobiles, échange écrit/voix « appuyer pour parler », restitution TTS dans le téléphone, animation réelle r20, reprise réseau et fonctionnement parallèle des autres canaux. Le navigateur Android peut demander la permission microphone. Sans PC allumé, aucun service mobile.

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

## Mise à jour du rendu émotionnel Live2D (15/11/2026)

Dans le fichier privé `JADE_SECRETS_FILE`, le réglage `JADE_AVATAR_INTENT_ENABLED=1` (valeur par défaut) autorise l'avatar Windows et la PWA Android à réagir à `Reply.intent`. `0` désactive uniquement les réactions visuelles/textuelles émotionnelles ; la voix, la bouche et l'Idle continuent. **Redémarrer Jade et recharger la PWA** après changement. Vérifier que `/assets/intent-visuals.json` est servi sur l'URL Tailscale privée ; sa propriété `enabled` reflète le réglage. Le contrat JSON public ne contient aucun secret. Ne jamais désactiver les contrôles d'accès de la PWA pour le diagnostiquer. Les expressions viennent de r20 installé par Git LFS et dépendent des SDK et GPU. Aucun nouveau fichier d'animation corporelle n'est livré. Recette concrète et suite obligatoire : [passation Live2D](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).

## Réglages de dialogue et conservation (develop, 15 novembre 2026)

Dans la configuration privée, `JADE_LLM_MODEL=gpt-6-luna`, `JADE_LLM_REASONING_EFFORT=low`, `JADE_MAX_COMPLETION_TOKENS=320` et `JADE_HISTORY_LIMIT=48` restent configurables. La mémoire et la curation sont désormais actives par défaut en mode réel, avec chemin SQLite privé automatique. Les échanges de serveur Discord traités par Jade inscrivent automatiquement un compte vérifié ; les MP Discord et Twitch restent sur `!jade-memoire activer`. Sur Discord, `!jade-memoire oublier` efface les données du compte et empêche toute réinscription automatique ; seul `!jade-memoire activer` la rétablit. Ne pas stocker la base SQLite privée dans Git.

Le schéma mémoire passe à **v4** pour la politique de rétention : **sauvegarder le fichier SQLite avant la première ouverture** car les anciennes versions de Jade peuvent refuser la base migrée. Au lancement, le nettoyage supprime les conversations brutes de plus de **7 jours** et les souvenirs ordinaires dont les **365 jours depuis leur création** sont écoulés. Il conserve les Core Memories sans purge temporelle. Les anciennes échéances ordinaires de 90 jours sont recalculées à 365 jours depuis la date d'origine, sans faire réapparaître les entrées déjà purgées. En fonctionnement réel, la purge est répétée chaque heure. À la reprise, tous les échanges des dernières **24 heures** pour la même personne et le même salon sont rechargés sans nombre maximum ; attention aux plafonds de tokens du modèle si le volume est important. Les autres utilisateurs et salons restent isolés.

Avant la recette réelle, lancer `poetry run python -m unittest discover -s tests -v` puis `poetry run python main.py --preflight`. Voir [détails et limites](../history/gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md). Aucun nouveau rig ou asset d'animation 2D n'est nécessaire pour ces réglages.

## Contrôle DevOps avant utilisation réelle (15/11/2026)

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Exécuter localement les tests et préflights décrits dans le guide technique. Le backup de mémoire SQLite supporte les schémas 1, 2, 3 et 4, mais l'archive ZIP n'est **pas chiffrée** : la déplacer uniquement via un support chiffré et vérifier la restauration sur une base de test. Le launcher copié dans `D:\Jade\launcher` doit être **réinstallé** après toute modification de ses scripts ; pas de mise à jour automatique garantie. Les tests de GitHub Actions n'établissent pas le fonctionnement du PC réel.

Les corrections historiques de CI sont conservées dans [l'audit DevOps](../history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Pour l'état actuel des fonctions codées : [BRANCH_STATE.md](BRANCH_STATE.md).

## Suivi des dépenses OpenAI sur mobile

Configuration et limites : [guide des dépenses OpenAI](../operations/reference/OPENAI-COSTS.md).
