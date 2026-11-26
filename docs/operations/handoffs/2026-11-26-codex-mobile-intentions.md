# DEV-001 · Chronologie des intentions sur mobile

Codex, 26 novembre 2026. Première étape de DEV-001 sur `develop`, base `80b30b1`. La recette de ce lot porte sur la PWA. Les essais dans VTube Studio et Discord restent hors de ce lot. [Backlog](../../backlog/01-DEVELOPPEMENT.md)

## Jeu de la réplique

- Une intention donne une pose initiale de la bouche et des sourcils et un tirage A/B à chances égales au début de chaque réponse. Le clip sélectionné se prépare pendant la pose. Le clignement automatique continue.
- Le premier tampon vise 200 ms d’avance pour la pose. Les transitions courtes entre fragments conservent la même intention. Quand la source a joué son dernier tampon et que le transport est terminé, la bouche se ferme, la pose tient 600 ms et le r21 revient vers le repos en 220 ms. Le parcours sans audio joue une réaction courte.
- Une nouvelle demande, une coupure, la mise en arrière-plan ou la bascule vers le r20 annulent le tour. La PWA ignore les callbacks devenus obsolètes.

## Vérifications mobiles

- Les bancs Node de l’avatar, du lecteur et du duplex passent. Ils couvrent les deux tirages de chaque intention et une répétition A/A, un trou entre fragments, la fin du dernier PCM, le secours WAV, le fondu et les callbacks après la bascule.
- La passe indépendante dans Edge à 393 × 873 charge le vrai r21 v45.1 avec WebGL et lit du PCM synthétique en Web Audio. Sur Sérieuse, la demande de pose précède le premier son planifié de 201 ms. La bouche garde sa forme pendant une pause PCM de plus d’une seconde et après le dernier son, puis l’échantillonnage détecte le début du fondu vers +655 ms. Un seul geste Sérieuse est joué. La recette physique Redmi et l’écoute de vraies répliques restent à faire.

## Comparaison vocale et suite

Le mobile et Discord partagent les consignes d’intention, le moteur Realtime et les réglages de voix. La parole anticipée était désactivée dans les démarrages récents examinés. Discord précharge environ 100 ms de PCM. La PWA pouvait ajouter 50 ms lors de la reprise d’un fragment tardif, avec un visage qui retournait au neutre. Le lecteur mobile reprend désormais dès qu’un tampon tardif est prêt et mesure la durée des creux dus à l’arrivée des fragments.

La comparaison du code établit l’écart de lecture. Le propriétaire a confirmé ensuite que le son fonctionne bien sur son téléphone. Les réglages vocaux en place sont conservés.

## Deuxième étape — Sérieuse et Enjouée

- **Sérieuse** garde une bouche sobre, un front presque symétrique et un buste stable. Les deux clips sont « Se redresser » et « Marquer le propos ».
- **Enjouée** garde un sourire léger, un sourcil relevé et des paupières légèrement asymétriques. Les deux clips sont « Feinte de côté » et « Balancement complice ». L’asymétrie s’inverse avec la variante. Les attitudes restent après le geste si la réponse continue.
- Cette première passe a utilisé le jeu des paupières et des sourcils. L’audit natif de l’étape suivante a clarifié le rôle des plaques de regard.
- Le premier réglage laissait une légère courbe de sourire sur la bouche fermée de Sérieuse. Le réglage final ramène le relief aux commissures de 7 px natifs au neutre à environ 3,4 px. À mi-ouverture, contour, dents, langue et intérieur restent solidaires.
- Après avoir observé un geste encore en téléchargement au moment du retour au repos, le client prépare les quatre clips au chargement du r21 et vérifie que la réponse est toujours active avant tout déclenchement différé.

La passe indépendante dans Chromium à 393 × 873 a rejoué le même texte et le même audio synthétique dans les quatre variantes. Chaque clip a démarré une seule fois. Enjouée B a tenu sur 5,84 s, à travers un trou PCM de 720 ms et après la fin du clip. Lors d’un autre essai, la bascule vers le r20 a coupé sept sources encore en file. Un clignement fermé complet a été observé pendant le maintien de Sérieuse. Les expressions du visage restent discrètes au cadrage large. La différenciation repose aussi sur les mouvements de tête et du buste. La validation du nouveau jeu sur le téléphone physique reste ouverte.

Les deux variantes Sérieuse ont été rejouées après la correction finale de la bouche. Elles tiennent la nouvelle forme durant la parole et avec la bouche fermée, puis fondent vers le repos. Les portraits zoomés montrent une ligne plus droite.

Le propriétaire autorise de revenir au dessin, au rig ou à l’animation lorsque les ressources actuelles limitent le rendu. Il demande de finir Sérieuse et Enjouée avant la reprise de l’ensemble des quatorze variantes.

## Troisième étape — Regard, rig et quatre gestes

- Les deux pièces historiquement appelées `SOCKET_SKIN` contiennent depuis le v45.1 les iris, pupilles et reflets. La course réelle de départ est de ±15 px en X et ±8 px en Y. La copie native v45.2 porte ces courses à ±26 et ±12 px en retouchant 64 formes hors neutre. La comparaison des exports Core conserve les masques, les UV, l’ordre de dessin et la géométrie des autres pièces. Les yeux complètement fermés sont identiques avant et après l’ajout d’un regard.
- Enjouée A engage l’œil avant la feinte. Enjouée B répartit deux accents latéraux avec des appuis et des retards d’oreilles distincts. Sérieuse A prend appui puis se redresse. Sérieuse B marque un hochement bref. Le premier accent arrive dans la phrase. Le repère Huohuo a guidé la continuité, les retards et la lisibilité à l’échelle du visage. La bouche reprend le dessin natif v43, avec un sourire adouci à l’ouverture pour Enjouée.
- L’export SDK 5.0 a été réalisé dans la session Cubism existante. Le manifeste mobile sélectionne le [nouvel export et les quatre motions](../../../jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/Jade_r21_v45/mobile/). Les [courbes sources éditables](../../../jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/Edition/mobile-intentions/) suivent le format PSD2Live. La livraison v45.1 reste la référence native et fournit les textures, la physique et les dix autres gestes.
- La passe Chromium à 393 × 873 associe WebGL, le MOC3 mobile et Web Audio. Les quatre clips se jouent sur la même phrase française de 4,31 s, synthétisée hors ligne. Pour Enjouée B, une pause PCM d’environ 0,9 s ferme la bouche et conserve la pose. Sérieuse B marque son hochement sur une phrase de 1,65 s. La bascule vers le r20 coupe les sources audio et invalide les événements tardifs. La validation physique sur Redmi reste ouverte.

## Quatrième étape — Dix variantes restantes

Le propriétaire a demandé le niveau de soin du lot Sérieuse et Enjouée pour les cinq intentions restantes. La direction de jeu utilise la séquence regard, tête et transfert d’appui pour rendre le premier accent lisible sur un écran de téléphone. Les silhouettes et la souplesse des retours s’appuient sur le repère Huohuo et le dessin maître de Jade.

| Intention | Variante A | Variante B |
| --- | --- | --- |
| Neutre | Accueille le propos avec un léger transfert du poids et se tourne vers l’interlocuteur. | Écoute de l’autre côté du corps, puis acquiesce d’un petit mouvement du menton. |
| Curieuse | Cherche du regard avant d’incliner la tête vers ce qui l’intéresse. | Explore une première direction, se ravise et relève la tête au déclic. |
| Enthousiaste | Prend appui et s’élance vers le haut, avec un rebond plus léger. | Ouvre le buste de côté puis relève la tête dans un deuxième temps. |
| Tendre | Penche la tête vers l’épaule et baisse brièvement les yeux avant de retrouver le regard. | Avance légèrement pour confier quelque chose et ramène le regard vers l’interlocuteur. |
| Rassurante | Marque un acquiescement posé et stabilise ses appuis. | Ouvre le buste en oblique et revient lentement au centre avec un regard présent. |

Les [quatorze exports mobiles](../../../jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/Jade_r21_v45/mobile/) et leurs [courbes éditables](../../../jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/Edition/mobile-intentions/) composent désormais un seul lot. Le schéma `motion_put` du MCP PSD2Live a servi à contrôler les fichiers éditables. Le même MOC3 v45.2 permet d’obtenir les poses et les appuis recherchés.

**Recette Codex du 26 novembre 2026.** Le contrôle Core des dix clips préserve les appuis des chaussures et permet de comparer les poses intermédiaires à la tête, au visage et aux raccords du dessin maître. Une deuxième passe a redonné du déplacement à la confidence de Tendre B et recentré l’acquiescement de Rassurante A. La relecture de Rassurante a conservé un regard presque frontal pour les deux variantes.

Les dix variantes finales ont été jouées séparément dans la PWA avec Chromium et WebGL en portrait 393 × 873, sur la même phrase française de 4,31 s synthétisée hors ligne. Chaque variante déclenche une seule motion avec la pose visible avant la voix. La bouche articule puis tient sa forme fermée jusqu’au fondu. Les tests représentatifs passent aussi sur Curieuse B en réponse courte de 1,64 s, Tendre B avec une pause PCM d’environ 0,91 s et l’interruption par une bascule de modèle. Les yeux peuvent se fermer complètement et le regard reste mobile derrière les masques. La recette matérielle Redmi est distincte de cette passe Chromium.

## Sourires de trois-quarts

Le propriétaire signale une déformation dans les sourires de profil sur l’exemple Enthousiaste B. La reprise exacte dans Cubism Core utilise `ParamAngleX=+22,79°`, `ParamAngleY=+10,63°`, `ParamAngleZ=−7,48°`, `ParamMouthOpenY=1` et `ParamMouthForm=.29`. Le diagnostic par couche montre une bande de dents très claire et trop large. Elle touche visuellement la peau au-dessus de la cavité. Les quatre maillages ouverts coïncident sur la même pose et le sprite fermé est à opacité zéro.

La copie native v45.3 retouche uniquement la plaque des dents supérieures, avec un ivoire plus court et une ombre sous la lèvre. L’atlas du manifeste mobile change de 362 pixels dans cette tuile. Le MOC3, les maillages, les masques et les clips restent utilisables avec le même rig. Dans la PWA, l’ouverture maximale de ce sourire en trois-quarts passe progressivement à environ .87 sur le même signal. La correction dépend de l’angle et reste continue et symétrique. De face, la parole garde toute sa course.

La recette Chromium à 393 × 873 rejoue 16 poses fixes, dont le cas signalé et son miroir, puis teste les ouvertures commandées par la PWA et une réplique française d’Enthousiaste B. Le trait supérieur et la cavité se rejoignent visuellement dans les deux trois-quarts. À ±22,79°, une ouverture de .35 devient .344, une ouverture de .65 devient .614 et l’ouverture maximale du sourire devient .870. De face et sur Sérieuse, l’ouverture maximale reste à 1. La bouche revient à zéro après la parole.

## Rotation du visage de trois-quarts

Les deux captures mobiles signalent un désaccord entre les traits et le contour, visible aussi à bouche fermée. Dans la rotation horizontale seule, le nez et la bouche se déplaçaient d’environ 77 px dans le dessin à 23°, contre environ 42 px pour le menton. L’œil proche gagnait environ 10 % de largeur. Deux anciens traits de cils étaient encore peints dans le fond des tempes et devenaient visibles quand les mèches s’écartaient.

Le v45.4 recale six poses du déformeur commun du visage. La joue éloignée se resserre, le menton accompagne les traits et le nez prend de l’avance sur la bouche. La retouche locale du dessin couvre 3 347 pixels RVB à l’emplacement des cils parasites et conserve l’alpha. La retouche v45.3 de la bouche reste dans le paquet mobile. Le CMO3 éditable et la plaque de peau sont conservés dans l’atelier Jade sur D:.

Dans les deux poses signalées, l’écart horizontal du centre de la bouche à l’axe nez–menton passe de −12,6 et +21,1 px à +1,5 et +6,3 px dans le dessin. Les poses sans rotation horizontale gardent les mêmes sommets. Les vrais sprites de fermeture restent visibles aux deux extrêmes et le MOC3 SDK 5.0 garde les masques et les coordonnées d’atlas.

Le manifeste par défaut de la PWA charge cet export dans Chromium en 393 × 873. Le contrôle rejoue les deux vues, une pose de face et une réplique Enthousiaste B en PCM. Le clignement SDK ferme les deux paupières pendant l’articulation à 19,6° et la bouche se referme à la fin de la voix. La recette s’est déroulée en émulation mobile Chromium.
