# Modèle artistique 2D — pilotage volontaire par Jade

**État au 22 novembre 2026 : 1 idée prospective active (L2D-01, P1).** Ce thème a été rouvert pour une capacité **nouvelle et distincte** de la production artistique r21 et des animations automatiques existantes. L'inscription ne déclenche aucun développement.

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| **L2D-01** | **P1 / P** | **Pilotage explicite et volontaire de son propre modèle 2D par Jade.** Jade connaît les commandes disponibles (expressions, regard, tête, posture, gestes, mouvements et autres contrôles effectivement supportés) et peut choisir de les déclencher **de sa propre initiative**, à tout moment pertinent d'une interaction ou d'un événement, même si aucun déclencheur automatique prévu par le logiciel ne le demande. Une action décidée par Jade passe par une commande structurée adressée au moteur graphique ; le résultat réel (acceptée, exécutée, interrompue, refusée, indisponible) lui revient comme événement exploitable, pour qu'elle **sache ce qu'elle a demandé et ce qui s'est effectivement passé**. **Éviter les conflits avec le pilotage existant** : un arbitre unique rassemble animations automatiques (idle, lip-sync, émotions, intentions), commandes volontaires et overrides manuels ; il définit propriétaire/priorité/durée d'une action, annulation, retour au neutre et canaux exclusifs (p. ex. bouche, regard, tête, corps). Autoriser la combinaison des couches compatibles et une transition fluide ; ne jamais lancer deux animations antagonistes sur le même contrôle. La commande volontaire doit pouvoir temporairement préempter les mouvements automatiques compatibles, sans casser la synchronisation audio, la visibilité, les permissions ni la priorité d'un contrôle manuel ou d'un arrêt d'urgence. Exposer l'état des actions à Jade **sans nouvelle inférence IA à chaque frame**. Recetter sur PC et mobile quand la même commande existe, ainsi que sur annulation, interruptions et simultanéité parole/animation. |

## Délimitation

- **Différent de** [NEW-28](11-CAPACITES-COMPORTEMENT-CONTROLE.md), qui enrichit le *répertoire de gestes*, et des animations r20/r21 déjà déclenchées par les intentions : **L2D-01 donne à Jade l'initiative explicite et la perception du résultat de son action**.
- **Complémentaire de** [NEW-38](11-CAPACITES-COMPORTEMENT-CONTROLE.md), cadre général de connaissance des actions et de commande volontaire des capacités du logiciel. L2D-01 en constitue le cas spécialisé temps réel, avec son propre arbitre graphique.
- **Compatibilité requise** avec [VIS-01 à VIS-14](04-AVATAR-VISIBILITE.md) : l'avatar ne révèle rien d'une conversation privée sur un écran public, et ne consomme pas de rendu graphique lorsque sa visibilité ne le justifie pas.

## Historique conservé

Les anciennes entrées `ART-01` à `ART-12` recoupaient le r20 déjà développé/accepté ou les travaux r21 suivis dans [ART-001 à ART-012](../backlog/04-PRODUCTION-2D.md), [DEV-001](../backlog/01-DEVELOPPEMENT.md) et [REC-020](../backlog/02-RECETTE.md). Elles ont été retirées du catalogue actif pour éviter un deuxième suivi. Leur détail reste consultable dans les révisions Git antérieures. **L2D-01 n'est pas un ticket ART et ne réouvre pas ces travaux.**
