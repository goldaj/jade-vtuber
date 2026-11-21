# Préparation D3–D4 sans services réels

Cette notice prépare les lots D3 et D4 de la [feuille de route](ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md). Elle ne valide ni VTube Studio, ni le partage Discord, ni le téléphone. Conserver le modèle et les assets intacts ; les travaux ci-dessous portent sur le runtime, ses doubles de test et la documentation. Le MVP Discord reste prioritaire sur le produit mobile autonome.

## D3 — Préparation testable hors connexion

1. **Partir de l'état réel du code.** `VTubeStudio` valide une URL WebSocket locale, authentifie avec un jeton fourni et déclenche une hotkey. Il ne fournit pas encore de procédure complète d'obtention initiale du jeton. Dans `main.py`, la hotkey est actuellement envoyée avant la synthèse TTS. Dans `SpeechOutput`, le WAV est ensuite synthétisé puis joué localement et/ou dans Discord. Aucun de ces constats ne prouve une animation visuelle.
2. **Définir un contrat d'événements de lecture**, découplé du modèle : identifiant du tour et de la session autorisée, début effectif de sortie, fin, annulation ou erreur. Utiliser une horloge monotone pour les mesures ; ne jamais journaliser le texte, l'audio ou les jetons. Clarifier quel lecteur fait foi pour une réponse Discord et comment on traite le cas `JADE_AUDIO_OUTPUT=none` : une lecture locale vide ne doit pas être prise pour un début audible sur Discord.
3. **Déplacer le signal visuel au bon endroit**, au moment attesté du début de lecture pertinente, et prévoir le retour au repos pour toute fin ou interruption. L'appel VTS doit rester optionnel et borné ; une erreur visuelle ne doit ni exposer une session révoquée, ni provoquer une seconde lecture, ni bloquer indéfiniment la sortie audio. Définir explicitement le comportement si VTS se ferme ou si le retour au repos échoue. Une hotkey ponctuelle n'est pas un lip-sync continu.
4. **Tester avec des doubles uniquement** : synthèse lente ou refusée avant lecture ; lecture réussie ou interrompue ; échec VTS au début et à la fin ; révocation Discord avant ou pendant la sortie ; absence de sortie locale ; concurrence et fermeture. Vérifier l'ordre des événements, l'absence de signal après révocation, le retour au repos quand il est possible, la durée bornée et l'absence de double diffusion. Des essais simulés ne prouvent pas la synchronisation perçue.
5. **Préparer l'authentification locale privée** : procédure d'autorisation interactive VTube Studio, conservation du jeton hors dépôt, puis cas de jeton absent, invalide ou révoqué, connexion interrompue et réponse API inattendue. Utiliser un faux serveur ou des mocks hors réseau pour les tests ; ne pas enregistrer le jeton ni les réponses sensibles. Le client limite déjà l'adresse à `localhost` ou `127.0.0.1` : préserver cette frontière.

## D3 — Recette physique ultérieure

1. Contrôler les objets LFS et les références du package r20 avec `python jade-modeling/verify_assets.py`. Le r20 est une sauvegarde distincte, pas l'export final du r21 ; la présence des fichiers ne valide pas leur rendu.
2. Dans VTube Studio installé séparément, ouvrir le modèle r20 suivant `jade-modeling/MODEL_GUIDE.md`. Observer textures, expression neutre, physique et mouvements. Ne pas exiger une caméra ni modifier le rig pendant cette recette.
3. Activer l'API locale, autoriser le plugin et conserver le jeton en configuration privée. Identifier dans VTube Studio les hotkeys réellement disponibles pour ce modèle ; leurs identifiants ne sont pas interchangeables par hypothèse. Déclencher une action visible, puis vérifier la fermeture et le refus d'un jeton invalide.
4. Avec les services et la session vocales explicitement activés et les participants informés, observer le repos, le début de parole, la fin et l'interruption. Relever les décalages réels et les échecs sans enregistrer les échanges privés. Conclure « mouvement simple » si c'est ce qui a été observé ; réserver « lip-sync » à une animation effectivement pilotée par l'audio.

## D4 — Préparation documentaire et recette téléphone

Préparer une checklist sans activer de service : poste Windows, VTube Studio avec modèle cadré, éventuellement une scène OBS capturant seulement la fenêtre utile, client Discord utilisateur sur PC, téléphone avec Discord, salon vocal de test et participants informés. La diffusion est lancée manuellement par le client utilisateur PC ; ni le bot ni OBS Virtual Camera ne constituent à eux seuls un émetteur Go Live.

Lors de la recette réelle :

1. Avec l'accord et la présence du propriétaire, ouvrir le modèle puis le client Discord PC ; couper son micro si le téléphone est la seule entrée souhaitée. Vérifier le cadrage et éviter de partager les notifications privées.
2. Partager la fenêtre VTube Studio ou la scène OBS dans le salon, puis rejoindre ce salon depuis le téléphone et afficher le flux. Éviter une seconde piste audio capturant Jade dans le stream ; sa voix doit venir une seule fois du bot Discord.
3. Prononcer une question sans nom d'activation, puis un suivi ; vérifier la pertinence de la réponse, la présence de l'avatar, sa réaction, l'audio unique et l'absence d'écho. Chronométrer les délais observés et noter l'appareil, le réseau et les limites sans conserver les conversations.
4. Vérifier arrêt/reprise du partage et déconnexion/reconnexion. Tester également le réseau cellulaire si disponible. Les essais nécessitent que les fonctionnalités vocales D2 soient effectivement intégrées et recettables ; les mocks ne satisfont pas le gate.

Les gates D3 et D4 restent ouverts jusqu'aux observations réelles prévues par la feuille de route et à la validation du propriétaire. Le téléphone du MVP utilise Discord ; le navigateur mobile/PWA et son transport média appartiennent à la phase ultérieure, distincte.
