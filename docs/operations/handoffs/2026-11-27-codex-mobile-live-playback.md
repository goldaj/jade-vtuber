# Voix Live et commandes de la PWA

- Branche `fix/mobile-live-playback-ui-20261127`, depuis `develop@81c28d2`. Les recettes REC-041, REC-048, REC-049 et REC-050 restent à valider sur Redmi.
- Revue par domaines. WebRTC : la transcription arrive via les événements, tandis que l’audio distant dépendait uniquement du graphe Web Audio. Ajout d’un lecteur natif suivant le [guide WebRTC de GPT-Live](https://developers.openai.com/api/docs/guides/voice-webrtc). L’analyseur mesure la piste reçue pour entraîner la bouche et la motion. Si la lecture est bloquée, le lecteur est mis en sourdine et le graphe déverrouillé assure l’unique sortie sonore. Le démontage de la piste coupe les deux et remet la bouche au repos.
- Interface : le micro rouge est un indicateur dans les vues de conversation lorsque Live est sélectionné. Le geste de démarrage ou de coupure est dans Config. La case Live tente de démarrer la capture lors d’une activation explicite. Au rechargement, la préférence reste distincte de la capture. Accueil affiche la pastille et « Live » ; ailleurs seule la pastille est visible. Le micro classique utilise sa couleur et ses noms accessibles. Le bouton de sortie du plein écran utilise un tracé vectoriel centré.
- Gestes : dans la zone de saisie du r21, un toucher qui atteint la silhouette annule le geste natif de la WebView. Le maintien, le pincement et le double appui restent gérés par la scène. Dans le décor, le comportement de la WebView est conservé.
- Un bouclage entre deux pairs WebRTC sous Edge 158 reçoit des paquets RTP et un signal synthétique de 440 Hz. L’ancien graphe mesure un niveau nul malgré les paquets. Avec le lecteur attaché à la même piste, la lecture démarre et le niveau RMS monte à 0,107. La sortie du navigateur de test est muette au niveau du processus. Un essai tactile Chromium vérifie le maintien de 1,4 s suivi du glissement et du relâchement sans annulation de pointeur, avec maintien du comportement natif hors silhouette.
- Les régressions hors ligne couvrent la piste distante, l’absence de double sortie, le refus de lecture, les arrêts et les états visuels. Sur Redmi, vérifier une réponse audible avec mouvement des lèvres en Accueil et en plein écran, le retour au micro classique, et le déplacement du r21 avec un maintien.

## Échanges accessibles

- **Propriétaire** (synthèse du 27 novembre) Jade répond par écrit en Live, sans voix ni réaction du modèle. Demande un micro rouge sans geste ni texte sur la scène, une pastille Live selon la vue, une icône de sortie du plein écran centrée et un correctif simple pour le maintien sur Jade. Demande une revue par domaines et la CI avant livraison sur `develop`.
- **Assistant** (synthèse) Corrige la sortie audio et son cycle de vie, fait relire les gestuelles et l’interface, puis vérifie la branche d’intégration.

Les heures individuelles ne sont pas disponibles.
