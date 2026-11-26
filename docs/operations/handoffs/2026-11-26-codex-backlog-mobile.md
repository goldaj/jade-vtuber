# Lot mobile du 26 novembre 2026

Le propriétaire demande une inscription au backlog avant de poursuivre le développement. La base `ede499a` sur `develop` contient le correctif du r21 qui prolonge le rendu des jambes jusqu’au bord. La mission porte sur le cadrage du lot.

| ID | Priorité | Suite |
| --- | --- | --- |
| [DEV-042](../../backlog/01-DEVELOPPEMENT.md#dev-042--zoom-et-déplacement-tactile-du-r21) | P1 | Ajouter le zoom par pincement et la saisie haptique du r21 à la PWA. Vérifier le double appui plein écran et le micro. |
| [DEV-043](../../backlog/01-DEVELOPPEMENT.md#dev-043--service-jade-indépendant-du-pc) | P2 | Faire tourner le service Jade sur un VPS autorisé. Le mobile reste utilisable sans avatar, PC éteint. Le PC garde le contrôle du modèle. |
| [DEV-044](../../backlog/01-DEVELOPPEMENT.md#dev-044--application-android-installable) | P2 | Qualifier puis livrer un client Android signé. Reprend UX-14, retirée du catalogue actif. |
| [UX-20](../../ameliorations/06-PRODUIT-MOBILE.md#ux-20--réaction-aux-secousses-p3) | P3 | Étudier la réaction physique à une secousse dans le catalogue prospectif. |

## Ordre et choix proposés

1. Réaliser les gestes sur la PWA actuelle pour tester leur confort sur le Redmi. Commencer par le pincement puis ajouter la saisie par appui long. Appliquer les transformations au modèle par-dessus son cadrage de base. Borner le zoom et le déplacement et prévoir un bouton **Recentrer**. Décider ensuite si le cadrage se mémorise par pièce au-delà de la session.
2. Prototyper la continuité PC éteint avec la PWA. Tester un moteur unique sur le VPS et une reconnexion du PC pour l’avatar. Vérifier les états de disponibilité, la reprise des sessions, la santé du service, les données et rappels, et l’absence de traitements en double. La désignation et l’accès au VPS Jade restent à qualifier avant une intervention.
3. Finaliser l’application Android sur le service stabilisé. L’installation signée privée et la reprise des fonctions de la PWA constituent l’hypothèse de première livraison. L’interface et le moteur d’affichage existants peuvent être réutilisés si la pile et la licence le permettent.
4. Reprendre le retour physique P3 à partir de ce qui fonctionne déjà sur la scène. Tester une impulsion amortie à partir des capteurs, avec seuil et désactivation. Comparer la sensation sur le téléphone au mouvement observé dans VTube Studio.

Les tests documentaires vérifient l’intégrité des cartes, de leurs priorités et de l’index. La validation matérielle du retour haptique, du rendu secoué et de la continuité PC éteint appartient aux recettes futures.

## Échanges accessibles

- **Utilisateur, extrait** « faire une vraie appli mobile (P2) ».
- **Utilisateur, extraits** « lorsque Jade n'est pas allumée sur le pc, pour une continuité des autres fonctionnalités » et « L'appli tournerait sans charger le modele du coup, le PC continuerait à être maitre du modele (P2) ».
- **Utilisateur, résumé** Réserver au nouveau modèle le zoom avec les gestes habituels, puis permettre une saisie par appui de 1 à 2 s avec confirmation haptique, déplacement sous le doigt et placement au relâchement. Priorité P1.
- **Utilisateur, résumé** Faire réagir le modèle en secouant le téléphone, avec l’effet d’un modèle secoué à la souris dans VTube Studio. Priorité P3.
- **Assistant, synthèse** La P1 peut commencer sur la PWA. La continuité du service et le maintien d’un moteur actif unique représentent le changement le plus structurant. Trois cartes DEV et une idée P3 sont inscrites.
- **Utilisateur, extrait** « je suis d'accord pour les deux points que tu rajoutes ; recentrer + bornage pour garde toujours une partie visible ». Le propriétaire autorise le développement de DEV-042 et précise ensuite « tous ces trucs c'est sur l'accueil et le plein écran. Pas sur les autres menus ».
- **Utilisateur, extrait** « le bouton pour recentrer on le mettra sur le bas gauche de l'écran accueil et plein écran ».

Chat actif du 26 novembre 2026. Heures individuelles indisponibles. Les échanges sont des extraits et des résumés, avec le rôle indiqué.
