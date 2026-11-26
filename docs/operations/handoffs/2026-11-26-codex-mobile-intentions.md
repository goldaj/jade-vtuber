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
- Dans le MOC3 v45.1, les entrées de regard bougent la peau des orbites et laissent les iris en place. Le jeu des paupières et des sourcils donne donc l’attitude du regard sur ces deux intentions. Le clignement complet est préservé.
- Le premier réglage laissait une légère courbe de sourire sur la bouche fermée de Sérieuse. Le réglage final ramène le relief aux commissures de 7 px natifs au neutre à environ 3,4 px. À mi-ouverture, contour, dents, langue et intérieur restent solidaires.
- Après avoir observé un geste encore en téléchargement au moment du retour au repos, le client prépare les quatre clips au chargement du r21 et vérifie que la réponse est toujours active avant tout déclenchement différé.

La passe indépendante dans Chromium à 393 × 873 a rejoué le même texte et le même audio synthétique dans les quatre variantes. Chaque clip a démarré une seule fois. Enjouée B a tenu sur 5,84 s, à travers un trou PCM de 720 ms et après la fin du clip. Lors d’un autre essai, la bascule vers le r20 a coupé sept sources encore en file. Un clignement fermé complet a été observé pendant le maintien de Sérieuse. Les expressions du visage restent discrètes au cadrage large. La différenciation repose aussi sur les mouvements de tête et du buste. La validation du nouveau jeu sur le téléphone physique reste ouverte.

Les deux variantes Sérieuse ont été rejouées après la correction finale de la bouche. Elles tiennent la nouvelle forme durant la parole et avec la bouche fermée, puis fondent vers le repos. Les portraits zoomés montrent une ligne plus droite.

Le propriétaire autorise de revenir au dessin, au rig ou à l’animation lorsque les ressources actuelles limitent le rendu. Pour le regard, [ART-006](../../backlog/04-PRODUCTION-2D.md) porte la reprise sur une copie native. Le contrôle mobile se fera sur le déplacement réel des iris, les reflets et le masque, en combinant regard, clignement, parole et rotations de tête. La même revue permettra de décider quelles autres intentions demandent une reprise de dessin ou de courbes avant de les intégrer.
