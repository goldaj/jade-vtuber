# Validation de la PR #26 sur develop

- **Validateur** · Codex, sous-agent `validation_audit`, le 20 novembre 2026. La revue et les tests ont été conduits après l'intégration et séparément de la réalisation.
- **Version vérifiée** · `b427dec700959914c045fb6371697b02ecfdf87e` sur `develop`. [PR #26 intégrée](https://github.com/goldaj/jade-vtuber/pull/26), [CI Windows et Ubuntu réussie](https://github.com/goldaj/jade-vtuber/actions/runs/44479236467), [scan de secrets réussi](https://github.com/goldaj/jade-vtuber/actions/runs/44479236492).
- **Résultat local** · 102 tests ciblés réussis sous Windows avec le venv Jade, sans appels API ni appareils.

| Carte | Décision | Preuves examinées et vérifiées |
| --- | --- | --- |
| DEV-003 | Done | Le repli WAV de Discord vocal utilise exclusivement le lecteur Discord pour une session active. Les tests exercent l'absence d'appel au lecteur local, une défaillance de diffusion et la révocation pendant la synthèse ou la lecture. Les recettes matérielles REC-005/007 restent ouvertes. |
| DEV-005 | Done | Le routage des entrées Discord texte, Twitch et HTTP prévoit uniquement une réponse écrite. Les tests de bout en bout simulés et les assertions de routage couvrent l'absence de TTS ainsi que la préservation des entrées vocales. |
| DEV-007 | Done | PCM et WAV utilisent le même pool Realtime. Les tests vérifient la réutilisation, la fermeture et l'absence de répétition de la synthèse après un échec en cours de réponse. |
| DEV-008 | Done | Les traces de latence sont désactivées par défaut. Les simulations multi-canaux vérifient les étapes file, mémoire, LLM, diffusion, fin et erreur. Les messages et identifiants de canal sont absents des traces de durée. La mesure effective du premier son, de la STT et des coûts reste REC-010. |
| DEV-004 | Bloqué | Le repli WAV et le PCM standard gardent les sous-titres Discord vocal hors du fichier partagé. Le flux anticipé écrit encore les phrases Discord vocal dans ce fichier. La reprise OBS est différée. |
| DEV-006 | Bloqué | Les tests existants vérifient le démarrage de la voix pendant un hotkey lent et l'annulation des tâches. Une reproduction indépendante montre l'échec d'un second hotkey si deux lectures se chevauchent. La reprise VTube Studio est différée. |

Commande de la passe indépendante, depuis la racine du dépôt et avec le Python du venv Jade.

```powershell
python -m unittest tests.test_jade_audio_safety tests.test_jade_discord_voice_output tests.test_jade_main_safety tests.test_jade_streaming_pcm tests.test_jade_runtime_realtime tests.test_jade_turn_logging tests.test_jade_all_channels tests.test_jade_realtime_tts -q
```

## Anomalies différées

- **DEV-004 / OBS** · En activant le mode expérimental `JADE_EARLY_VOICE`, une réponse Discord vocale de deux phrases a été testée avec une destination simulée et une capture des écritures de `EarlySpeechTurn`. Les deux phrases ont été écrites dans le fichier temporaire puis publiées par remplacement atomique avant l'effacement final. Le test existant confirme lui-même ces remplacements. À la reprise, appliquer la décision centrale de visibilité à chaque écriture du flux anticipé. Vérifier que le fichier et son temporaire restent vides de contenu Discord vocal pendant toute la lecture, puis que le sous-titrage public fonctionne encore. Recetter ensuite OBS dans REC-005. Le PCM progressif courant reste disponible avec le mode anticipé désactivé.
- **DEV-006 / VTube Studio** · Une connexion simulée qui retarde la réponse au premier hotkey et refuse les lectures concurrentes reproduit `RuntimeError: concurrent receive` quand le second hotkey entre dans `VTubeStudio.request`. À la reprise, n'autoriser qu'un lecteur sur la connexion et rattacher chaque réponse à son ID, y compris après l'annulation d'une demande. Vérifier deux hotkeys rapprochés, une réponse tardive après annulation et l'absence d'attente côté voix.

La [vue développement](../../backlog/01-DEVELOPPEMENT.md) porte ces statuts. La [vue recette](../../backlog/02-RECETTE.md) suit les essais réels restant à faire.


## Installation Windows et lancement

- **Agent / validation** · Codex, 20 novembre 2026. Inventaire initial du poste et vérifications après installation.
- **Base et code exécuté** · Avance rapide de develop de c03d20f à b427dec. Poste Windows sur D:. Les fichiers de cette passation, du backlog et du journal constituent le seul changement de ce lot sur Git.
- **OPS-001/002/003/004 validées** · Arbre initial propre, worktrees isolés préservés. Git LFS et verify_assets réussis (207 fichiers contrôlés). Python 3.11.1, Poetry 2.2.1, synchronisation du lock avec les extras all, pip check, FFmpeg et ffplay avec Rubber Band et détection des périphériques audio. Installation du lanceur officiel hors Git, scripts comparés par SHA-256. Le rendu r20 a ouvert sa fenêtre sur le PC.
- **OPS-011 validée** · Jeton expiré renouvelé par le mécanisme existant, sauvegarde privée synchronisée et droit d'envoi vérifié. Le socket IRC avait été vérifié pendant le premier démarrage.
- **Instance laissée ouverte** · Suite à la demande finale, Discord texte/vocal et avatar r20 uniquement. Une seule instance. Présence du bot dans le vocal confirmée par Discord après relance. Twitch, micro PC, API HTTP de test et OBS sont fermés. Le modèle est affiché en local. La parole réelle et le partage d'écran restent à recetter.
- **Arrêt et relance** · Ctrl+C dans la console Jade. Pour relancer ce même périmètre, attendre la fermeture puis ouvrir le raccourci local Lancer-Jade-develop.cmd dans le dossier du lanceur sur D:. Le lanceur officiel conserve son mode tous canaux.
- **OPS-005/006/009/010 bloquées** · Le préflight Discord passe. Le préflight tous canaux bloque sur les paramètres privés mobiles et Tailscale. Le MSI officiel signé est préparé sur D: pour l'installation administrateur. Attendre que le propriétaire relie le PC et Android au même tailnet. Ensuite configurer Serve privé vers le port 8766, l'origine HTTPS réelle, le compte propriétaire et un jeton mobile distinct. Les trois bibliothèques JS Live2D Web restent à installer localement, puis à valider avec r20. [Procédure d'installation](../../handbook/INSTALLATION.md#4-configurer-android-privé-et-le-live2d-web).

## Validation locale

Compilation, vérification documentaire et tests ciblés réussis. Deux passages locaux de la suite complète ont donné 497 tests, avec un test ignoré, un échec micro synthétique et deux erreurs Git 128 dans les tests de prévol et d'export. OPS-006 conserve ces écarts. Les commandes Git réussissent dans un processus Python neuf. Dans le groupe de tests, Git signale une surcharge de configuration incomplète, missing config value GIT_CONFIG_VALUE_0. À la reprise, retirer les surcharges GIT_CONFIG_ du seul processus de test et rejouer la suite après correction de la fixture. L'échec micro est reproductible seul avec Rubber Band et une fixture de deux échantillons PCM, soit environ 0,083 ms. Le même test passe avec un signal synthétique de 100 ms ou sans le filtre. Le traitement d'un signal synthétique de longueur réaliste passe dans FFmpeg. Le défaut de fixture est suivi dans DEV-009.

## Branches distantes

**OPS-013/014 validées** par l'audit distinct de Codex. L'intégration de 21 têtes a été établie par ascendance (16) ou égalité de l'arbre au squash intégré (5). Aucun checkout ni PR ouverte ne les utilisait. Suppression atomique conditionnée aux SHA vérifiés. Principaux lots retirés : rangement, démo, documentation, mémoire autobiographique et cœur, unification Discord, PWA, launcher, intentions Live2D, stabilité CI, PCM et quick wins. Les trois têtes historiques ci-dessous conservent des documents ou gardes propres. Leur code utile est déjà intégré via les PR #3 à #5.

| Tête conservée | SHA |
| --- | --- |
| docs/jade-persistent-memory-identity-20261115 | b88f62a |
| feat/turn-conversation-logs-20261115 | 5ee7eab |
| test/intent-all-channels-20261115 | f447f2d |

Main est restée à 632c687. Aucun code ni asset de ces branches n'a été réintégré.


## Reprise mobile le 20 novembre

- **OPS-009** · Installation de Tailscale sur D: confirmée. Le PC a été reconnecté sans changer de profil. Android était en ligne avec la même identité. Tailscale Serve HTTPS pointe exclusivement vers 127.0.0.1:8766, sans Funnel. La page PWA et le manifeste ont répondu 200 depuis le PC via Serve. L'identité, le port privé et la connexion Android au tailnet sont vérifiés. Le chargement depuis Android et le passage Wi-Fi/data restent à recetter.
- **OPS-005** · Origine HTTPS et identité VPN réelles, jeton Bearer propre au mobile et configuration hors Git, sur D:. L'accès loopback sans identité renvoie 403, l'API via Serve sans jeton renvoie 401, un Origin incorrect renvoie 403 et un corps invalide avec le bon jeton renvoie 400. Cette vérification ne déclenche pas OpenAI.
- **OPS-010** · Core installé depuis le ZIP Cubism SDK Web 5-r.5 du propriétaire. PixiJS 6.5.10 et pixi-live2d-display 0.4.0 installés après contrôle SHA-512 publié par npm. Les trois JS, le manifeste r20 et le fichier Idle répondent 200 via Serve. Le manifeste servi par le gateway ajoute bien le mouvement Idle si absent de l'export. Le Core a chargé le modèle et le paramètre de bouche hors ligne. Le navigateur de test Windows n'a pas fourni de rendu observable. La compatibilité adaptateur/Core et l'animation sous Chrome Android restent REC-019.
- **Instance laissée ouverte** · Une console Jade develop sur D: avec une instance Discord écrit/vocal, PWA et avatar local r20. Présence vocale et port 8766 exclusivement sur loopback vérifiés après relance. Le même lanceur local démarre maintenant les deux canaux. Arrêt par Ctrl+C dans la console Jade develop, puis relance avec Lancer-Jade-develop.cmd.
