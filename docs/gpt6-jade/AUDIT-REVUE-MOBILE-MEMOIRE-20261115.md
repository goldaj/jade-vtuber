# Contre-audit PO / architecture / développement : Jade Mobile + mémoire
**15 novembre 2026.** Revue distante du code des PR #7 (mobile) et #6 (mémoire). Aucun accès au PC Jade, à Chrome Android, à Tailscale Serve actif, à OpenAI payant ni au VPS de trading.

## Décision de revue

- **Code de la PR mobile #7 : candidat à la revue technique et à l'intégration contrôlée**, sous réserve de CI au vert sur le dernier commit.
- **Produit mobile effectivement utilisable, avatar animé et parole mobile en conditions réelles : PAS ENCORE VALIDÉS.** Ce lot reste une PR brouillon tant que les gates physiques ne sont pas franchis.
- **Réunion mémoire #6 + mobile #7 : BLOQUÉE tant que les modifications conjointes de `main.py`, `messages.py` et la configuration ne sont pas intégrées et testées sur une branche de rapprochement.** Aucun merge dans `develop` ou `main` n'a été effectué pendant l'audit.

## Constats confirmés et correctifs effectivement codés

| Priorité | Constat | Traitement |
| --- | --- | --- |
| P0 | Tailscale Serve peut réécrire le `Host` du backend en `localhost` alors que `Origin` reste l’URL HTTPS du téléphone. La comparaison initiale Host/Origin empêchait alors les POST Android. | Ajout obligatoire de `JADE_MOBILE_PUBLIC_ORIGIN=https://<nom-pc>.<tailnet>.ts.net` ; le backend compare l’origine du navigateur à cette URL configurée et non au Host réécrit. Nouveau test HTTP reproduisant le reverse proxy. |
| P1 | Les ressources PWA / SDK / modèle en GET étaient servies sans identification personnelle. Toute personne du tailnet pouvant joindre le service pouvait les demander, même sans Bearer. | Ajout obligatoire de `JADE_MOBILE_OWNER_LOGIN` dans la configuration et contrôle du `Tailscale-User-Login` envoyé par **Tailscale Serve** sur **toutes** les routes GET et POST ; les requêtes sans identité ou avec autre identité reçoivent 403. L'API conserve aussi un Bearer indépendant. Tests hors ligne négatifs et positifs ajoutés. |
| P1 | Le bouton microphone pouvait recevoir des touches multiples pendant la demande de permission ou la fermeture asynchrone, conduisant potentiellement à plusieurs captures. | Ajout du verrou `starting` et de `busy` avant fermeture ; une seule capture active, relâchement des pistes, fermeture du contexte audio ; en cas de passage en arrière-plan, abandon sans envoyer la parole enregistrée. |
| P1 | `Voix coupée` ne désactivait pas la synthèse payante lorsque le message venait du micro. | Ajout du contrôle `X-Jade-Speak: 0|1`. Le backend ne facture plus le TTS pour une entrée vocale lorsque la sortie sonore est désactivée. Test hors ligne. |
| P2 | Le début du son pouvait être interdit sur Android lorsque les 20 secondes de capture s'achevaient automatiquement, hors interaction. | Activation précoce du contexte de lecture dès la première touche micro. Recette réelle Android encore requise. |
| P2 | Une erreur de lecture audio pouvait être immédiatement écrasée à l'écran par l'état « Prête ». | Conservation de l'erreur de lecture dans le statut ; séparation des erreurs 401 (jeton) et 403 (identité Tailscale). |
| P2 | Le service worker minimal n'avait pas de gestionnaire `fetch`, ce qui pouvait gêner certains contrôles d'installation PWA. | Gestionnaire GET réseau uniquement, sans stockage local de jetons, messages, fichiers voix, modèle ou SDK. |
| P1 transverse | Les messages mobiles ne partageaient pas la même identité mémoire persistante que le microphone PC dans la PR #6. | Sur la PR #6, `identity_of` résout désormais les entrées propriétaires `mobile` et `microphone` vers `('microphone','goldaj')`. Test de Core Memory partagée. **Activation dans `main.py` après réunion des deux PR restant à intégrer.** |

## Points importants non résolus et raisons

### 1. Avatar Live2D r20 : gate graphique bloquant

Le chargeur actuel utilise `pixi-live2d-display` (PixiJS 6 et bundle Cubism 4). Sa documentation cite principalement les modèles **Cubism 3/4**, pas la compatibilité garantie avec une exportation `.moc3` en Cubism 5. Le projet Jade contient des sources en Cubism 5, mais le format effectif **du binaire r20 LFS** doit être vérifié avant de trancher. La présence du modèle JSON n'est pas une preuve de chargement sur Android.

- **Si r20 est compatible Cubism 4 :** tester le bundle prévu avec le Core associé, WebGL Android et le rendu alpha ; vérifier les idle motions, émotions, physique et bouche.
- **Si r20 exige Cubism 5 :** changer de pile complète (adaptateur Cubism 5 + PixiJS compatible, ou SDK Web 5 officiel) et adapter `avatar.js`. La simple substitution du JS `live2dcubismcore.min.js` n'est **pas** une preuve de compatibilité.
- Aucun SDK propriétaire ou fichier sensible ajouté au dépôt. Les trois scripts de runtime restent à acquérir/installer légalement en privé sur D: et valider. Le décor et le chat continuent à fonctionner en cas d'échec du rendu.

Sources techniques à contrôler : https://github.com/guansss/pixi-live2d-display ; https://www.live2d.com/en/sdk/download/web/ ; https://github.com/omniwaifu/pixi-live2d5 (alternative candidate non encore recettée).

### 2. Authentification réelle sur le téléphone : gate réseau bloquant

L'URL HTTPS attendue **doit être relevée par `tailscale serve status` sur le PC** et inscrite dans `JADE_MOBILE_PUBLIC_ORIGIN`. Ce paramètre évite de supposer que le `Host` reçu par le backend est le même que l'`Origin` du navigateur : la réécriture par Go `ReverseProxy.SetURL()` est un cas réel. Le test automatisé couvre la situation `Host=127.0.0.1:<port>` + `Origin=https://...ts.net`, sans en déduire qu'un navigateur réel a été testé.

Tailscale Serve transmet l'en-tête `Tailscale-User-Login` et retire les versions forgées par les clients distants ; c'est une garantie du proxy et **non** de Python lorsqu'on se connecte directement au loopback. Le backend exige cet en-tête pour toutes les routes en production. Le test HTTP direct du PC renvoie désormais 403 par conception ; la vérification de l'avatar doit passer par l'URL privée HTTPS affichée par Serve. Activer la règle d'accès tailnet strictement pour Goldaj et ne pas exposer le port au LAN, à Funnel ni à Internet.

Source : https://tailscale.com/docs/features/tailscale-serve

### 3. Audio mobile : encore une V1 push-to-talk

Le micro Android est une capture WebAudio courte (maximum 20 secondes) puis envoi WAV. Le navigateur reçoit un WAV complet renvoyé dans du JSON Base64. Il n'y a **pas de streaming audio**, de duplex ni d'interruption de la parole en cours. Cela génère de la latence et des copies mémoire temporaires, mais permet une V1 contrôlable. Ni le STT ni le TTS ne créent de fichier WAV sur disque ; les traces `jade.conversation` du runtime contiennent toutefois le texte des tours. En cas de coût ou de délai excessif, passer à un transport en flux et borner la file d'envois.

### 4. Mémoire et identités : rapprochement de branches obligatoire

Le code de la mémoire est sur la PR #6, non présente dans la PR #7. L'alias propriétaire mobile→microphone est maintenant codé sur #6 ; **le démarrage du service mémoire quand seul `--mobile` est actif n'est pas encore intégré**. Après rapprochement, même SQLite sur D:, même clé propriétaire, même `scope='person'` entre microphone local et téléphone. Éviter le dédoublement d'une nouvelle personne propriétaire, les conflits de champs `Incoming` et l'écrasement des paramètres dans `main.py`. La conversation Discord voix+texte relève encore d'un chantier Codex à part.

## Matrice de recette restante (sur matériel réel)

| Vérification | Critère d'acceptation |
| --- | --- |
| Web SDK / modèle r20 | Animation Idle, clignement et bouche visibles sur le téléphone, aucune bordure verte ; GPU raisonnable |
| Chat Android | Texte soumis une seule fois ; contexte inchangé au passage texte→micro dans une même session |
| Micro Android | Permissions correctement gérées, abandon en arrière-plan, pas de double capture, audio en mémoire seulement |
| TTS Android | Une seule réponse audible sur le téléphone, intention/transcription correctes, haut-parleurs du PC non dupliqués |
| Connexion privée | Seul login Tailscale autorisé reçoit la page/le modèle ; Bearer requis pour POST |
| Réseau instable | Erreurs/reconnexions comprises, aucune répétition invisible de tour facturé |
| Mémoire après rapprochement | Un seul profil Goldaj partagé entre PC et Android, Core Memories conservées, suppression explicite respectée |
| Migration ordinateur | DB SQLite exportée/importée, puis client mobile connecté au nouveau PC, sans VPS trading impacté |
| Arrêt PC / Tailscale | Message d'indisponibilité ; l'application n'invente pas de réponse hors ligne |

## Décision de passage

**GO pour la revue du code et les tests automatisés. NO-GO pour annoncer une application Android fonctionnelle/recettée ou effectuer un déploiement automatique.** Conserver la PR #7 ouverte et, si utile, en brouillon jusqu'à installation des SDK privés et recette physique. Ne pas toucher au VPS Hyperliquid. Les aspects licence/compatibilité et l'absence d'accès matériel sont des limites réelles, pas des détails de documentation.

## Complément de revue après reprise du chantier

- **CSP et WebAssembly :** le chargement de certains moteurs Cubism Web peut exiger la compilation de WebAssembly ; la politique HTTP initiale n'autorisait que `script-src 'self'`. Elle autorise maintenant **uniquement** `'wasm-unsafe-eval'`, sans `'unsafe-eval'` pour le JavaScript général. Ce changement réduit le risque d'un modèle invisible sur Chrome Android, mais n'établit toujours pas la compatibilité r20/Cubism 5. Test HTTP de l'en-tête ajouté. Référence : documentation CSP MDN, `wasm-unsafe-eval`.
- **Échec du modèle IA et attente excessive :** la passerelle ne passait pas le `Future` de résultat au runtime. Si le dialogue levait une erreur avant `on_reply`, le téléphone attendait environ 55 secondes puis affichait une expiration. Elle écoute désormais le résultat d'exécution uniquement pour **propager rapidement les échecs** tout en continuant à recevoir l'objet `Reply` complet (texte, intention) par le callback normal. Test d'échec synthétique avec délai client 4 secondes ajouté, aucune requête API facturée.
- **Choix de ne pas fusionner les PR #6 et #7 au cours de cette revue :** ces branches modifient simultanément `main.py`, `messages.py`, `dialogue.py`, `config.py`, `AGENTS.md` et les docs. Leur mise en commun réclame une vraie branche d'intégration, combinant les champs `account_id`, `input_modality`, `requested_speech`, et le `MemoryService` au démarrage `--mobile`. La CI propre à chaque PR **ne teste pas leur réunion**. Codex doit éviter un merge mécanique qui remplacerait l'une des deux versions.
- **Borne de certitude :** le backend HTTP a des tests Python indépendants du matériel ; les tests JS vérifient surtout la syntaxe et la présence des ressources. Aucun test de rendu Live2D Web, de capture mobile ni de permission audio Chrome sur appareil physique. Ne pas confondre compilation/CI verte avec un produit prêt à installer.
