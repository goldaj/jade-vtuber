# Jade : démarrage unifié sur le PC Windows et arbitrage des conversations

**Décision du 15 novembre 2026 :** le propriétaire refuse la sélection de modes du launcher. Jade doit être présente simultanément sur **tous ses supports** ; Jade décide ensuite **l'ordre des réponses**, sans priorité fixe à un support. Cette décision remplace la sélection de profils de la PR #13.

## Fonctionnement livré

- Le launcher ne propose que **le choix de la branche Git** et le chemin facultatif de la configuration privée. Poetry et Git LFS sont systématiquement préparés. Il invoque uniquement `python main.py --all-channels` pour le préflight et pour le runtime.
- `--all-channels` active ensemble les sources prises en charge par le moteur : **Discord texte et vocal, Twitch, microphone local, API HTTP locale, application mobile privée**, ainsi que la voix OpenAI et l'avatar r20 autonome. VTube Studio est aussi activé si et seulement si son connecteur `JADE_VTS_ENABLED=1` est configuré, car il s'agit d'un rendu supplémentaire et non d'un canal de conversation obligatoire.
- Le moteur `Runtime` conserve une **file unique bornée** pour tous les messages sélectionnés. Quand plusieurs conversations sont en attente, `TurnArbiter` demande au modèle de dialogue de Jade de choisir l'identifiant du prochain tour selon pertinence, urgence et attente. Il n'existe **aucun poids fixe accordé à Discord, Twitch, PC ou mobile**.
- Les tours successifs d'une même conversation conservent leur ordre. Un délai d'attente de 15 s ou une requête proche de son expiration prévaut sur l'arbitrage IA pour empêcher la famine. Si le modèle ne répond pas en 2 secondes, renvoie une réponse invalide ou est indisponible, l'ordre d'arrivée reste le repli fiable.
- Le moteur n'interrompt pas de force une réponse déjà en cours. Il réordonne **les demandes encore en attente**, et fait l'arbitrage seulement lorsqu'il y a contention. Les messages privés ne sont pas inclus dans les réponses adressées à un autre utilisateur.
- Les appels d'arbitrage sont **des appels supplémentaires potentiellement facturables** lorsqu'il existe au moins deux conversations prêtes. Ce ne sont pas des appels STT ou TTS. Les éléments utilisés pour décider sont des extraits limités des messages en attente, envoyés au même LLM de Jade et **jamais consignés dans un journal supplémentaire**.
- L'écoute du micro local ne patiente plus jusqu'à la vidange de **tous** les messages des autres canaux ; la barrière audio conserve le contrôle contre les retours TTS. Les réponses du micro local et de l'API HTTP privée ne sont plus automatiquement diffusées dans un salon vocal Discord sous prétexte que ce salon est aussi connecté.
- Les réponses demeurent distribuées selon la destination originale (Discord texte, Twitch texte, mobile, etc.) et la politique de Jade. **Toujours active** ne signifie pas recopier toutes les conversations sur tous les supports.

## Mise en place

Installer ou mettre à jour une fois le lanceur depuis un clone `develop` à jour en double-cliquant sur `Installer-Launcher-Jade.cmd`. Il installe les scripts **hors du clone Git** dans `D:\Jade\launcher`. Le launcher n'est pas mis à jour automatiquement à chaque changement de branche : **relancer cet installateur après récupération de cette correction**.

Ensuite double-cliquer sur `D:\Jade\launcher\Lancer-Jade.cmd`. Sélectionner la branche Git et cliquer **Mettre à jour et lancer toute Jade**. Le lanceur refuse de détruire les changements locaux, utilise un fast-forward et lance **automatiquement** `poetry sync --only main -E all`, `git lfs pull` et le préflight, sans option pour désactiver un support. Le lancement réel peut facturer OpenAI.

## Prérequis *stricts* pour démarrer tous les canaux

La configuration privée existante doit contenir les secrets et l'activation **de tous** les connecteurs. Le launcher ne les invente pas et ne masque pas les canaux absents : si un préflight obligatoire échoue, **aucun lancement partiel** ne survient.

- `OPENAI_API_KEY`, `DISCORD_TOKEN` et `DISCORD_VOICE_CHANNEL` ;
- `JADE_TWITCH_ENABLED=1`, `JADE_TWITCH_SEND=1`, `TWITCH_CHANNEL`, `TWITCH_TOKEN` ;
- `JADE_MOBILE_ENABLED=1`, `JADE_MOBILE_TOKEN`, `JADE_MOBILE_OWNER_LOGIN`, `JADE_MOBILE_PUBLIC_ORIGIN` (HTTPS privé Tailscale Serve réel) ;
- `JADE_HTTP_ENABLED=1`, `JADE_HTTP_TOKEN` (jeton **différent** du mobile) ;
- `JADE_AUDIO_OUTPUT=ffplay`, `ffplay` et `ffmpeg` dans le PATH, Python/Poetry, dépendances facultatives (`-E all`) et ressources Live2D ;
- Pour le rendu VTube Studio en plus de l'avatar autonome, configurer localement l'API VTS et le jeton correspondant ; sinon le modèle r20 autonome s'affiche quand même.

Les SDK Web Live2D propriétaires de la PWA doivent avoir été obtenus légalement et installés sur D:, hors Git ; Tailscale Serve reste configuré **uniquement sur le PC**. Les vérifications locales ne prouvent pas que Discord, Twitch, Tailscale, micro, rendu GPU et OpenAI fonctionneront réellement. Aucun VPS trading ni port public modifié.

## Limites et recette

Les tests GitHub hors ligne valident l'arbitrage, le compte de la file, les délais, le routage confidentiel et la transmission des flags. L'essai **sur le vrai PC Windows** reste indispensable : vérifier démarrage simultané, log de connexion de chaque canal, échange sur Discord/Twitch/micro/mobile/HTTP sans désactiver les autres ; audio local et Discord ; charge simultanée, latence et coût ; fermeture propre Ctrl+C ; reprise après déconnexion. Ne pas qualifier `--all-channels` de réussite multi-supports simplement parce que les tests passent.

Le mécanisme d'arbitrage ne rend pas Jade omnisciente ou parallèle : le moteur reste séquentiel à l'échelle de la génération des réponses. Un modèle peut faire des choix discutables ; le fallback, les délais et l'ordre par conversation restent des garanties techniques, indépendantes de l'IA.
