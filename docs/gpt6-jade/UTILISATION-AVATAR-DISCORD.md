# Afficher Jade pendant une conversation Discord

Cette procédure lance le vrai modèle Live2D r20 fourni avec le dépôt, sur le PC Windows qui exécute Jade. Son animation de bouche suit approximativement le volume du son à partir du début de lecture local ou Discord ; ce n'est pas une synchronisation phonétique. Le démarrage du lecteur, le traitement et l'acheminement audio ajoutent une latence variable. Le modèle et les services externes ne sont pas démarrés par le préflight.

1. Dans un clone complet de `develop`, récupérer les fichiers du modèle avec `git lfs pull`. Installer Python 3.11, Poetry et FFmpeg ; vérifier que `ffmpeg` est dans le `PATH`. Utiliser `ffplay` également si la sortie locale est souhaitée.
2. Installer les dépendances verrouillées : `poetry sync --only main -E discord-voice -E avatar`.
3. Dans la configuration privée locale, renseigner la clé OpenAI, `DISCORD_TOKEN` et `DISCORD_VOICE_CHANNEL`. Ne pas les publier. Pour écouter uniquement via Discord, régler `JADE_AUDIO_OUTPUT=none` ; pour écouter aussi sur le PC, utiliser `ffplay` (attention au retour audio et aux doublons).
4. Vérifier sans connexion ni coût : `poetry run python main.py --preflight --live --voice --discord --discord-voice --avatar`.
5. Lancer : `poetry run python main.py --live --voice --discord --discord-voice --avatar`. La fenêtre r20 s'ouvre ; Jade rejoint le salon vocal configuré. Les appels OpenAI en mode live sont payants.
6. Pour voir la fenêtre sur un téléphone : sur le compte Discord du PC, rejoindre le salon vocal, lancer manuellement le partage de la fenêtre Jade, puis ouvrir le même salon sur le téléphone. Le bot ne partage pas lui-même l'écran. Le son de la voix vient de la connexion vocale du bot ; éviter d'ajouter une deuxième capture du son du PC.
7. Arrêter Jade avec Ctrl+C. La fenêtre enfant se ferme avec le runtime. Si elle ne s'ouvre pas, vérifier l'extra `avatar`, les fichiers LFS et OpenGL ; le préflight ne garantit pas la compatibilité graphique.

Le lancement graphique r20 a été vérifié localement en mode caché. La chaîne complète avec Discord, partage d'écran, téléphone et perception de la synchronisation reste à vérifier dans un essai réel. Le modèle r21 artistique est un travail distinct encore non validé.
