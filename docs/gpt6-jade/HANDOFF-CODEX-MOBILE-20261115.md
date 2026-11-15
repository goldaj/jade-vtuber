# Jade Mobile : client privé Goldaj, architecture et passation Codex
**Date : 15 novembre 2026. Branche : `feat/jade-private-mobile-pwa-20261115`. PR vers `develop` ; aucune fusion dans `develop` ou `main` sans revue.**

## 1. Choix retenu et périmètre livré

**PWA installable sur Android + Live2D Web transparent + transport HTTPS privé via Tailscale Serve directement du téléphone au PC Windows qui fait tourner Jade.** La PWA reste un client : le LLM, le STT, le TTS, les intentions et la mémoire sont calculés par le runtime Python du PC, non par le téléphone ou le VPS.

C'est volontairement distinct du VPS Hyperliquid. Le dépôt de trading indique déjà que Tailscale Serve est utilisé sur ce VPS pour l'IA :443 et le dashboard :8443. **Aucune route ni configuration de ce VPS n'est modifiée par ce chantier.** L'autre solution étudiée, streaming de la fenêtre Windows en vidéo, a été écartée du trajet principal car plus coûteuse en bande passante et en latence. Le rendu Live2D dans le navigateur n'a pas besoin de « chroma key » ; l'alpha du canvas laisse apparaître le décor CSS derrière Jade.

### Ce qui fonctionne dans le code, en mode opt-in

- `main.py --live --mobile` lance un serveur distinct sur **`127.0.0.1:8766` par défaut**, sans ouvrir de port vers Internet. `JADE_MOBILE_TOKEN` est différent de `JADE_HTTP_TOKEN` ; jeton de 32 à 256 caractères requis et transmis en Bearer, jamais en URL, cookie ou stockage local du navigateur.
- Interface visuelle PWA : décor chaleureux et animable par CSS, texte et microphone, sous-titres de dialogue, sélection de la synthèse vocale, nouvelle discussion, mode plein écran, couleurs adaptatives, manifest/icône SVG, service worker **sans cache privé**. Fichiers dans `src/jade_runtime/mobile_web/`.
- `GET /` sert le client ; `GET /assets/*`, `GET /vendor/*` et `GET /model/*` sont des ressources en lecture seule, limitées à une whitelist. Le modèle r20 est servi à partir de son répertoire existant après un vrai `git lfs pull`.
- `POST /api/chat` reçoit `{text,session,speak}` ; `POST /api/voice` reçoit un court WAV mono PCM16/16 kHz produit dans le navigateur. Pas d'enregistrement WAV sur disque : octets en RAM, envoyés au service STT OpenAI existant, puis au dialogue Jade et au TTS OpenAI pour une réponse vocale.
- Les réponses portent `reply`, `intent`, `transcript` (voix uniquement), `audio_wav_b64` facultatif. Le client décode le WAV, le joue sur Android et anime approximativement la bouche d'après l'amplitude du son réellement lu.
- Les deux entrées appartiennent à **Goldaj, créateur et père de Jade** : `Incoming(platform="mobile", author="Goldaj", input_modality="text"|"voice")`. La même `session` logique est conservée entre voix et texte sur ce client, à la différence de la fusion Discord multicanal qui reste un autre chantier. Le rôle de Goldaj est ajouté au contexte *uniquement pour la plateforme mobile produite par le serveur authentifié*.
- L'intention `[INTENT:...]` est toujours parsée/supprimée par le moteur actuel ; le client lit `Reply.intent`. Le traitement TTS du mobile n'envoie **pas** une seconde lecture à `ffplay` ni à VTube Studio sur PC.
- Modes : le micro est initialement **appuyer pour parler, toucher à nouveau pour envoyer** (20 secondes maximum). Un mode voix continue, interruptions/barge-in et audio streaming temps réel ne sont **pas encore livrés** ; le code ne prétend pas les réaliser.

### Dépendance graphique : SDK Web Cubism

Le SDK Live2D Web requiert son moteur **Cubism Core propriétaire**. Pour éviter de publier un composant dont la redistribution est encadrée, **aucun `live2dcubismcore.min.js` ni bundle tiers n'est intégré au dépôt**. La PWA tente de charger trois fichiers sur le PC Jade, dans un dossier privé hors Git :

| Nom dans le dossier privé | Provenance |
| --- | --- |
| `pixi.min.js` | PixiJS 6.x, version de la génération compatible avec l'adaptateur |
| `live2dcubismcore.min.js` | Téléchargement officiel Live2D Cubism SDK for Web, après acceptation de la licence |
| `cubism4.min.js` | `pixi-live2d-display`, bundle Web Cubism 4 compatible avec Cubism 3/4 ; compatibilité avec l'export r20 Cubism 5 **à tester** |

Exemple local : `D:\Jade\private\mobile-sdk\`. Le script `scripts/setup-jade-mobile-sdk.ps1` copie les trois fichiers **déjà acquis** vers ce dossier et affiche leur SHA-256. Vérifier d'abord leurs licences et leur provenance : script volontairement non téléchargeur.

Lorsque les bibliothèques manquent ou que le modèle r20 ne se charge pas, le décor et le chat restent disponibles, **mais l'avatar Live2D n'est pas dessiné** ; un message explicite signale la limite. C'est une dégradation contrôlée, pas une preuve de rendu réussi. Le model3.json r20 ne déclarant pas le mouvement Idle pourtant présent, le serveur ajoute virtuellement sa référence sans modifier le fichier source du modèle.

Sources des licences et SDK :
- https://docs.live2d.com/en/cubism-sdk-manual/cubism-sdk-for-web/
- https://www.live2d.com/en/sdk/download/web/
- https://github.com/guansss/pixi-live2d-display
- https://www.live2d.com/en/sdk/license/

## 2. Installation sur le PC Windows, sans toucher au VPS

**Ne lancer aucune commande de ce guide depuis le VPS Hyperliquid.** Le serveur Jade tourne sur ton PC Windows, avec tous les fichiers de travail sur **D:**. Vérifier les branches et processus locaux avant toute reprise.

1. Travailler sur la PR mobile, vérifier les éventuels travaux Codex/Terra en parallèle et installer les dépendances Python déjà utilisées par Jade.
2. Restaurer les binaires Live2D locaux : `git lfs pull`, puis `python jade-modeling/verify_assets.py`. Le package r20 se trouve dans `jade-modeling/runtime-installed/Jade_professional_r20_idle_complete/`. Ses images et le `.moc3` sont enregistrés via Git LFS et peuvent apparaître comme des pointeurs sans les objets.
3. Télécharger/acquérir légalement les trois bibliothèques Web Live2D sur le PC, vérifier qu'elles fonctionnent avec la version r20, puis copier vers un dossier privé sous D: à l'aide du script (ou manuellement). Ni ce SDK ni ses fichiers binaires ne doivent être committés sur GitHub.
4. Inscrire les valeurs suivantes dans le **fichier de configuration privé** Jade (pas dans `.env.example` versionné pour les secrets) :

```dotenv
# Exemple : adapter au vrai chemin de ton poste, ne pas recopier un jeton dans Git.
JADE_MOBILE_ENABLED=1
JADE_MOBILE_TOKEN=<jeton aleatoire prive d'au moins 32 caracteres>
JADE_MOBILE_OWNER_LOGIN=<identifiant de connexion Tailscale du propriétaire>
JADE_MOBILE_PORT=8766
JADE_MOBILE_VENDOR_DIR=D:\Jade\private\mobile-sdk
# Optionnel, sinon le package r20 du depot est utilise :
JADE_MOBILE_MODEL_DIR=D:\Jade\jade-vtuber\jade-modeling\runtime-installed\Jade_professional_r20_idle_complete
```

5. Tester **sans connexion ni facturation** :

```powershell
python main.py --preflight --live --mobile
python -m compileall -q src main.py
python -m unittest discover -s tests -v
```

6. Puis, **après ton autorisation pour les appels OpenAI facturés**, lancer depuis le PC :

```powershell
python main.py --live --mobile
```

Le client local sera accessible sur `http://127.0.0.1:8766/` pour la vérification du rendu sur le PC. `--voice` n'est **pas nécessaire** pour la voix mobile, puisque la passerelle utilise directement le même TTS et renvoie le WAV au navigateur. Éviter d'activer simultanément `--http` sur le même port ; la config l'interdit.

### Accès Android par Tailscale Serve

Vérifier que le PC et le téléphone sont connectés au **même tailnet**, que les autorisations limitent ce nouveau service à ton compte/appareil et que les certificats HTTPS fonctionnent. Depuis le PC Jade uniquement :

```powershell
tailscale serve status
# Si le port HTTPS par defaut du PC est disponible et sans route existante :
tailscale serve --bg 8766
tailscale serve status
```

La commande fournit normalement une URL privée `https://<nom-du-pc>.<tailnet>.ts.net/`. **Ne pas inventer d'adresse : lire celle réellement affichée sur ton PC.** Si Serve possède déjà une route, choisir une route distincte avec la version de CLI installée, plutôt que remplacer une application existante. Les ports :443 et :8443 du **VPS Hyperliquid** ne sont pas concernés, puisqu'il s'agit d'un autre appareil Tailscale.

Ouvrir cette URL HTTPS sur Android Chrome, puis « Ajouter à l'écran d'accueil » ou « Installer l'application ». Saisir le jeton privé du client mobile dans l'écran d'accès. La page **ne le stocke pas** : il faudra le ressaisir au rechargement complet. Autoriser le microphone Android à la demande et vérifier les paramètres d'absence d'écho.

**Interdictions :** Tailscale Funnel, ouverture d'un port public, bind `0.0.0.0`, hébergement de la mémoire SQLite sur le VPS trading, collage du jeton dans l'URL, déploiement d'un SDK propriétaire dans un dépôt public.

## 3. Isolation, limites et contrats à préserver

- Le serveur HTTP est limité à `127.0.0.1` ; chaque requête de conversation doit présenter le jeton Bearer. Il n'y a pas de cookie, de CORS, d'analytics, de fonts distantes ni d'exposition du moteur OpenAI au téléphone.
- L'identité Goldaj est **attribuée par la passerelle authentifiée et privée**, pas par un pseudo reçu de Discord ou Twitch. Dans cette PR, la session vocale/texte mobile est unifiée ; **la mémoire SQLite durable de la PR #6 n'est pas encore intégrée** et Codex devra réconcilier explicitement `mobile:Goldaj` avec `microphone:Goldaj` sans créer un double profil et sans affaiblir la reconnaissance des tiers.
- Le dossier `/model` ne sert que les fichiers listés par le modèle ; les SDK tiers locaux sont servis en lecture seule sous `/vendor`. Il n'y a pas de cache Service Worker des données privées. **Les assets statiques ne sont pas sous Bearer** afin que Live2D puisse charger ses dépendances depuis un navigateur ; leur confidentialité repose sur le tailnet privé et les règles d'accès.
- Les messages peuvent figurer dans les logs `jade.conversation` existants, mais la passerelle n'enregistre pas les WAV/transcriptions sur disque. Il faut gérer séparément la politique de conservation des logs.
- Limites actuelles : pas de streaming PCM/WebRTC, pas de reprise fiable de lecture lors d'une perte réseau, aucune notification push, pas d'APK Android généré, pas de mode toujours à l'écoute, pas de visuel Live2D validé sur un téléphone réel. Une PWA installable suffit à l'objectif de **client dédié V1**, l'APK étant une option ultérieure.
- Le modèle Jade reste sur le PC : **PC éteint = Jade indisponible**, même si le VPS trading fonctionne.
- Le chargeur `pixi-live2d-display` est une intégration de SDK à tester sur l'export r20 Cubism 5 ; si incompatible, remplacer l'adaptateur graphique ou employer le SDK Web officiel. Ne pas présenter son rendu comme déjà vérifié.

## 4. Tests de reprise pour Codex

Les tests présents dans `tests/test_jade_mobile_gateway.py` couvrent hors ligne : jeton et origine, conversation texte suivie de voix dans un même fil, identité Goldaj, réponse TTS WAV mockée, parsing de WAV et limites, routes statiques, sources du modèle en liste blanche, injection virtuelle du mouvement Idle, et syntaxe JS si Node est installé.

**Validation physique obligatoire** avant fusion en production :
1. Ouvrir la PWA sur ton Android, constater que le modèle **Jade r20 réel** s'affiche sans fond vert, repos/idle, Blink, expression et bouche articulée sans caméra.
2. Couper le réseau, rouvrir, vérifier que la session échoue proprement sans enregistrer le jeton ; reconnecter Tailscale.
3. Écrire « Salut Jade », puis appuyer pour parler « tu te souviens de ce que je viens de dire ? » : même fil, voix restituée **une fois** dans le téléphone, pas sur les haut-parleurs du PC.
4. Mesurer premier son et durée totale, Android en Wi-Fi puis mobile, et tester expiration du STT, TTS indisponible, refus microphone, perte du modèle.
5. Vérifier que seul ton compte/device Tailscale peut consulter l'interface, aucun port n'est rendu public, aucune modification de la route VPS trading.
6. Avec PR #6 intégrée et validée, vérifier que les **souvenirs Goldaj sont réellement partagés** micro PC / micro mobile / texte mobile, puis seulement y activer la curation Core. Le code de cette PR ne l'affirme pas.
7. Vérifier Tailscale Serve au reboot PC si souhaité ; ne pas confondre un test de connexion ponctuel avec un service toujours disponible.

## 5. Reprise future, priorités produit

**Phase 2 (Codex)** : conserver le rendu Live2D mobile après inspection d'une version Cubism Web vérifiée, normaliser animations/expression selon les sept intentions, affiner le lip-sync et la lecture audio sur Android. Ajouter un transport audio faible latence en streaming avec WebSocket/WebRTC et un vrai duplex, gestion d'interruption/barge-in, état audio/texte robuste, reconnexion et wake lock contrôlé.

**Phase 3** : harmoniser la mémoire propriétaire avec PR #6 et la conversation Discord texte/vocal unifiée déjà réservée à Codex dans `IDEE-CONVERSATION-UNIFIEE-20261115.md`, sans divulgation des conversations privées. Décider ensuite seulement si un APK encapsulant la PWA apporte un gain concret.

**Fichiers d'entrée à lire** : `AGENTS.md`, `main.py`, `src/jade_runtime/mobile_gateway.py`, `src/jade_runtime/mobile_web/{index.html,app.js,avatar.js,styles.css}`, `src/jade_runtime/dialogue.py`, `src/jade_runtime/messages.py`, `src/jade_runtime/openai_services.py`, `src/jade_runtime/turn_logging.py`, `docs/gpt6-jade/ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md`. Avant toute intégration, comparer les branches et les modifications locales simultanées.

**Ne jamais considérer les tests hors ligne GitHub comme une preuve que l'application est installée ou animée sur le téléphone Android.**
