# Reprise de develop sur le poste Windows — 20 novembre 2026

Extraits des échanges visibles de la session Codex Jade. Les heures individuelles et les réponses des sessions antérieures ne sont pas disponibles ici. Les éléments de configuration privée et les sorties de diagnostic sont exclus.

## Utilisateur — extraits verbatim

> ne t'amuse pas à corriger les sous titre obs pour le moment, on fera ça plus tard

> pareil, on corrige ça plus tard. Note tous les défauts dans la backlog. Objectif 1 : réussir à tout lancer en local depuis develop

> j'aimerais surtout tester le discord et le mobile. Les autres canaux peuvent rester fermés, notamment twitch et obs

> s'il manque quelque chose, dis le moi. Par exemple la conf tailscale, et explique moi ce que je dois faire. Puis tu t'arrête jusqu'à ce que je te dise que ça soit fait

> attention à ne pas lancer plusieurs cmd en parallèle inutilement aussi, ou plusieurs tout d'ailleurs

## Assistant — synthèse de la session

Mise à jour en avance rapide de develop, installation sur D:, lancement d'une instance Discord écrit/vocal avec l'avatar r20 et préparation des prérequis mobiles. Les corrections OBS et VTube Studio sont différées. Le détail et les limites sont dans la [passation opérationnelle](../../operations/handoffs/2026-11-20-codex-validation-develop.md).


## Suite après installation des prérequis

**Utilisateur — extrait verbatim**

> je crois que j'ai fait ce que t'as demandé. Tu peux vérifier et reprendre. Si besoin de quelque chose, dis le moi

**Assistant — synthèse**

Tailscale et le SDK téléchargé ont été vérifiés sur le poste. Activation de Serve en privé, ajout du mobile à l'instance Discord, vérification de la PWA et de ses contrôles HTTP depuis le PC. Recette réelle sur Android à faire.

## Retour sur la recette mobile

**Utilisateur — extrait verbatim**

> je vois les réponses de jade sur mobile et je l'entends, mais je ne vois pas son modele dans l'appli. Corrige ça

**Assistant — synthèse**

Reproduction de deux erreurs du moteur de rendu et confirmation de l'affichage r20 dans un navigateur au format téléphone. Voir la [passation](../../operations/handoffs/2026-11-20-codex-avatar-mobile-r20.md).

## Validation Discord et mobile

**Utilisateur — extrait verbatim**

> Je valide que tous les tests de lecture/écriture et écoute/réponse orale fonctionnent sur discord et sur l'appli mobile. Tu peux les valider à done explicitement.

**Assistant — synthèse**

Quatre parcours texte et voix portent la décision **Done** dans la [recette](../../backlog/02-RECETTE.md#validation-propriétaire-du-20-novembre-2026).

## Chambre de Jade dans la PWA

**Utilisateur — extrait verbatim**

> Tu me feras valider l'image, puis les animations, et une fois développé tu me préviens, on ne pushera sur develop qu'après ma validation finale.

**Assistant — synthèse**

Une illustration originale a été générée et présentée pour validation. La demande et les étapes restent dans la [passation](../../operations/handoffs/2026-11-20-codex-chambre-mobile.md).

## Déploiement de la chambre printanière

**Utilisateur — extraits verbatim**

> L'idée est bien, mais j'aimerais quelque chose de plus joyeux quand même. Jade est pétillante !

> Ça serait bien que ça soit dans le style graphique du modèle de référence de Jade aussi.

> Ok pour l'image.

> Non mais laisse tomber. J'accepte et mets le tout de suite sur develop et sur l'appli que j'utilise actuellement. J'accepte de ne pas l'avoir checké avant.

> Ah et Jade utilise beaucoup beaucoup trop le mot Papa. Ça doit être vraiment exceptionnel normalement. Corrige son prompt de personnalité en ce sens.

> Je constate aussi qu'après plusieurs heures, Jade se fait déconnecter automatiquement du vocal discord. Pourquoi ? Est-ce qu'on peut régler ça ?

## Validation du cadrage mobile

**Utilisateur — extraits verbatim**

> Non il faut la zoomer vraiment plus encore

> Genre 50%

> Yes on est bons. Tu peux le coder tel quel et redéployer

**Assistant — synthèse**

Le cadrage soumis à validation montrait le modèle r20 à 150 % de sa taille précédente, décalé de 16 % de la hauteur de la scène vers le bas.

## Ajustements du décor après essai

**Utilisateur — extraits verbatim**

> les mouvements du décors sont un peu trop subtils. Il faudrait que ça bouge un peu plus, notamment le rideau.
> Jade devrait se décaler légèrement sur la droite pour qu'on voit la tasse en fonds.
> Les ombres et effets de lumières devraient bouger un peu plus aussi.

**Assistant — synthèse**

Ajustements du cadrage, du rideau, des ombres et des reflets dans la PWA.

## Reprise du backlog

**Utilisateur — extrait verbatim**

> Dépile la backlog et commence à réaliser les tâches prioritaires qui y sont. Ne livre pas sur develop pour l'instant

**Assistant — synthèse**

Travail réalisé sur une branche isolée. Les sujets OBS et VTube Studio précédemment différés restent en attente.
