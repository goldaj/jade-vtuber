# Passation ChatGPT — quick wins VIS-04 et RTE-12 (22 novembre 2026)

## Décision, branches, règles

Le propriétaire a demandé de promouvoir d'abord le `develop` courant sur `main`, puis de réparer la CI si nécessaire avant les nouveaux développements. **PR #41**, fusion normale sur `main` en `6afbe0c`, conserve le baseline validé. Tous les changements suivants sont limités à `develop`. Aucun force-push, aucune activation de modèle ou connexion externe.

Le catalogue d'idées a été dédoublonné par promotion unique :
- **VIS-04 → DEV-027 (P1)** ; entrée active retirée de `docs/ameliorations/04-AVATAR-VISIBILITE.md`.
- **RTE-12 → DEV-028 (P1)** ; entrée active retirée de `docs/ameliorations/03-CANAUX-ROUTAGE.md`.
Le catalogue contient désormais 114 idées prospectives, dont 23 P1.

## Correctif de CI préexistant

Avant le lot, les workflows `Jade rebuild offline tests` étaient rouges : 13 échecs et 5 erreurs Linux, avec divergence entre contrat de mémoire approuvé et vieux tests, plus deux modules utilisant `pytest` pendant la découverte `unittest`. Les tests ont été convertis en `unittest` et alignés sur les décisions validées : Core L3 volontaire par Jade depuis toute identité enrôlée, lectures de souvenirs globales, L2 obligatoire seulement sur demande ordinaire du propriétaire authentifié, pas de citation littérale exigée. L'isolement des écritures, l'absence d'écriture sans identité et les erreurs JSON restent recettés. Les assertions de version SQLite se réfèrent au schéma v8 courant. La publication privée a aussi été corrigée pour copier les deux nouveaux calques WebP de DEV-010 tout en validant leurs en-têtes RIFF/WEBP.

Les corrections ne modifient pas le moteur de mémoire runtime. La suite Windows a déjà terminé avec succès sur le commit pré-développement `fe4a99d` ; une exécution complète Linux/Windows sur le HEAD final du lot doit encore servir de preuve définitive.

## DEV-027 — Live2D mobile en visibilité réelle

- `src/jade_runtime/mobile_web/avatar.js` suspend le ticker PixiJS et, quand exposé par le SDK, le `model.autoUpdate` lors du masquage de l'onglet, de l'absence de composant ou de la sortie de l'avatar hors fenêtre via `IntersectionObserver`.
- Le rendu démarre seulement après chargement complet, visibilité et attachement, puis reprend sans recréer l'avatar ni rejouer l'animation Idle. L'absence d'`IntersectionObserver` utilise au minimum `visibilitychange`.
- Aucun changement de génération des réponses, lecture audio, transport, mémoire ni API. Gain GPU/batterie attendu, **pas de mesure matérielle attestée**.
- `tests/mobile_avatar_visibility_test.js` contrôle démarrage, onglet caché, retour, hors champ, démontage et absence d'API d'observation.

## DEV-028 — preuves passives de livraison (refonte du 22 novembre)

**La première implémentation a été retirée**, car elle imposait un contrat de retour structuré entre `main.py`, `Runtime.on_reply` et `SpeechOutput._speak_progressive`. Même avec des tests verts, coupler le journal à la diffusion créait un risque inutile.

La refonte conserve **exactement les contrats fonctionnels de la version de référence sur `main`** :
- `Runtime.on_reply` ne consomme aucun accusé ni dictionnaire de résultat ; son comportement, ses appels mémoire et ses erreurs restent les mêmes.
- `SpeechOutput.speak` et `_speak_progressive` ont retrouvé leurs valeurs de retour historiques ; le choix du repli WAV, les autorisations et le TTS n'ont pas été modifiés.
- Trois **points d'observation facultatifs et synchrones**, sans `await`, sont placés **après un succès préexistant** : `main.py` après l'API Discord texte, `AudioOutput.play` après la sortie réussie de ffplay, et `DiscordVoiceBridge.mark_voice_reply_played` après confirmation de session.
- `turn_logging.observe_delivery` ne décide rien, n'envoie rien et ignore les événements non autorisés ou sans identifiant de tour issu du `ContextVar` local. Les seuls événements sont `transport_accepted / discord_text / discord_api` et `playback_completed / discord_voice / discord_audio_consumer` ou `local_audio / ffplay_exit_zero`.
- La méthode `_emit_delivery_diagnostic` isole les deux destinations de logs (console, fichier privé). Une exception de l'une ne bloque jamais l'autre ni le transport. Le `record_delivery` historique est rendu non bloquant également ; son statut `handoff_completed` **n'est pas** une preuve que le client a reçu ou lu la réponse.
- Aucun contenu de conversation, token, identifiant de message, identité ou secret n'est ajouté aux événements de preuve ; seulement identifiant numérique de tour, destination, état et provenance technique. Aucun coût LLM.
- Les événements ne prouvent **jamais** que l'utilisateur a lu le texte ou entendu la voix. L'absence d'événement peut signifier une destination sans accusé (mobile/Twitch), un contexte non lié, une défaillance du journal ou une interruption ; ce n'est pas un échec de livraison démontré.

Les tests ciblés `tests/test_jade_delivery_observation.py` simulent la panne indépendante des deux sinks, une preuve invalidée/hors tour, une lecture ffplay réussie/échouée/désactivée et une session Discord acceptée/refusée. Les anciens tests de rappel d'un dictionnaire depuis `on_reply` ont été retirés : ils validaient précisément le couplage indésirable.

**Réserve de recette :** vérifier sur Discord réel les horodatages et l'exactitude des événements de fin audio ; le gain de robustesse est établi par tests hors ligne, pas par une mesure en production.

## Validation et suite

Aucun appel OpenAI ni Discord/Twitch réel lancé par les tests. Après CI complète : transférer les deux cartes DEV dans REC au statut `À valider` si seul l'essai réel du propriétaire reste (sans doublon DEV/REC actif). Recette : masquer/remontrer le Live2D mobile et vérifier la reprise de voix/expressions ; observer les journaux d'une réponse Discord, d'une lecture vocale et d'une interruption, et vérifier que les simples handoffs restent non confirmés.

Les tests unitaires et les mesures de coût ne constituent pas une preuve de gain de FPS, de batterie ou de vraie livraison mobile. Ne pas clôturer en `Done` sur seule absence de régression.
