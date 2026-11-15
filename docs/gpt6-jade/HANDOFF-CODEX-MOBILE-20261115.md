# Guide opérationnel : Jade sur Windows et Android (passation à Codex)

**Mise à jour du 15 novembre 2026. Statut : code livré sur \`develop\`, installation réelle non effectuée.**

Ce document est **la procédure courante que Codex doit suivre sur le PC de Goldaj à sa demande**. Il remplace les étapes historiques où la PWA était lancée seule via \`--live --mobile\` et les instructions mentionnant une PR mobile non fusionnée.

## 0. Demande et résultat attendu

Le propriétaire veut, depuis **son PC Windows avec les données et le travail Jade sur D:** :

1. Choisir la branche Git dans le launcher, puis **lancer une seule instance de Jade présente simultanément sur tous ses supports** : Discord écrit/vocal, Twitch, micro du PC, API HTTP locale, PWA Android privée, voix et avatar. Aucun profil ni priorité fixe par support. L'arbitrage de l'ordre des réponses appartient au runtime Jade.
2. Installer une PWA Android réservée à Goldaj. Elle permet d'écrire, de parler avec un bouton microphone, d'entendre la réponse et d'afficher Jade r20 animée au-dessus d'un décor. **Ce n'est pas un APK** et ne nécessite pas le VPS Hyperliquid.
3. Après installation initiale, usage normal : **Jade et Tailscale actifs sur le PC ; Tailscale actif sur Android ; ouverture de l'icône Jade installée dans Chrome**. PC éteint ou Jade arrêtée : service indisponible.
4. Codex doit **faire les manipulations réalisables sur le PC lorsqu'il aura accès**, vérifier les résultats, présenter les opérations nécessitant un compte ou une autorisation humaine et ne pas inventer des succès.

**Références de code :** intégration de la PWA/mémoire/Discord dans \`develop\` (PR #11), launcher Windows (PR #13), correction « tous les supports » et arbitrage (PR #14). \`main\` n'est pas la branche de travail de ce déploiement. Lire aussi [launcher Windows](LAUNCHER-WINDOWS-20261115.md), [audit transverse](AUDIT-TRANSVERSE-20261115.md), et \`AGENTS.md\`. Les anciens journaux de PR #6/#7/#8/#9 décrivent une situation antérieure à la fusion.

## 1. Séquence de reprise obligatoire pour Codex sur le vrai PC

**Phase A, inventaire sans modification :**

- Vérifier que la session est bien celle du PC Jade Windows, le volume \`D:\`, le clone Git existant, l'état \`git status --short --branch\`, les branches et processus Jade éventuels. Ne **pas** écraser des changements de Terra/Codex, lancer un \`reset --hard\`, nettoyer des données uniques, changer \`main\` ou tuer d'autres logiciels.
- Localiser le vrai dépôt Jade, les dossiers privés, le fichier de secrets existant, Python 3.11, Poetry 2.2.1, Git + LFS, FFmpeg/\`ffplay\`, SDK Web Live2D éventuel et installation Tailscale **sur le PC**. Les chemins ci-dessous sont des emplacements cibles, pas une preuve que ces dossiers existent.
- Vérifier les ports et la configuration actuelle avant toute écriture : \`tailscale status\`, \`tailscale serve status\`, \`tailscale version\` et les éventuels ports déjà utilisés (\`8766\` mobile, \`8765\` HTTP local). Ne pas publier dans le chat de tokens, contenu du \`.env\`, transcriptions ou identités tierces.
- Vérifier l'état des accès et autorisations réels (Discord/Twitch/Tailscale/OpenAI) en demandant au propriétaire uniquement l'action qu'il doit effectuer lui-même (connexion, portail, licence), sans recopier ses secrets dans la conversation.

**Phase B, préparation et configuration :** utiliser les étapes 2 à 5 ci-dessous, vérifier chaque commande et conserver la configuration existante si elle fonctionne.

**Phase C, recette PC et Android :** tests hors ligne d'abord, puis démarrage réel **uniquement quand le propriétaire accepte les connexions et appels OpenAI facturables**. Ne pas conclure à la réussite sur la base de CI GitHub : il faut des essais sur les appareils.

**Phase D, passation :** fournir un compte-rendu au propriétaire avec les éléments réellement installés, les vérifications réussies/échouées, la vraie URL privée (si autorisé, jamais le jeton), l'état du Live2D et les actions Android restantes. Ne pas signaler « terminé » si une dépendance ou un test matériel manque.

## 2. Mettre le code et le launcher à jour sur D:

Sur le **clone existant** du PC, vérifier les travaux locaux avant de changer de branche. Si le dépôt est propre et la cible est \`develop\` :

\`\`\`powershell
git status --short --branch
git fetch --prune origin
git switch develop
git merge --ff-only origin/develop
git lfs pull
poetry sync --only main -E all
\`\`\`

Ne jamais remplacer le clone existant ni supposer son chemin. En cas de modifications locales, **ne pas forcer** : présenter le diff et préserver le travail. Les commandes Python se lancent dans le venv Poetry du dépôt. Vérifier les binaires du modèle après LFS (si présent) :

\`\`\`powershell
poetry run python jade-modeling/verify_assets.py
\`\`\`

La première fois **ou après une modification du code du launcher**, double-cliquer \`Installer-Launcher-Jade.cmd\` depuis le dépôt : il installe un lanceur **hors Git**, dans \`D:\Jade\launcher\Lancer-Jade.cmd\`. Il conserve le chemin du fichier privé déjà configuré, mais il faut s'assurer qu'il pointe vers le bon fichier. Il est possible de créer un raccourci Bureau. Le programme ne se met **pas** à jour tout seul lorsque le clone change de branche.

**IMPORTANT :** le launcher actuel ne possède **aucun sélecteur de mode**. La seule commande runtime attendue est \`poetry run python main.py --all-channels\`; préflight : \`poetry run python main.py --preflight --all-channels\`. Tous les canaux sont activés ensemble. Son démarrage est **bloquant si un prérequis obligatoire manque**, au lieu de démarrer silencieusement un sous-ensemble.

## 3. Configurer Tailscale Serve sur le PC et Tailscale Android

1. Installer/ouvrir Tailscale sur **le PC Jade Windows** et l'y connecter, puis installer/ouvrir Tailscale sur **Android** en utilisant le **même tailnet** et un compte utilisateur personnel. Des appareils Tailscale « tagged » ne transmettent pas forcément l'identité utilisateur attendue par cette application.
2. Sur le PC, vérifier les certificats HTTPS du tailnet, MagicDNS, les politiques d'accès et les routes Serve existantes. La CLI récente de Tailscale a changé par rapport aux anciens guides. Sur Windows, utiliser si nécessaire **Windows Terminal / PowerShell en administrateur** pour les commandes Serve. Référence officielle : https://tailscale.com/docs/features/tailscale-serve et https://tailscale.com/docs/reference/tailscale-cli/serve.
3. Sur le **PC Jade seulement**, inspecter sans écraser :

\`\`\`powershell
tailscale version
tailscale status
tailscale serve status
tailscale serve --help
\`\`\`

4. **Uniquement si le PC n'a pas de route Serve incompatible sur le port HTTPS choisi**, ajouter le proxy privé persistant vers le backend Jade sur loopback :

\`\`\`powershell
tailscale serve --bg 8766
tailscale serve status
\`\`\`

Lire l'adresse HTTPS **réellement renvoyée** : généralement \`https://nom-reel-du-pc.nom-reel-du-tailnet.ts.net\`. Si une route existe déjà sur ce PC, choisir une route/port compatible avec la version installée **sans écraser l'existant** et noter l'URL avec son port éventuel. Les routes Tailscale \`:443\`/\`:8443\` du **VPS Hyperliquid sont sur une autre machine** et **ne doivent jamais être modifiées** pour Jade.

5. Vérifier que la configuration est en **Serve privé**, pas en Funnel public. Ne jamais exposer \`0.0.0.0:8766\`, configurer une redirection de box/pare-feu, ou rendre les données mémoire accessibles publiquement. Le service Python reste uniquement sur \`127.0.0.1:8766\`. Tailscale Serve fournit au backend l'en-tête vérifié \`Tailscale-User-Login\`. **Ne pas confondre** le nom de l'appareil et le login réel du compte Tailscale. Dans \`JADE_MOBILE_OWNER_LOGIN\`, saisir le login exact du propriétaire associé au téléphone, typiquement une adresse e-mail ; le code compare cet en-tête exactement (hors casse).
6. Avec \`--bg\`, Serve demeure normalement enregistré après un redémarrage de Tailscale/Windows, mais **Jade elle-même doit être démarrée sur le PC** pour répondre. Vérifier la reconnexion et le comportement après reboot sur le poste réel.

## 4. Secrets et réglages privés de Jade

La configuration est chargée par \`src/utility/private_config.py\`. **Priorité aux variables d'environnement du processus**, puis au fichier \`JADE_SECRETS_FILE\`, puis aux anciens emplacements de compatibilité. Sur le poste actuel, **retrouver le vrai fichier avant de créer une copie**. Si un nouveau fichier est nécessaire, préférer par exemple \`D:\Jade\private\jade.env\`, avec droits restreints et **hors du dépôt Git**. Dans le launcher, renseigner **seulement le chemin** vers ce fichier privé, pas son contenu.

Valeurs exactes à vérifier ou renseigner dans le fichier privé ; les marqueurs entre chevrons sont **des exemples**, ne jamais les laisser comme valeurs réelles :

\`\`\`dotenv
# Services partagés, tous activés par --all-channels :
OPENAI_API_KEY=<cle_ouverte_reelle>
DISCORD_TOKEN=<jeton_discord_existant>
DISCORD_VOICE_CHANNEL=<id_numerique_du_salon>
JADE_TWITCH_ENABLED=1
JADE_TWITCH_SEND=1
TWITCH_CHANNEL=<chaine_twitch>
TWITCH_BOT_LOGIN=<compte_bot_twitch>
TWITCH_TOKEN=<jeton_twitch>
JADE_HTTP_ENABLED=1
JADE_HTTP_TOKEN=<jeton_http_independant_de_32_caracteres_ou_plus>
JADE_AUDIO_OUTPUT=ffplay

# PWA Android privee :
JADE_MOBILE_ENABLED=1
JADE_MOBILE_TOKEN=<jeton_mobile_aleatoire_de_32_a_256_caracteres>
JADE_MOBILE_OWNER_LOGIN=<login_utilisateur_tailscale_exact>
JADE_MOBILE_PUBLIC_ORIGIN=https://<hote_reel>.<tailnet_reel>.ts.net
JADE_MOBILE_PORT=8766
JADE_MOBILE_VENDOR_DIR=D:\Jade\private\mobile-sdk
# Facultatif : sinon le repertoire r20 du depot est utilise
# JADE_MOBILE_MODEL_DIR=D:\chemin_reel_du_clone\jade-modeling\runtime-installed\Jade_professional_r20_idle_complete
\`\`\`

Le client mobile requiert un **jeton distinct** du jeton HTTP local, aléatoire et entre 32 et 256 caractères. Le créer dans le fichier privé avec une génération cryptographiquement sûre, pas dans une PR, un prompt ou un journal. La valeur \`JADE_MOBILE_PUBLIC_ORIGIN\` doit être **l'origine HTTPS Tailscale réelle**, sans slash final ni chemin, avec \`:<port>\` si la route Tailscale choisie l'exige. Le validateur attend un domaine \`.ts.net\`. Attention aux valeurs d'environnement Windows existantes, qui **peuvent prévaloir sur le .env**.

Si la mémoire doit fonctionner, conserver les réglages \`JADE_MEMORY_ENABLED\`, \`JADE_MEMORY_DB_PATH\` et \`JADE_MEMORY_CURATOR_ENABLED\` **déjà choisis**, sans réinitialiser ni écraser la base SQLite ; consulter [la passation mémoire](HANDOFF-CODEX-MEMORY-20261115.md). Le client authentifié mobile et le micro PC sont tous deux associés à l'identité Goldaj. Pour l'avatar autonome, VTube Studio est **facultatif** ; si activé, il doit être effectivement configuré sur le PC. Éviter d'inventer des paramètres d'activation Discord historiques : le runtime actuel utilise \`--all-channels\` et les paramètres de connexion.

## 5. Installer le SDK graphique Web et les ressources r20

Le modèle source Live2D r20 vient du dépôt et de **Git LFS** : \`jade-modeling/runtime-installed/Jade_professional_r20_idle_complete/\`. Vérifier notamment \`Jade.model3.json\`, textures et \`.moc3\` réels, pas des pointeurs LFS.

Le navigateur Android ne peut pas afficher le modèle avec le moteur Live2D Python du PC. Il lui faut sur le PC **trois fichiers JavaScript réels**, servis par Jade depuis un répertoire privé hors Git :

| Fichier requis | Origine et précaution |
| --- | --- |
| \`pixi.min.js\` | PixiJS compatible avec l'adaptateur sélectionné (initialement génération PixiJS 6.x) |
| \`live2dcubismcore.min.js\` | SDK Live2D Cubism Core for Web officiel, acquis suivant sa licence |
| \`cubism4.min.js\` | Adaptateur \`pixi-live2d-display\` pour Cubism 3/4, **non garanti** si le modèle exporté relève de Cubism 5 |

**Codex doit vérifier la version du .moc3 et la compatibilité de la pile graphique AVANT d'installer un faux mélange de versions.** Si Cubism 5 : choisir et tester une pile SDK/adapter cohérente, adapter \`src/jade_runtime/mobile_web/avatar.js\` si nécessaire, et documenter la décision. Ne pas committer les binaires propriétaires dans le dépôt public.

Références : https://docs.live2d.com/en/cubism-sdk-manual/cubism-sdk-for-web/ ; https://www.live2d.com/en/sdk/download/web/ ; https://www.live2d.com/en/sdk/license/ ; https://github.com/guansss/pixi-live2d-display.

Pour copier les trois **fichiers déjà obtenus légalement**, utiliser le script fourni en donnant les véritables chemins :

\`\`\`powershell
.\scripts\setup-jade-mobile-sdk.ps1 -PixiJs "D:\chemin\reel\pixi.min.js" -CubismCoreJs "D:\chemin\reel\live2dcubismcore.min.js" -CubismAdapterJs "D:\chemin\reel\cubism4.min.js" -Destination "D:\Jade\private\mobile-sdk"
\`\`\`

**Attention :** ce script **refuse un répertoire destination non vide** ; ne pas effacer le SDK existant pour le relancer. Il copie, vérifie des tailles plausibles et affiche les sommes SHA-256. Un fichier présent n'est pas à lui seul une validation de compatibilité ou de rendu Android.

**État réel :** le préflight actuel signale le SDK Web et certains fichiers modèle en **information facultative**, donc il peut réussir **sans l'avatar graphique mobile**. Pour considérer le travail terminé, Codex doit tester son affichage sur Android ; chat texte et voix peuvent fonctionner sans lui, mais le résultat complet demandé par le propriétaire ne serait pas atteint.

## 6. Préflight, démarrage puis installation Android

**Tests locaux sans connexion OpenAI, microphone ou facturation :**

\`\`\`powershell
# Dans la session PowerShell de travail, remplacer par le chemin prive REEL :
$env:JADE_SECRETS_FILE = "D:\Jade\private\jade.env"
poetry run python main.py --preflight --all-channels
poetry run python -m compileall -q src main.py
poetry run python -m unittest discover -s tests -v
tailscale serve status
\`\`\`

Vérifier et corriger **tous les diagnostics obligatoires**, y compris les extensions Discord vocal, Twitch en lecture **et en réponse**, la sortie vocale locale \`JADE_AUDIO_OUTPUT=ffplay\`, \`ffmpeg\`, \`ffplay\`, Jetons Discord/Twitch/OpenAI/HTTP/Mobile, les droits du salon vocal et la présence de Tailscale. \`poetry sync --only main -E all\` installe les extras Python attendus. Le préflight ne teste pas les permissions réelles ni l'API distante.

**Démarrage réel, avec accord du propriétaire pour les connexions/API payantes :**

- Double-cliquer \`D:\Jade\launcher\Lancer-Jade.cmd\`, sélectionner la branche \`develop\` (ou celle réellement demandée) puis **« Mettre à jour et lancer toute Jade »**. Le launcher refait Git fetch/fast-forward, LFS, Poetry, préflight, puis démarre le runtime dans une console PowerShell séparée. Si le launcher lui-même vient d'être corrigé, relancer d'abord \`Installer-Launcher-Jade.cmd\` depuis le clone Git à jour.
- Ne pas lancer \`--live --mobile\` en remplacement : ce serait une exécution **partielle**, contraire à la décision produit. Éviter plusieurs instances Jade concurrentes sur les mêmes salons/ports.
- Vérifier que la console reste active et que le service mobile répond **via l'URL HTTPS Serve**. Une requête directe vers \`http://127.0.0.1:8766/\` peut renvoyer **403** : c'est normal, car elle ne transporte pas l'identité Serve.
- Un port serveur mobile \`8766\` ne doit pas être utilisé par une autre application ; l'API HTTP locale distincte utilise \`8765\` par défaut.

**Sur le téléphone Android (actions où Codex guide le propriétaire) :**

1. Installer/ouvrir **Tailscale** depuis Google Play, autoriser le VPN, se connecter au même tailnet que le PC.
2. Ouvrir **Chrome** et saisir l'adresse **HTTPS Serve réelle du PC** ; ne jamais ouvrir un lien public Funnel ou une adresse hypothétique.
3. Dans la fenêtre **« L'espace privé de Jade »**, saisir le \`JADE_MOBILE_TOKEN\` configuré sur le PC. Le jeton reste **uniquement en mémoire de l'onglet** : il faut le saisir à nouveau après rechargement complet ; ne pas le coller dans une URL, un historique ou une capture.
4. Dans le menu \`⋮\` Chrome, sélectionner **« Installer l'application »** ou **« Ajouter à l'écran d'accueil »** selon le menu proposé. Une icône Jade apparaît sur Android ; aucun APK n'est nécessaire.
5. Envoyer un message écrit. Tester **microphone appuyer pour parler, retoucher pour envoyer** (20 s maximum), accorder l'autorisation micro Android ; vérifier lecture audio, expression/bouche et le décor. Le mode « toujours à l'écoute », les interruptions et les notifications push ne sont **pas implémentés**.
6. Tester en Wi-Fi et en réseau mobile avec Tailscale connecté, puis après mise en veille/réouverture et coupure/rétablissement du réseau.

La PWA garde texte et voix dans une même session mobile. La réponse TTS est restituée **sur Android**, sans seconde lecture automatique sur les haut-parleurs du PC, et les souvenirs de Goldaj suivent le profil propriétaire si la mémoire privée est activée.

## 7. Dépannage à faire par Codex

| Symptôme | Vérification / correction |
| --- | --- |
| Launcher bloque avant démarrage | Lire chaque ligne du préflight, la configuration complète \`--all-channels\` et le chemin \`JADE_SECRETS_FILE\`. Ne **pas** masquer un connecteur par un mode partiel. |
| Serve indique une erreur proxy ou le site ne répond pas | Confirmer que Jade écoute réellement \`127.0.0.1:8766\`, que l'URL Serve vise ce port, que le PC n'a pas été arrêté et que les deux appareils sont en ligne Tailscale. |
| **403** dès l'ouverture | Identité \`Tailscale-User-Login\` manquante/différente (mauvais compte, appareil tagged, lien direct au port local, route incorrecte). Sur un POST, une origine HTTPS non autorisée peut aussi produire 403. |
| **401** à l'envoi d'un message | Jeton Bearer de la PWA absent/incorrect, le ressaisir depuis le fichier privé réel ; ne jamais le publier dans les logs. |
| Page affichée, Jade r20 invisible | \`git lfs pull\`, \`.moc3\`, textures, \`JADE_MOBILE_VENDOR_DIR\`, vrais fichiers JS et compatibilité Cubism ; vérifier la console Chrome Android sans fuite de secrets. |
| Microphone refusé / aucune voix | HTTPS valide, permission Chrome/Android, Tailscale, WAV/STT/TTS, bouton « Voix activée », autorisations de capture. La voix continue n'est pas développée. |
| Erreur 404 sur \`/vendor/\` ou \`/model/\` | Fichiers locaux manquants/chemins ou noms invalides ; le SDK sous D: n'est pas automatiquement téléchargé par Poetry. |
| Jade répond sur Discord mais pas sur Android | Le PC doit lancer \`--all-channels\` et la PWA doit joindre le backend privé avec le bon login et jeton ; diagnostiquer la passerelle, pas changer de « profil ». |

## 8. Recette de fin, preuves et limites

Faire constater **sur le matériel réel**, pas seulement dans les tests simulés :

- [ ] Le dépôt, Poetry/SDK/cache et le launcher sont bien sur D:, sans perte de travaux locaux.
- [ ] Le launcher Windows n'a **pas** de sélecteur de mode et lance une seule instance \`--all-channels\`.
- [ ] Discord écrit et vocal, Twitch, micro du PC, HTTP local et mobile sont disponibles simultanément ; répondre depuis plusieurs canaux n'en désactive aucun.
- [ ] L'arbitrage choisit entre plusieurs conversations **sans priorité fixe par plateforme** et les réponses sont délivrées à leurs destinataires légitimes, sans fuite de conversation privée.
- [ ] Tailscale Serve est sur le **PC**, URL HTTPS et login réellement vérifiés, aucune exposition Funnel, aucune modification du VPS.
- [ ] La PWA installée depuis Chrome s'ouvre sous son icône Android, accès réservé à Goldaj, texte puis voix dans le même fil.
- [ ] Le vrai avatar r20 est visible **sans fond vert** sur le décor, joue son idle, cligne des yeux, change d'expression, et sa bouche réagit au son sur Android ; noter précisément ce qui n'est pas vérifié.
- [ ] Le bouton de voix coupée évite un TTS payant côté mobile ; micro Android fonctionne uniquement après autorisation et n'envoie pas de son en arrière-plan.
- [ ] Les tests fonctionnent en Wi-Fi et en connexion mobile, après reconnexion Tailscale, sans double réponse ni données privées dans Git/logs publics.
- [ ] Évaluer coûts et latence réels avec l'accord du propriétaire ; relever les problèmes et ne pas les transformer en succès supposés.

Ne pas annoncer que l'avatar Live2D est compatible avec la version du SDK, que Tailscale est configuré, ou que les identités Android sont correctes avant de l'avoir observé sur la machine. La PWA ne fournit **ni APK**, ni WebRTC vocal continu, ni notifications push, ni fallback via VPS. Le PC doit rester sous tension avec Jade démarrée.

**Fin de mission Codex :** rapport synthétique avec branche/SHA réellement exécuté, services fonctionnels par support, tests faits (automatiques vs matériels), URL privée sans token, lieu du fichier de secrets **sans son contenu**, problèmes ouverts et prochaines interventions humaines. Aucune modification de \`main\`, aucun déploiement de code/proxy sur le VPS Hyperliquid sans autorisation spécifique.
