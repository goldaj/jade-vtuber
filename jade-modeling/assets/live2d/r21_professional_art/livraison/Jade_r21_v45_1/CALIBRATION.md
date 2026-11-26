# Calibration de Jade v45.1 dans VTube Studio

Le 25 novembre 2026, le dossier installable de cette livraison a remplacé l’ancienne copie sur le poste de Jade. VTube Studio 1.35.10 a chargé le profil `Jade_r21_v45`, ses quatorze gestes et ses deux expressions. Le cadrage opérateur a été restitué puis relu par l’API. Le profil portable du dépôt conserve les valeurs de suivi mesurées sur cette installation.

## Réglages retenus

| Entrée | Sortie | Lissage VTS | Contrôle sur le modèle |
| --- | --- | ---: | --- |
| Tête X, Y, Z | Angles de tête X, Y, Z | 15, 15, 20 | Les entrées ±12°, ±8°, ±6° donnent respectivement ±12°, ±12°, ±6° après stabilisation. |
| Tête X, Y, Z | Angles du buste X, Y, Z | 20 | Aux mêmes paliers, le buste atteint ±4°, ±2,67°, ±2°. |
| Regard X, Y | `ParamEyeBallX/Y` | 8 | X garde le sens miroir du profil. Les deux directions de chaque axe répondent. |
| Paupières gauche et droite | `ParamEyeLOpen/ROpen` | 10 | Deux clignements courts et une fermeture tenue affichent les vrais sprites fermés des deux côtés. L’essai à 5 donne la même fermeture, sans gain de durée reproductible. |
| Ouverture de bouche, sourire | `ParamMouthOpenY`, `ParamMouthForm` | 0 | Le pilote de parole adoucit déjà l’ouverture. La bouche se ferme à l’interruption et retrouve sa pose de repos. |

Les valeurs exactes des vingt correspondances, les quinze groupes de physique, ainsi que les lissages des sourcils et des autres contrôles sont dans le [profil VTube Studio](Jade_r21_v45/Jade_r21_v45.vtube.json) et la [physique Cubism](Jade_r21_v45/Jade_r21_v45.physics3.json).

## Lecture en situation

Deux scènes ont utilisé la même phrase française synthétisée localement. Le pilote de parole a reçu l’enveloppe du fichier audio au rythme de sa lecture, avec une interruption, une reprise, les expressions Smile et Sad, du suivi de tête et deux gestes. Les poses observées via l’API ont été rendues avec le MOC3 et les atlas de cette livraison pour relire les épaules, le visage et les appuis en pied.

- **Accent sur un mot.** Le premier accent du balancement complice est écrit à 1,08 s dans le mouvement. Pour le mot « trouvé », la commande a été programmée environ 1,10 s avant le repère du fichier audio. Sur la seconde prise, l’inclinaison atteint 12,29° pour une crête dessinée à 12,30° au moment du mot. Ce repère porte sur l’horloge du fichier, sans mesure acoustique sur haut-parleur.
- **Premier geste après chargement.** Sur deux lectures isolées, les courbes de tête et de buste suivent la commande avec un retard médian de 110 puis 24 ms. Le début visible à 2 px se situe entre 207 et 258 ms puis entre 174 et 224 ms pour un portrait où les yeux sont espacés de 100 px. La montée du geste fait partie de son dessin. Le délai d’environ 0,73 s relevé sur une longue série antérieure reste à prendre en compte pour les appels très chargés.
- **Parole et fluidité.** Sur les deux scènes, l’ouverture suit l’enveloppe du fichier avec 66 à 78 ms de retard estimé. La bouche a été vue fermée après la coupure, ouverte à la reprise puis fermée au repos. Un passage de parole et d’expressions avec un seul observateur a donné une médiane de 59 images/s sur 44 lectures du compteur VTS, avec une plage de 50 à 59 et 42 lectures à 57 ou plus. Dans les scènes instrumentées à plusieurs connexions, certains relevés de paramètres sont espacés de près de deux secondes. Ces lacunes limitent la datation d’une pose à partir de l’API.
- **Amplitude et raccords.** Sur la seconde scène, à 57 px entre les yeux, le nez parcourt 64 px latéralement et la taille 42 px. Les pointes des deux chaussures restent fixes. Les mèches accompagnent le mouvement sans fragment détaché aux épaules. Les yeux retrouvent leur forme et la bouche en parole conserve le dessin v43. Le cadrage reste celui du début.

La recette du modèle et du pilotage local est acceptée par Codex. La sélection automatique d’une des deux variantes par le bot Windows et la PWA relève du raccordement applicatif DEV-001.
