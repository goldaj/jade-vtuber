# Push-to-talk et secousses dans la PWA

26 novembre 2026 · base `2699ced` sur `develop` · DEV-039 → REC-042 (P1) et UX-20 → REC-043 (P3).

## Fonctionnement

- Le bouton micro classique enregistre pendant l’appui tactile, souris ou clavier. Les trames PCM commencent à partir dès que le WebSocket est prêt. Le relâchement libère le micro et signale la fin d’énoncé une seule fois. Un silence pendant le maintien ne termine pas la prise. Au plafond de 20 s, le micro se ferme et la fin attend le relâchement. Un geste annulé ou interrompu libère les ressources. Le secours WAV ne double pas une conversation déjà confirmée par le WebSocket.
- Dans **Profil**, le réglage **Réagir aux secousses** s’active pour le salon ouvert. Une accélération qui s’inverse rapidement déclenche une impulsion amortie des angles du r21 dans Live2D. Elle anime le modèle autour du zoom et du placement choisis. L’effet est réservé à l’Accueil et au plein écran et se met en pause en arrière-plan ou selon la préférence de mouvement réduit.

## Vérifications intégrées

- Chromium a envoyé des trames au vrai gateway HTTPS/WSS avant le relâchement. Un silence simulé de 1,45 s est resté dans la prise. Le relâchement hors du bouton a fermé les pistes et produit une fin, une transcription simulée et une réponse de recette. L’autorisation micro accordée après relâchement et l’annulation tactile n’ont créé aucun tour. Le clavier dans Chat et le micro du plein écran ont aussi été exercés.
- Avec le vrai SDK WebGL et des événements capteur simulés, le r21 a reçu une impulsion dynamique. Sa contribution aux paramètres est revenue à zéro après amortissement, tandis que l’échelle et la position du modèle sont restées identiques. Le plein écran, le refus de permission, les mini-scènes, le réglage désactivé et le r20 ont été vérifiés. Aucun appareil autorisé n’était visible via ADB.
- Sept suites Node ciblées et 26 tests Python des transports, du micro et du backlog ont réussi. Les essais ont utilisé une source audio et un fournisseur de recette locaux.

Après le signalement du propriétaire, une nouvelle recette Chromium a mesuré le déplacement du vrai r21 à 393 × 873. Une forte secousse simulée a déplacé la silhouette de 54 px dans un sens puis de 46 px dans l’autre, avec une impulsion de 23° dans le rig. Le déplacement atteint 64 px en plein écran. Le zoom et le placement au repos sont restitués exactement. Le scénario couvre aussi des données brutes avec gravité, un axe manquant, une secousse modérée, la marche, un choc isolé et les vues qui écartent l’effet. Le test physique sur le Redmi reste nécessaire.

Pour distinguer accès au capteur et amplitude, cocher **Réagir aux secousses** dans Profil, revenir à l’Accueil avec le r21, secouer puis consulter le statut dans Profil. Si aucune donnée n’est reçue, vérifier l’autorisation de capteurs du site dans Chrome sur Android. [Aide Chrome](https://support.google.com/chrome/answer/114662?co=GENIE.Platform%3DAndroid&hl=fr)

## Recette Redmi

- Maintenir le micro sur l’Accueil, dans Chat et en plein écran. Parler avec un silence intermédiaire. Relâcher hors du bouton. Vérifier une seule réponse, puis la libération immédiate du micro. Essayer un appui trop bref, un passage en arrière-plan, un verrouillage, une rotation, une coupure réseau et un refus de permission.
- Activer la secousse depuis Profil. Vérifier sur le r21 un effet net mais court dans les deux pièces et en plein écran. Refaire le test après zoom et déplacement, puis après un changement de modèle ou d’onglet. Essayer une rotation, les mouvements ordinaires, la désactivation et le mouvement réduit. Régler la sensibilité après observation sur l’appareil.

Les deux scénarios sont suivis dans [REC-042 et REC-043](../../backlog/02-RECETTE.md).

## Échanges accessibles

- **Utilisateur, extrait** « une amélioration sur le push to talk, pour que ça soit vraiment en push & relache pour parler ».
- **Utilisateur, extrait** « quand je secoue le téléphone ça fasse les petits mouvements, la P3 ».
- **Assistant, synthèse** Le micro capture pendant l’appui et termine la prise au relâchement. La secousse anime le r21 autour du placement choisi.
- **Utilisateur, résumé** Le push-to-talk lui convient. La secousse ne produit aucun effet perceptible sur son téléphone. Il demande comment l’activer et souhaite un mouvement flagrant, exagéré pour les grosses secousses.

Extraits et synthèse du chat actif du 26 novembre 2026. Heures individuelles indisponibles.
