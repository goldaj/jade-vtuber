# Journal technique unique — develop

Ce document est **la seule pièce documentaire systématiquement exigée en CI** pour les changements techniques. Les guides, atlas et passations sont révisés uniquement quand le comportement ou les procédures qu'ils décrivent changent. Une entrée indique les faits vérifiés ; un ancien journal ne remplace pas le code.

## 2026-11-16 — Réorganisation du dépôt (branche chore/develop-repository-cleanup-20261116)

- Démonstrations : garder `demo/express/` ; retirer `demo/reelle/` et `demo/windows/` et leurs tests spécifiques. **Le renderer r20 auparavant dépendant de `demo/reelle/avatar.py` est déplacé vers `src/jade_runtime/avatar_renderer.py`**, avec son appel mis à jour. Les tests du protocole avatar et du TTS de production sont conservés sous des noms `test_jade_*`.
- Documentation : séparer `docs/handbook/`, `docs/architecture/`, `docs/ameliorations/`, `docs/operations/` et `docs/history/`; reclasser les fichiers historiques sans les jeter, réparer leurs liens et définir les lieux de passation inter-agents.
- Hygiène : supprimer du suivi Git les huit fichiers `.idea/`, les ignorer à l'avenir et retirer trois anciennes branches des triggers `jade-rebuild.yml`.
- Contrat documentaire : remplacer l'obligation de rééditer neuf guides à chaque changement par l'unique entrée changelog technique, avec vérification des liens locaux des guides actifs et actualisation ciblée des documents affectés.
- Transparence : expliciter que `goldaj/jade-vtuber` est déjà public et que les contrôles de provenance, droits et secrets ne sont pas automatiquement acquis.
- Modélisation : inspection des 221 fichiers Git de `jade-modeling/` : aucun SHA de blob strictement dupliqué ; aucun art source, checkpoint ni outil de rigging supprimé sans preuve d'inutilité.
- **Validation** : état des modifications constaté dans GitHub sur cette branche ; exécution complète des tests, du rendu Windows et contrôle des objets LFS matériels à confirmer via CI/poste local.

## Format des entrées futures

`YYYY-MM-DD — <mission> (<branche>, <PR/commit>)` : changement observable, références code, documentation impactée, contrôles réellement effectués, limitations et suivi. Ne pas recopier les mêmes lignes dans tous les manuels.


## 2026-11-16 — Discord PCM, liaison mémoire et PWA (PR #23, branche fix/discord-pcm-memory-mobile-20261116)

- **Code :** supprimer le verrou erroné entre `ffplay` (micro local) et streaming PCM Discord ; continuer à autoriser le mode phrases facultatif seulement pour Discord vocal autorisé.
- **Mémoire :** conserver les tours SQLite complets lors de `complete_link` et d'un `unlink` non ambigu ; codes de confirmation liés à un ID Discord/Twitch vérifié et expirant après 5 minutes, sortie en commande explicite, redaction des codes dans les logs.
- **Mobile :** PWA Goldaj uniquement, `POST /api/link` avec la double authentification déjà existante, formulaire et copie de commande. Le SDK Live2D Web reste une dépendance du PC, aucun bundle propriétaire ajouté.
- **Tests / impacts :** régressions PCM all-channels, liaison/historique et API propriétaire, mises à jour du guide utilisateur, technique, état de branche et fiche de passation. Les résultats CI, les essais matériels, coûts et latence ne sont pas présumés. Aucun merge/déploiement effectué.
- **Limites :** fallback WAV et ancien broadcast non refondus ; comptes liés effaçables ensemble par `oublier` ; aucune interface de déliaison ; Live2D mobile réel reste à installer/recetter.
