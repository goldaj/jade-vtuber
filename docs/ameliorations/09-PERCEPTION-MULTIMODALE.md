# Perception multimodale : images fixes et flux vidéo

**Propositions du propriétaire — 18 novembre 2026.** Il s'agit d'**idées à concevoir**, pas de fonctionnalités déclarées présentes dans le code, ni d'une autorisation d'activer la capture ou des API payantes. La perception est une **entrée** pour Jade, distincte de la visibilité de son propre avatar Live2D (voir [04-AVATAR-VISIBILITE.md](04-AVATAR-VISIBILITE.md)).

## 1. Voir et comprendre les contenus statiques

**Intention produit :** permettre à Jade de recevoir des images statiques, textes visibles, photos, illustrations, dessins, captures d'écran, interfaces et autres documents visuels, de les comprendre dans leur contexte et **d'y réagir naturellement en direct** en texte ou en voix selon le canal d'origine et les autorisations.

| ID | Priorité / nature | Proposition et conditions de réussite |
| --- | --- | --- |
| PER-01 | P2 / P | **Réception d'images fixes** via connecteurs compatibles : pièces jointes et images de messages, dépôt explicite d'image sur la PWA/PC, capture d'écran partagée volontairement ; prévoir un adaptateur pour les sources futures sans coupler le moteur à une plateforme. |
| PER-02 | P2 / P | **Compréhension visuelle et textuelle** : photo, dessin, capture, texte intégré à l'image, interface, schéma ; utiliser une capacité de vision multimodale et, au besoin, une extraction de texte adaptée, en conservant les limites d'interprétation et l'incertitude. |
| PER-03 | P2 / P | **Réaction conversationnelle contextualisée** : identifier le contenu montré, relier l'observation à la discussion, pouvoir commenter ou répondre à une question sur l'image, avec sortie sur le seul canal autorisé. Éviter les réactions non sollicitées répétitives ; permettre d'activer/désactiver les commentaires spontanés. |
| PER-04 | P1 / C | **Consentement et périmètre** : aucune surveillance de bureau, capture de fenêtre, ingestion d'images privées ou propagation en stream par défaut ; sources explicitement autorisées, sessions isolées, limites de taille/format, politique de conservation et masquage des données sensibles. |

### Scénarios attendus
- Un utilisateur montre à Jade une photo, un dessin ou un mème : elle peut le décrire, poser une remarque pertinente ou répondre oralement à une question si le canal est vocal.
- Une capture d'écran contient une interface, un graphique ou du texte : Jade peut lire ce qui est visible et réagir à cette information, sans inventer les éléments illisibles.
- Plusieurs images arrivent pendant une conversation : Jade distingue les images et leur ordre, en conservant la référence à l'image commentée.

## 2. Voir le mouvement : jeux vidéo, vidéos, films et animations

**Intention produit :** permettre à Jade de **suivre un flux visuel évolutif**, en particulier un jeu vidéo, un film, une vidéo ou une animation, pour comprendre ce qui se passe au fil du temps et réagir au bon moment.

| ID | Priorité / nature | Proposition et conditions de réussite |
| --- | --- | --- |
| PER-05 | P2 / P | **Entrées vidéo interchangeables** : partage d'écran/jeu consenti, capture d'une fenêtre ou d'une source vidéo autorisée, lecture d'un fichier ou flux accessible, connecteurs compatibles Discord/PC/PWA selon possibilités réelles des API ; ne pas présumer que toute plateforme expose la vidéo. |
| PER-06 | P2 / P | **Perception temporelle** : analyser des images échantillonnées, leur horodatage, les changements de scène, les mouvements et les événements dans une fenêtre de contexte glissante ; ne pas réduire une vidéo à une seule image isolée. |
| PER-07 | P2 / P | **Audio et vidéo coordonnés si disponibles** : joindre facultativement STT/sons/événements au flux d'images, synchroniser les horodatages sans perturber la conversation vocale de Jade ; distinguer ce que Jade a effectivement vu ou entendu de ce qu'elle déduit. |
| PER-08 | P2 / P | **Réactions live pertinentes** : commenter une scène ou une action en jeu, répondre à « qu'est-ce qui vient de se passer ? », gérer la temporalité des interventions et le contexte récent sans monopoliser la voix, le chat ou le moteur d'inférence. |
| PER-09 | P2 / P | **Budget et adaptation dynamique** : fréquence d'analyse configurable, images clés/détection de changements, cadence réduite en inactivité, backpressure, limites CPU/GPU/bande passante/coût API, mode dégradé et arrêt immédiat lorsque la source cesse ou est révoquée. |
| PER-10 | P1 / C | **Sources autorisées et confidentialité** : démarrage/arrêt explicites, indicateur de capture active, restriction à la fenêtre/au flux consenti, respect des droits sur médias et de la vie privée, aucune rediffusion non autorisée des contenus ou des réactions en public. |

### Scénarios attendus
- Pendant une partie, Jade remarque un événement notable et y réagit sans qu'on ait à lui envoyer une capture à chaque fois.
- Sur une vidéo, un film ou une animation autorisé, Jade suit les évolutions et peut commenter une séquence précise, pas seulement une image figée.
- Une source vidéo passe hors ligne ou la capture est désactivée : Jade cesse de l'analyser et ne continue pas à faire croire qu'elle voit des images actuelles.

## Architecture attendue et critères transverses

1. **Contrat d'entrée commun** : `VisualObservation` (source, session, audience/autorisations, type image/frame, temps de capture, référent média, éventuellement transcription et métadonnées). Définir sa forme réelle lors de la conception, pas ici comme API implémentée.
2. **Pipeline indépendant** : `VisualSourceAdapter → FrameSampler/Preprocessor → VisionProvider → Context/EventRouter → ConversationEngine → OutputRouter`. Adapter images, vidéos, modèles de vision et sorties sans réécrire les connecteurs ; voir [05-ARCHITECTURE-IA.md](05-ARCHITECTURE-IA.md).
3. **Compétences facultatives** : Jade conserve Discord, Twitch, voix, mémoire, PWA et avatar lorsqu'une entrée visuelle ou un fournisseur de vision est désactivé/indisponible. Le contenu perçu n'est partagé qu'avec la session et l'audience qui y ont droit.
4. **Qualité mesurable** : pour les images, justesse et délai de réaction ; pour les vidéos, pertinence temporelle, retard entre événement et réaction, coût/minute, consommation des ressources, fausses observations, interruptions et fonctionnement simultané avec les autres canaux.
5. **Livraison incrémentale** : commencer par quelques formats et une source image explicitement choisie ; ensuite captation vidéo échantillonnée et comparaison de fournisseurs ; ajouter l'audio synchronisé et les commentaires spontanés seulement après validation de la confidentialité et des coûts.

**Statut au 18/11/2026 :** propositions documentaires uniquement. Aucun code, connecteur de capture ou abonnement facturé ajouté par cette note.
