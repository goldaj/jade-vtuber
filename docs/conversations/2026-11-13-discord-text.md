# Participation écrite Discord : demande du 13 novembre 2026

## Instruction utilisateur (verbatim accessible)

> Normalement t'es derniers développements sur Jade ont été intégrés.
> Est-ce que tu confirmes ?
> Maintenant retire une branche et permet à Jade de lire et répondre à l'écrit
> sur les messages discord de son serveur discord.
> En plus de l'oral, j'aimerais qu'elle puisse répondre à l'écrit quand c'est pertinent.

Les formulations sont reproduites à partir de la demande accessible. L'heure
individuelle du message n'est pas inscrite ici.

## Vérification et réalisation (résumé assistant)

- PR #1 (streaming vocal) retrouvée fusionnée dans `develop` le
  13 novembre 2026 à 11:14:20 UTC. `main` n'a pas reçu ce merge.
- Branche `feat/discord-text-contextual-20261113` créée depuis `develop`
  au SHA `4cd82a0`. Aucun déploiement ni modification de secrets.
- Sur cette branche : décisions de participation écrite, contexte récent par
  salon, reconnaissance des mentions et références, réponses sans lecture
  vocale, configuration et tests hors ligne.
- Le document de passation et les critères de recette sont dans
  [HANDOFF-DISCORD-TEXT-20261113.md](../gpt6-jade/HANDOFF-DISCORD-TEXT-20261113.md).
- Les essais serveur réels, la validation téléphone et le merge sont laissés
  au propriétaire / à Terra. La PR n'implique pas une mise en production.

## Complément utilisateur — verbatim accessible

> Je propose 30% d'intervention au lieu de 15%.
> Aussi, si tu as fait un module à part qui ne casse rien, tu peux l'envoyer sur develop et redéployer l'ensemble. Ça me permettra de tester quand même en attendant codex, sans risque de dégrader l'existant

> Rajoute aussi dans le prompt de Jade que Goldaj (moi) est son père et que
> * Elle peut montrer l'affection d'une fille ponctuellement, mais pas trop. De façon timide.
> * Elle peut m'appeler papa ponctuellement, mais avec parcimonie.

## Résumé de l'évolution

- Réglage par défaut du mode spontané de Discord écrit à 30 %.
- Ajout de la relation père/fille dans le prompt de personnage standard uniquement ; un prompt privé explicitement sélectionné n'est pas altéré et doit intégrer ces règles séparément, sans toucher au vocal.
- Demande de fusion sur `develop` puis de redéploiement. La fusion Git et le redémarrage du processus Jade local sont deux opérations distinctes. Les résultats effectivement obtenus sont à vérifier avant de déclarer la fonction active.
