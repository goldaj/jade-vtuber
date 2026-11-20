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
