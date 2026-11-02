# Décisions de refonte de Jade (24 octobre 2026)

## Portée validée par le propriétaire
- Priorité au fonctionnement **rapide** plutôt qu'aux moteurs de qualité maximale.
- **Exclusivité OpenAI pour STT et TTS** dans le chemin applicatif : supprimer ElevenLabs, Google TTS et tout moteur de transcription tiers, y compris dépendances mortes.
- Choix initial **`gpt-4o-mini-transcribe`** pour transcription, **`gpt-4o-mini-tts`** pour voix (WAV pour lecture simple) ; les identifiants sont **configurables** via environnement et le coût n'est jamais encouru dans les tests. Ce ne sont pas des revendications de benchmark de latence.
- Dialogue via un fournisseur interchangeable : OpenAI dans la première version, possibilité d'un modèle local ensuite sans recoder Twitch/Discord/audio.
- Assets Cubism r21 v30, candidat r02, runtime VTS r20 et manifestes LFS sont intouchables par la refonte Python. Les autres modèles/branches peuvent être audités mais pas fusionnés aveuglément.
- Aucun login Twitch/Discord, appel OpenAI payant ni sortie audio dans les tests CI. Tout ce qui nécessite appareils/comptes reste à confirmer localement.
- Secrets via variables process / `JADE_SECRETS_FILE`. Dépôt privé avec anciens identifiants dans l'historique. Ne pas publier sans purge et rotation.
- Travaux isolés sur `codex/chat-gpt6-jade-rebuild`, sans merge. `develop` modifié uniquement pour notification à Codex.

## Séquencement produit révisé
1. Inventaire et fondations, tests CI hors ligne, configuration stricte.
2. Cœur asynchrone et queue (gestion des erreurs, isolation, backpressure).
3. Dialogue texte fonctionnel via OpenAI ou doubles de test.
4. **TTS OpenAI uniquement** avec sous-titres OBS et lecture WAV ordonnée.
5. **STT OpenAI uniquement**, microphone capturé localement (capture audio non-IA) et gestion des erreurs.
6. Twitch texte avec authentification et reconnexion.
7. VTube Studio WebSocket et expressions.
8. Discord texte.
9. Discord vocal sous consentement explicite, audio reçu et STT OpenAI.
10. Mémoire bornée et client léger local sécurisé.
11. Nettoyage contrôlé code mort, dépendances, preuves, documentation.

## Décision complémentaire du propriétaire — 29 octobre 2026 : Tera / Astra

- **Modèle d'exécution préféré : Tera 6.1**, plutôt qu'Astra, pour Jade
  en général et **par défaut** pour les tâches utilisant directement
  l'ordinateur, le dessin, les animations, le rig, la physique du modèle
  Live2D, les retouches et les exports.
- **Tera prend l'initiative d'une escalade motivée** lorsqu'un doute justifie
  Astra : finaliser et tracer le lot courant dans un état sûr, puis demander
  à l'humain de **basculer manuellement sur Astra**. Pas de changement
  de modèle réalisé en silence ou sans demande humaine.
- **Le propriétaire contrôle lui-même les revues Astra additionnelles** :
  elles ne font pas partie du workflow imposé à Tera, même si le propriétaire
  peut décider ultérieurement de vérifier chaque livraison ou certains lots.
- Motif : privilégier les capacités pratiques de Tera et la consommation
  de tokens, sans sacrifier la traçabilité ou la sécurité des sources.
- Voir `docs/gpt6-jade/TERA-ASTRA-WORKFLOW.md` pour les critères et
  la formulation de passation. Aucune action automatique de publication,
  de connexion aux comptes ou de migration des secrets n'en découle.

## Critères de confiance
Des tests simulés verts prouvent le bon fonctionnement de certaines interfaces,
**pas** la qualité de la voix, le fonctionnement en réel, les permissions des plateformes,
ni la latence réseau mesurée. Ne pas annoncer une fonctionnalité comme testée matériellement.
