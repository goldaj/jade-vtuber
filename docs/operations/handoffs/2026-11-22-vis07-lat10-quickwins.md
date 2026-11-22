# Passation : VIS-07 → DEV-029, LAT-10 → DEV-030

**Décision du propriétaire, 22 novembre 2026 :** promouvoir les deux idées P1 dans la backlog officielle, et développer VIS-07 avant LAT-10 sur `develop`. La branche `main` reste inchangée, les développements VIS-04 (DEV-027) et RTE-12 (DEV-028) ne sont pas clôturés ici.

## Audit des doublons et limites

- VIS-04 possède déjà un seul arbitre de visibilité (`syncRenderVisibility`) sur le moteur mobile PixiJS/Live2D. VIS-07 n'a pas de boucle ni de gestionnaire graphique supplémentaire : il enrichit **le même arbitre**, sans intervenir sur Windows, VTube Studio, OBS ni le décor mobile `room-motion.js` (déjà animé avec sa propre pause).
- Une page en arrière-plan peut avoir ses timers réduits ou gelés par Android et son moteur graphique doit être arrêté sans délai. La demande d'hystérésis est donc appliquée aux **occlusions transitoires du viewport**, pas aux sorties de l'application.
- LAT-10 est distinct : inventaire des deadlines du pipeline TTS/PCM, sans aucun changement apporté dans ce lot.

## DEV-029 — politique implémentée

- **Visible :** PixiJS actif, `model.autoUpdate` actif. Le modèle et la motion Idle sont chargés une seule fois.
- **Sortie temporaire du viewport :** temporisation **6500 ms** programmée une fois ; si Jade redevient visible avant expiration, minuterie annulée, **aucun stop/start**.
- **Hors viewport au-delà de 6500 ms :** `pixi.ticker.stop()`, `model.autoUpdate=false`.
- **Onglet caché, application en arrière-plan, élément absent/démonté :** arrêt **immédiat**, sans différé, et annulation de l'éventuelle minuterie ; ne pas consommer des ressources GPU inutilement pendant les six secondes de grâce.
- **Vraie reprise après arrêt :** expression neutralisée visuellement, minuterie de réaction annulée, reprise du ticker et des updates. **Aucun rechargement Live2D**, aucune relance d'Idle, aucune modification de la génération de dialogue, de la synthèse vocale, des messages, ni de la mémoire. La bouche reste pilotée par l'audio réel.
- **Chargement initial en arrière-plan :** aucun ticker actif avant que le modèle soit chargé et visible. En l'absence d'`IntersectionObserver`, le repli de VIS-04 surveille toujours `visibilitychange`.

## Qualité, risques et recette

Le test Node `tests/mobile_avatar_visibility_test.js` utilise une horloge simulée (aucune attente réelle) : il vérifie occlusion 3,5 s / retour / minuterie annulée, occlusion 6,499 s puis 6,5 s, absence de répétition des timers, arrêt immédiat sur `document.hidden` et déconnexion DOM, reprise neutre, conservation de l'état audio, non-recréation du modèle et de la motion Idle, compatibilité sans `IntersectionObserver`. Il est exécuté sur les deux OS dans `jade-rebuild.yml`.

**Impacts :** une fenêtre où seul l'avatar passe juste hors viewport peut maintenir le GPU actif jusqu'à 6,5 s supplémentaires, en échange de l'évitement de bascules intempestives ; aucune consommation LLM supplémentaire. Les gains/pertes d'énergie et FPS ne sont **pas mesurés** sur Android réel. Les transitions de visibilité de plus de 6,5 secondes sont suspendues comme avant. La fonction n'est pas une garantie de mise en pause sur toutes les superpositions visuelles du système Android.

**Recette utilisateur restante :** sur Android réel, défilement rapide avec apparitions/disparitions de Jade, quitter/revenir dans la PWA, vérifier neutralité des expressions après véritable pause, absence de recharge du modèle, continuité de la voix et du dialogue. **DEV-029 n'est pas Done tant que cette acceptation n'est pas acquise.**

## DEV-030 — cadrage, sans développement

Harmoniser `JADE_API_TIMEOUT`, synthèse WAV, flux Realtime/PCM, lecteur ffplay, limites de tour, révocations et annulations. Avant tout changement de code, inventorier les valeurs effectives et mesurer la cause d'éventuelles interruptions. Pas de nouveau modèle ni d'appel IA payant dans ce lot.
