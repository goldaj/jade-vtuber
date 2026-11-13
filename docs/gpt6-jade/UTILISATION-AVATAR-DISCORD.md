# Afficher Jade pendant une conversation Discord

Cette procédure lance le vrai modèle Live2D r20 fourni avec le dépôt, sur le PC Windows qui exécute Jade. Son animation de bouche suit approximativement le volume du son à partir du début de lecture local ou Discord ; ce n'est pas une synchronisation phonétique. Le démarrage du lecteur, le traitement et l'acheminement audio ajoutent une latence variable. Le modèle et les services externes ne sont pas démarrés par le préflight.

1. Dans un clone complet de `develop`, récupérer les fichiers du modèle avec `git lfs pull`. Installer Python 3.11, Poetry et FFmpeg ; vérifier que `ffmpeg` est dans le `PATH`. Utiliser `ffplay` également si la sortie locale est souhaitée.
2. Installer les dépendances verrouillées : `poetry sync --only main -E discord-voice -E avatar`.
3. Dans la configuration privée locale, renseigner la clé OpenAI, `DISCORD_TOKEN` et `DISCORD_VOICE_CHANNEL`. Ne pas les publier. Pour écouter uniquement via Discord, régler `JADE_AUDIO_OUTPUT=none` ; pour écouter aussi sur le PC, utiliser `ffplay` (attention au retour audio et aux doublons).
4. Vérifier sans connexion ni coût : `poetry run python main.py --preflight --live --voice --discord --discord-voice --avatar`.
5. Pour essayer la réponse progressive sous PowerShell :

   ```powershell
   $env:JADE_EARLY_VOICE = '1'
   $env:JADE_TTS_SPEED = '1.5'
   poetry run python main.py --live --voice --discord --discord-voice --avatar
   ```

   La fenêtre r20 s'ouvre ; Jade rejoint le salon vocal configuré. Les appels
   OpenAI en mode live sont payants. Le découpage des réponses en plusieurs
   synthèses est expérimental et peut modifier le coût ou la prosodie : en cas
   de problème, fermer Jade, régler `JADE_EARLY_VOICE=0` et relancer. Le
   streaming audio Discord reste actif pour le TTS Realtime même sans découpage
   anticipé du texte. Pour une vitesse normale : `JADE_TTS_SPEED=1.0`.
6. Pour voir la fenêtre sur un téléphone : sur le compte Discord du PC, rejoindre le salon vocal, lancer manuellement le partage de la fenêtre Jade, puis ouvrir le même salon sur le téléphone. Le bot ne partage pas lui-même l'écran. Prévoir au besoin deux comptes utilisateurs distincts : un pour partager depuis le PC et un pour regarder depuis le téléphone. Couper le micro du compte PC pour éviter un retour, et ne pas partager le son du PC : la voix vient du bot. Voir le [guide officiel du partage Discord](https://support.discord.com/hc/en-us/articles/360040816151-Go-Live-and-Screen-Share).
7. Arrêter Jade avec Ctrl+C. La fenêtre enfant se ferme avec le runtime. Si elle ne s'ouvre pas, vérifier l'extra `avatar`, les fichiers LFS et OpenGL ; le préflight ne garantit pas la compatibilité graphique.

Le propriétaire confirme la réponse vocale réelle depuis le téléphone et le
mouvement du modèle en local. Le partage vidéo vers le téléphone, la perception
de la synchronisation et les scénarios d'interruption restent à vérifier avec
lui. Le portrait Discord utilise maintenant r21 ; cela ne remplace pas le modèle
animé r20. Voir le [relais latence](PLAN-LATENCE-20261110.md).

## VTube Studio : état et reprise du partage différé

`--avatar` ouvre le moteur r20 autonome ; `--vts` désigne un connecteur distinct.
Le poste possède VTube Studio et le package `Jade_professional_r20_idle_complete`,
mais la configuration active du dernier essai n'activait pas ce connecteur et
ne contenait pas son jeton. Son code actuel déclenche une hotkey avant la voix ;
il n'envoie pas l'enveloppe audio à la bouche. L'essai autonome ne valide donc
pas une synchronisation dans VTube Studio.

À la reprise avec le propriétaire :

1. Relancer le parcours vocal ci-dessus ; garder `davey==0.1.7` avec
   `discord.py==2.7.1`. La mise à niveau isolée vers davey 0.2.0 empêchait les
   clés DAVE de devenir utilisables ; ne pas contourner le verrou à l'installation.
2. Pour partager le rendu déjà essayé, sélectionner la fenêtre Jade dans le
   client Discord du PC. Si la session demande encore une connexion, utiliser
   le QR code ou la connexion normale du propriétaire ; le code QR est temporaire.
3. Pour le parcours demandé dans VTube Studio, ouvrir le package r20 décrit dans
   [MODEL_GUIDE](../../jade-modeling/MODEL_GUIDE.md), activer son API locale et
   autoriser le plugin Jade. Conserver le jeton obtenu dans la configuration
   privée (`JADE_VTS_TOKEN`, `JADE_VTS_ENABLED=1`), jamais dans Git. L'authentification
   et la lecture du modèle chargé suivent l'[API officielle VTS](https://github.com/DenchiSoft/VTubeStudio).
4. Vérifier le modèle visible. Pour une bouche pilotée par la voix de Jade dans
   VTS, il reste à raccorder le niveau PCM réellement joué à un paramètre de
   bouche VTS, ou à configurer une entrée audio locale adaptée. Une hotkey seule
   ne prouve pas cette synchronisation. Garder la fenêtre autonome disponible
   pour la recette du MVP tant que ce raccordement n'est pas vérifié ; ne pas
   installer un nouveau routage audio complexe sans nécessité.
5. Partager **une seule** fenêtre, sans son PC ni micro PC en doublon, puis vérifier
   sur le téléphone image en mouvement, voix du bot et arrêt/reprise. Le propriétaire
   a reporté cet essai ; aucun succès vidéo n'est annoncé à sa place.
