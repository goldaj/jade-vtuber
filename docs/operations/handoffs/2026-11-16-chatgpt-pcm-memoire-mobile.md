# Mission : correction PCM Discord et liaison d'identités mémoire

- **Agent / rôle :** ChatGPT (développement Python async, sécurité mémoire, intégration Web, QA et documentation)
- **Branche :** `fix/discord-pcm-memory-mobile-20261116`, partie de `develop` au SHA `5368f008`, réconciliée sur la réorganisation `91e7e7d` (commit final à lire sur PR)
- **PR :** [#23](https://github.com/goldaj/jade-vtuber/pull/23), **en brouillon, non fusionnée**.
- **Décision :** ne pas utiliser `main`, ne pas toucher au PC/VPS, ne pas installer des SDK propriétaires ni provoquer d'appels facturés. La PWA expose un mécanisme d'association **réservé à Goldaj**, pas un portail public générique.

## Changements committés et justification

Le détail du protocole et des risques suit. Sources techniques modifiées : `src/jade_runtime/output.py`, `memory_store.py`, `memory_service.py`, `mobile_gateway.py`, `discord_text_policy.py`, `twitch_irc.py`, `turn_logging.py`, `mobile_web/index.html`, `app.js`, `styles.css`. Tests ajoutés dans les suites PCM, mémoire et mobile. La documentation fonctionnelle et le journal technique sont synchronisés avec ce code.

## Vérifications et suites

- **Vérifié dans Git :** lecture du câblage, adaptation des conditions PCM et code de test ; code de liaison borné à l'ID cible et à l'opt-in, migration des tours SQLite, route PWA derrière la double authentification déjà en place.
- **Non vérifié dans l'environnement de rédaction :** exécution de la suite Python, nouveau SDK Cubism, Tailscale réel, Discord/Twitch réel, latence et coût. La CI GitHub de la PR doit donner l'état exact des tests.
- **À faire avant approbation :** CI Windows/Ubuntu et gitleaks, revue sécurité d'un code de confirmation dans un chat Twitch public, vérification absence d'effacement inattendu ; test sur PC du streaming et de l'association de deux comptes, avec accord du propriétaire.
- **Avertissement important :** `!jade-memoire oublier` depuis un compte lié efface le **profil partagé entier**. `MemoryStore.unlink` n'a pas d'interface mobile et refuse les séparations ambiguës. Le routage exclusivement par canal d'origine n'est pas livré. Le SDK Live2D Web doit être installé localement sur D: et le modèle r21 final manque encore.

---

**Branche de travail :** `fix/discord-pcm-memory-mobile-20261116`. Cette note décrit **le contenu de la PR**, pas le code de `develop` tant que la PR n'est pas fusionnée. Le PC Jade, les comptes réels, les clés et le SDK Live2D ne sont pas accessibles depuis l'environnement GitHub ; ne pas présenter ces vérifications comme effectuées.

## 1. Discord vocal : streaming PCM avec le launcher tous canaux

Le launcher `--all-channels` conserve `JADE_AUDIO_OUTPUT=ffplay` pour la réponse du microphone local, mais `SpeechOutput.start_early` et `_speak_progressive` ne refusent plus **le vocal Discord** à cause de ce réglage local.

- Avec une source `discord_voice`, une session vocale autorisée, un bridge PCM et un modèle TTS Realtime, la sortie PCM progressive est envoyée directement à Discord même si `ffplay` est configuré localement.
- La sortie locale du microphone PC continue à utiliser `ffplay`; la synthèse écrite/locale et les cas non compatibles restent sur leur chemin WAV existant.
- `JADE_EARLY_VOICE=1` reste facultatif : lorsqu'il est activé, le découpage texte→phrases peut alimenter le PCM Discord dès les premières phrases. Sans cette option, les blocs PCM commencent après génération du texte complet.
- Le **repli WAV** si le TTS n'offre pas de PCM peut encore diffuser aussi sur le lecteur local, selon l'ancienne politique ; le routage exclusif par canal est un chantier distinct du backlog `RTE-01/02`. Ne pas affirmer qu'il est réalisé.
- Un échec pendant le streaming ne doit jamais déclencher une deuxième synthèse facturée pour rejouer la réponse ; conserver la gestion d'annulation existante.

## 2. Liaison mémoire Discord/Twitch avec Goldaj

### Parcours utilisateur

1. Activer `JADE_MEMORY_ENABLED=1` et préparer la SQLite privée sur le PC. Le profil Goldaj doit être actif (micro PC ou PWA privée et authentifiée).
2. Depuis **le compte Discord ou Twitch visé**, envoyer `!jade-memoire activer`. L'identifiant du compte cible est un ID numérique de transport, pas un pseudo. Le salon/serveur ne change pas cette identité.
3. Depuis la PWA Android **privée** Goldaj, ouvrir « Associer un compte Discord / Twitch », choisir le transport et saisir son ID numérique. La requête `POST /api/link` requiert **à la fois** l'identité Tailscale propriétaire et le Bearer PWA ; elle ne permet pas de choisir librement la source : c'est toujours `('microphone','goldaj')`.
4. Copier la commande à usage unique affichée et l'envoyer **depuis le compte cible** : `!jade-memoire confirmer <code>`. Le code expire au bout de cinq minutes, est lié à l'ID cible et ne peut être utilisé par un autre compte, même lorsqu'il apparaît dans le chat Twitch public.
5. La réussite associe les deux identités au même profil **mais ne lève pas les restrictions de rappel par canal/scope** ; aucune lecture automatique des souvenirs privés d'un salon vers un autre.

### Précautions

- Ne pas publier le jeton Bearer du téléphone, la base SQLite ou les secrets d'infrastructure. Le code temporaire de confirmation est masqué dans les logs de tours ; il peut cependant être visible dans le chat cible au moment de la confirmation.
- `!jade-memoire oublier` sur un des comptes **efface le profil entier lié**, pas seulement le canal, y compris les mémoires owner-only si Goldaj y est lié. Ne pas utiliser sans intention explicite de tout effacer. La séparation `MemoryStore.unlink` existe côté API mais **n'a pas encore d'interface utilisateur dédiée**.
- Le moteur SQLite migre maintenant les **tours complets** avant suppression de l'ancien profil pendant `complete_link`, et restitue les tours d'origine lors d'un `unlink` non ambigu. Les liaisons transitives contenant plusieurs comptes d'une même plateforme ne sont pas détachées automatiquement, car les anciennes lignes de conversation ne possèdent pas l'ID source individuel.
- Les anciennes fonctions `begin_link` / `complete_link` non liées à une cible restent accessibles **uniquement en API interne** pour compatibilité. La commande publique refuse ces codes anciens.
- Pas de synchronisation entre PC, ni de lien Twitch Whisper ; Twitch IRC reçoit les commandes dans le chat normal. Contrôler les permissions et l'exposition des réponses.

## 3. Avatar Live2D de la PWA

Le HTML, le rendu `pixi-live2d-display`, les intentions faciales, le décor transparent, la bouche et le repli sont déjà présents. **Aucun SDK Live2D propriétaire n'est ajouté à Git**, ni un modèle final r21 inexistant : la mise à disposition de `pixi.min.js`, `live2dcubismcore.min.js`, `cubism4.min.js` et d'un bundle r20 compatible demeure une étape d'installation locale **sur D:**, suivie d'une vérification Android/Chrome/WebGL/SDK et de la licence. Voir `docs/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md`.

## Tests et critères de clôture

Automatisés à exécuter (pas de facture, sans comptes réels) :

```powershell
python -m unittest tests.test_jade_streaming_pcm tests.test_jade_persistent_memory tests.test_jade_mobile_gateway -v
python -m unittest discover -s tests -v
python -m compileall -q src main.py
```

Vérification PC **après fusion autorisée** : `--preflight --all-channels`, Discord vocal PCM tout en conservant la réponse micro dans les haut-parleurs ; coupure/reconnexion Discord pendant synthèse ; aucun doublon TTS ; deux comptes réels pour confirmer la liaison ; test refus du code depuis un autre ID ; PWA sous Tailscale Serve, SDK Live2D installé légalement et modèle r20 animé ; relevé de latence/coût et contrôle des logs. Aucun déploiement ni merge `develop`/ `main` inclus dans cette PR.
