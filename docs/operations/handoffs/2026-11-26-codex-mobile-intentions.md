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

La comparaison du code établit l’écart de lecture. L’écoute mobile devra établir l’écart de jeu vocal en comparant la même phrase dans deux intentions opposées. Les poses livrées ici servent à valider la chronologie. Le travail artistique sur le regard, les sept poses complètes et la gestuelle en pied suit dans DEV-001.
