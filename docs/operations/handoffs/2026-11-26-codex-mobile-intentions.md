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
