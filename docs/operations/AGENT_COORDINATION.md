# Contrat de collaboration entre les agents Jade

## Lecture dans l'ordre

1. Lire [`AGENTS.md`](../../AGENTS.md), le code et la configuration de la **branche concernée** ; constater le SHA, `git status`, les PR et les travaux locaux non commités.
2. Lire [l'état fonctionnel courant](../handbook/BRANCH_STATE.md), [le manuel technique](../handbook/TECHNICAL.md) et les guides impactés.
3. Ouvrir [le backlog opérationnel](../backlog/README.md) et la [Definition of Done officielle](../backlog/DEFINITION_OF_DONE.md) pour toute tâche d'installation, développement engagé, recette, production r21 ou maintenance ; lire la vue et l'ID de carte avant d'intervenir. Ouvrir séparément [le catalogue d'améliorations futures](../ameliorations/README.md) uniquement si le sujet est une évolution future : une idée n'est jamais une tâche engagée par défaut. Ne pas confondre notes historiques et demandes actives.
4. Consulter [les passations de la mission](handoffs/README.md) et la PR liée, puis les références spécialisées dans [reference/](reference/).

## Où écrire pour communiquer

- **Travaux en cours / relais Codex, Terra, Astra, ChatGPT :** créer `docs/operations/handoffs/YYYY-MM-DD-<agent>-<sujet>.md` depuis le [modèle](handoffs/TEMPLATE.md). Ne pas éditer une fiche d'un autre agent sans coordination.
- **Échanges, contrôle et arbitrage sur un changement :** commentaires de la PR GitHub correspondante ; la PR pointe vers la fiche de mission. Une conversation ChatGPT seule ne fait pas foi pour la branche.
- **Modifications techniques :** ajouter une entrée à [`CHANGELOG.md`](CHANGELOG.md) en indiquant référence Git/PR, changement, impact, vérification observée et limites. **C'est la seule mise à jour documentaire obligatoire par défaut en CI.**
- **Fait fonctionnel durable :** modifier [`BRANCH_STATE.md`](../handbook/BRANCH_STATE.md) et le guide thématique si le comportement du code a évolué ; corriger également atlas et diagrammes impactés. Une simple modification des tests ne rend pas une fonction « non implémentée ».
- **Travaux opérationnels en attente :** maintenir l'ID, les dépendances et le **statut canonique** dans la vue correspondante de [`docs/backlog/`](../backlog/README.md), classées DEV/REC/OPS/ART. Un résultat de recette négatif peut ouvrir une anomalie DEV liée à REC, sans qualifier la fonction codée comme absente.
- **Idées non engagées :** inscrire dans [`docs/ameliorations/`](../ameliorations/README.md), classées par thème. Ne les promouvoir dans le backlog opérationnel qu'après arbitrage du propriétaire.
- **Anciennes décisions / recherche :** conserver dans [`docs/history/`](../history/README.md), datées et signalées comme historiques.

## Definition of Done et validation des tâches

La [DoD adoptée](../backlog/DEFINITION_OF_DONE.md) vaut pour toute tâche **DEV, REC, OPS ou ART**. Elle exige cinq conditions : **réalisation complète**, **tests/preuves pertinents**, **validation positive explicite par Codex OU le propriétaire**, **intégration dans develop ou application sur l'environnement concerné**, **traçabilité/documentation impactée**. Il ne faut **ni double approbation ni validation humaine systématique**.

**Codex** comprend ses modèles Terra/Astra/Sol et ses sous-agents, non plusieurs systèmes d'approbation obligatoires. La passe de vérification doit être **explicite et distincte** de la réalisation ; un agent Codex auteur peut également réaliser cette vérification, une contre-revue indépendante restant recommandée seulement pour les tâches risquées. **ChatGPT en mode chat n'est pas une validation Codex implicite.** Un propriétaire peut valider directement à partir des résultats suffisants. Pour un lot, citer explicitement chaque ID validé et les preuves correspondantes.

**Avant Done :** relever dans une PR ou une passation l'ID de carte, le validateur (Codex ou propriétaire), la date, le SHA ou l'environnement/asset, les scénarios réellement exécutés, les résultats, les limites et l'intégration applicable ; puis mettre à jour le **statut canonique** dans la vue. Une CI verte ne se substitue pas à une recette PC/Android/VTS. Si une anomalie conditionnelle n'est pas observée, **classer sans suite** et justifier, pas Done fictif. Les autorisations sur main, le PC privé, la facturation et les secrets restent distinctes de la DoD.

## Passation minimale

Indiquer : mission et propriétaire, ID(s) du backlog et statut, branche + SHA de base et d'arrivée, fichiers réellement modifiés, décisions prises et raisons, vérifications effectivement exécutées, limites et dépendances locales, **passe distincte de validation et conclusion**, validateur/date si la tâche est close, étapes restant à faire, PR associée. Ne jamais écrire de secrets, jetons, enregistrements vocaux, SQLite ou données personnelles.

## Commits, focus et recette légère

Regrouper autant que possible **une unité logique de travail en un commit**, avec tests et documentation impactée, plutôt qu'un commit par fichier. Les jalons réellement indépendants peuvent conserver plusieurs commits. Le contrôle CI annule les exécutions obsolètes du même ref : éviter les pushes en rafale uniquement documentaires. **Ne pas réécrire l'historique déjà partagé.**

À chaque nouvelle session, lire en premier la [reprise prioritaire du backlog](../backlog/README.md) et ne prendre effectivement en charge que quelques tâches compatibles (cible indicative : trois en cours). Pour les recettes, utiliser le [tableau de preuve rapide](../backlog/02-RECETTE.md#compte-rendu-de-recette-rapide) plutôt qu'un compte rendu dédié à chaque micro-test. La [DoD](../backlog/DEFINITION_OF_DONE.md) reste inchangée ; une preuve manquante ne devient pas un test réussi par convention.

## Règles de concurrence et revue

Créer une branche de travail depuis la tête réelle de `develop`, ne pas écraser les changements locaux Codex/Terra, ne pas faire `reset --hard`, ne pas utiliser `main` sans autorisation. Vérifier l'ascendance avant merge et supprimer les branches seulement après vérification et autorisation. Les agents adaptent uniquement la documentation **de leur propre branche**.

## Contrôle documentaire rationalisé

La CI vérifie l'existence des guides essentiels et exige **une seule entrée dans `docs/operations/CHANGELOG.md` pour un changement technique**. L'agent évalue ensuite les autres guides par impact : aucun « touch » mécanique de neuf fichiers. Les changements strictement documentaires et les tests seuls ne déclenchent pas d'entrée obligatoire. Le contrôle automatisé ne dispense jamais de corriger des liens ou guides devenus faux.
