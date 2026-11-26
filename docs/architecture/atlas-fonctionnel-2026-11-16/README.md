# Jade : atlas de la boucle fonctionnelle intégrale

**Extension postérieure :** [Live mobile du 26/11](../LIVE_MOBILE.md), intégré sur develop depuis `90ec0c7`, ajoute une conversation orale native concurrente et des délégations dans l'arbitre existant. L'atlas ci-dessous conserve sa date et son SHA ; il ne décrit pas ce nouveau transport ni sa recette.

Référence : `goldaj/jade-vtuber` • branche `develop` • commit GitHub `a841628b37d9d7449c8aeb5c6ca45bc679746655` (15/11/2026) • analyse du 16/11/2026.

**Lecture** : les SVG sont les schémas vectoriels de référence. Les PNG sont des rendus d’aperçu. L'exécution réelle dépend de la configuration privée du PC et n’a pas été vérifiée sur le matériel.

## Les cinq vues

1. `01_boucle_maitre.svg` : entrées, décisions locales/IA, traversées réseau, dialogue, sorties, mémoire et retour au tour suivant.
2. `02_decisions_canaux.svg` : politique de sélection propre à Twitch, Discord écrit/vocal, PC, Android, HTTP/console.
3. `03_parallelisme_voix.svg` : parallélisme réel, chaîne vocale courante, voie anticipée conditionnelle, Android et curation asynchrone.
4. `04_memoire_et_identites.svg` : mémoire de session, journal exact, décision IA séparée de sélection de souvenirs, contrôles d'accès et oubli.
5. `05_sorties_et_exceptions.svg` : confidentialité des sorties, autorisations, interruptions, journaux, maintenance et tâches annexes.

## Avertissements d’interprétation

- La **file de dialogue ne traite qu'un tour principal à la fois**. Les connexions, certains sous-traitements et la sélection différée des souvenirs peuvent continuer en parallèle.
- Le **tri initial Discord/Twitch/vocal** contient des règles et des tirages aléatoires. Ce n’est pas, dans le code actuel, un appel au modèle à chaque message.
- L’**arbitrage IA entre conversations** n'a lieu que s’il y a au moins deux conversations en attente et si les règles de repli/équité ne court-circuitent pas l'appel.
- Le **dialogue IA** peut être évité pour une commande mémoire ou un message non sélectionné.
- La **transcription** est un appel distant pour les voix. La **synthèse vocale** est un autre appel, seulement si la sortie autorisée le requiert.
- La **voix anticipée** exige une sortie locale désactivée (`none`) ; le lancement de tous les canaux vérifie que la sortie locale est `ffplay`. La voie progressive ne doit donc pas être représentée comme active dans ce profil.
- Pour les **réponses tamponnées**, l'historique de session en RAM est actualisé avant la distribution ; pour la **voie vocale anticipée**, la validation de l'historique attend la lecture/abandon du flux. L'enregistrement SQLite des échanges complets a lieu après le traitement de la sortie, si autorisé.
- La **curation des souvenirs** fait un *troisième type d'appel IA* indépendant (après arbitrage éventuel et dialogue). Ce travail est lancé après la réponse, n'est pas bloquant pour la suivante et peut ne pas aboutir.
- Les souvenirs ne sont pas injectés sans limite : historique récent borné, scope isolé, mémoires sélectionnées ; les données issues d'autres personnes ne sont pas des instructions.
- Pour l'**application Android**, le TTS est déclenché après la réponse, puis texte, intention et son sont renvoyés ensemble. Son affichage Live2D est distinct du rendu PC.
- **OBS** récupère les sous-titres/audio/visuels via des outils locaux ; Jade ne pilote pas directement tout le transport du stream Twitch.
- Les journaux de sorties représentent surtout des **destinations prévues**, pas des preuves de livraison. Des sorties facultatives peuvent échouer sans faire échouer le dialogue.
- Le modèle 2D actuel utilise des expressions de substitution. Les 14 animations dédiées prévues ne sont pas encore des animations finales intégrées.
- Ce sont des **cartes fonctionnelles** construites par lecture du code, pas une preuve exhaustive du comportement sur une installation privée. Les branches historiques ou des expériences qui ne sont pas reliées au lancement actif sont exclues de la boucle courante.

## Source du code vérifié

- [Point d'entrée / lancement](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/main.py)
- [Arbitrage et exécution principale](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/src/jade_runtime/orchestrator.py)
- [Décision de priorité](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/src/jade_runtime/turn_arbitration.py)
- [Dialogue et contexte](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/src/jade_runtime/dialogue.py)
- [Décisions Discord écrit](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/src/jade_runtime/discord_text_policy.py)
- [Décisions Discord vocal](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/src/jade_runtime/voice_decision.py)
- [Moteur de mémoire et curation](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/src/jade_runtime/memory_service.py)
- [Sorties vocales](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/src/jade_runtime/output.py)
- [Passerelle Android](https://github.com/goldaj/jade-vtuber/blob/a841628b37d9d7449c8aeb5c6ca45bc679746655/src/jade_runtime/mobile_gateway.py)
## Représentations compactes et lisibilité

Les cinq SVG versionnés ici utilisent des cartes organisées sans espaces inutiles ; les décisions détaillées et les allers-retours sont explicités dans le contrat fonctionnel (dont les diagrammes Mermaid). Les anciennes images du 15 novembre restent archivées à l'index parent.
