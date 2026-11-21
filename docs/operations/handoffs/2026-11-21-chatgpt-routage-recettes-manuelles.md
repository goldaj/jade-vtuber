# Décision produit — routage des recettes automatiques et manuelles

- **Date :** 21 novembre 2026.
- **Auteur documentaire :** ChatGPT.
- **Décision :** propriétaire de Jade, dans la conversation : « quand une recette n'est pas possible automatiquement, on mets directement en À valider ».
- **Branche de destination :** `develop`, SHA de base `52d3ab8eef8bfec95c055dfd2c33606a610c8212`.
- **Périmètre :** processus et statuts de la backlog, sans modification de code, test matériel, API ou déploiement.
- **Statut des cartes :** restent ouvertes. Il ne s'agit **pas** d'une validation de résultat, seulement d'un routage vers la recette manuelle.

## Règle opérationnelle

1. Une recette automatisable dans un environnement autorisé demeure `À faire` / `En cours` jusqu'à exécution et consignation des preuves par un agent.
2. Quand le scénario complet exige une vérification humaine (audio, visuel, services et comptes réels non pilotables automatiquement), la carte REC passe **directement à `À valider`**, même si la recette manuelle n'a pas encore été exécutée.
3. Le validateur effectue les vérifications explicites de la carte, consigne résultat/version/contexte, puis peut la clôturer en suivant les cinq exigences de la Definition of Done. Aucun test fictif.
4. Un vrai blocage de prérequis ou un défaut confirmé ne doit pas être maquillé en recette validée. Conserver les liens DEV et les critères en attente ; documenter ce qui est réellement bloquant. Effectuer les contrôles automatisables complémentaires lorsqu'ils sont disponibles.

## Cartes reclassées

| ID | Prio | Statut initial | Nouveau statut | Pourquoi un contrôle manuel est requis |
| --- | --- | --- | --- | --- |
| REC-002 | P0 | À faire | **À valider** | Échanges réels Discord en serveur et MP, identité de plusieurs auteurs, confidentialité et retour de l'utilisateur ; dépend du correctif DEV-019. |
| REC-004 | P0 | À faire | **À valider** | Micro/enceintes physiques et écoute humaine du résultat STT/TTS et anti-écho sur le PC. |
| REC-006 | P0 | À faire | **À valider** | Écoute réelle du premier son PCM Discord, transitions streaming et comportement en salon vocal. |
| REC-008 | P0 | À faire | **À valider** | Interactions vocales réelles, interruptions pendant la diffusion et départ du salon. |
| REC-012 | P1 | À faire | **À valider** | Parcours du compte Twitch réel : autorisations, messages en direct et comportement réseau, sans automatisation disponible avec les comptes de test autorisés. |
| REC-020 | P1 | À faire | **À valider** | Observation humaine des sept intentions, des 14 variantes A/B et des expressions du modèle en condition réelle. |
| REC-022 | P1 | À faire | **À valider** | Parcours d'identités réelles Discord/Twitch et association intercanale avec preuve utilisateur, dont tests de refus et confidentialité. |
| REC-023 | P1 | À faire | **À valider** | Reconnexion réelle Discord/Twitch, pertes réseau et arrêt/redémarrage sur l'instance physique ; les injections de panne automatisables restent utiles. |
| REC-024 | P2 | À faire | **À valider** | Essai graphique de l'installation, du raccourci, du démarrage et de la désinstallation sur Windows réel. |

**Maintenues `À faire` car des recettes automatiques restent pertinentes :** REC-001 (démarrage sur PC accessible à l'agent), REC-021 (SQLite et consentement en base de test) et REC-025 (restauration/effacement sur copie sécurisée). Ces scénarios ne sont pas déclarés exécutés.

**Déjà `À valider` :** REC-005 et REC-010, inchangées.

## Contrôles et limites

- **Vérification distincte de la réalisation :** comparaison des statuts canoniques et des critères d'acceptation des cartes ; vérification que la modification n'affecte ni les cartes Done, ni les priorités, ni les dépendances.
- **Validation de la décision produit :** propriétaire le 21/11/2026 ; **aucune validation de recette** ni mesure matérielle nouvellement acquise.
- **Livraison :** mise à jour des règles AGENTS / DoD / coordination / backlog / vue REC et de cette passation sur `develop`.
- **Prochaines actions :** agent exécute les recettes automatisables ; propriétaire ou environnement de recette autorisé réalise les scénarios manuels et confirme ou refuse les cartes `À valider`.

