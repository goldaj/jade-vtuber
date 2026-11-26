# ART-013 · Les oreilles dans le jeu de Jade

Le 26 novembre 2026, le propriétaire a validé le lot Sérieuse et Enjouée et donné la priorité P0 aux oreilles. La reprise des dix autres variantes vient ensuite. [Backlog artistique](../../backlog/04-PRODUCTION-2D.md)

## Respiration et intentions

Les deux oreilles utilisent les pièces visibles du r21. Les attaches restent fixes pendant que les pointes se soulèvent ou s’abaissent. La PWA lit le souffle effectivement visible sur le torse. Une réponse légèrement retardée soulève les oreilles à l’inspiration et les détend à l’expiration. Le mouvement conserve le suivi physique de la tête et les petits accents déjà présents dans les clips.

| Intention | Jeu des oreilles |
| --- | --- |
| Neutre | Les deux pointes s’éveillent légèrement puis se détendent. |
| Enjouée | Une oreille part en premier, l’autre lui répond. Le côté suit la variante A/B. |
| Enthousiaste | Les deux oreilles se dressent ensemble avec un second rebond. |
| Curieuse | L’oreille d’écoute se dresse pendant que l’autre s’abaisse. Le côté suit la variante A/B. |
| Tendre | Les deux oreilles s’abaissent lentement, puis se détendent. |
| Rassurante | Un léger retrait précède une ouverture lente et douce. |
| Sérieuse | Les oreilles s’abaissent ensemble sur l’accent et gardent une attitude sobre. |

La configuration locale de Huohuo fait réagir ses oreilles à la tête et à chaque œil. Elle confirme l’intérêt d’articuler plusieurs réactions indépendantes. Les amplitudes et la respiration sont calibrées sur le rig et la silhouette de Jade.

## Recette

Codex, 26 novembre 2026. La passe indépendante joue le vrai r21 v45.2 dans Chromium à 393 × 873, avec du Web Audio local. Au repos, les deux pointes suivent la respiration visible sur 11 secondes avec un décalage de l’ordre de 100 à 150 ms. Le contrôle géométrique rejoue les mêmes poses sans composante d’oreille pour isoler la flexion du mouvement global de tête.

Les sept intentions ont chacune donné un profil de pointes distinct. La variante B d’Enjouée inverse le premier accent et les oreilles continuent de jouer pendant une pause PCM d’environ 0,9 seconde, avec la bouche fermée. Lorsque le chargement du geste de Rassurante est retardé au-delà de sa courte réplique, ses oreilles jouent quand même et aucun geste tardif ne se déclenche. La lecture normale, la fermeture pendant le maintien et le retour au repos ont été contrôlés. Les tests ciblés de l’avatar et du lecteur passent. P0 validé sur la PWA en vue mobile. La recette matérielle Redmi fait partie du suivi plus large des intentions dans DEV-001.
