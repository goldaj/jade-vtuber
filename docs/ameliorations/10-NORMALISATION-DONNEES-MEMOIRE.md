# Normalisation des données, événements et souvenirs

**Idée du propriétaire — 18 novembre 2026.** Objectif : rendre les **entrées, sorties, échanges entre modules et données mémorisées** de Jade cohérents, typés, facilement traitables et retrouvables, y compris lorsque le contenu entrant est brut/non structuré (parole, texte libre, images, vidéos). Priorité **P2 (chantier structurant)**, à affiner par mesure. **Proposition uniquement : ne pas modifier le runtime ni la base SQLite sans mission distincte.**

## Intention produit

Jade doit recevoir des contenus hétérogènes, les transformer **une seule fois au bon endroit** en représentations canoniques utiles, puis les transmettre entre modules sans reconvertir, reparcourir ou réinterpréter inutilement les mêmes informations. Les connaissances durables doivent être **structurées, indexables, sourcées, mises à jour et récupérées rapidement** pour que le moteur IA ne lise pas un historique entier à chaque question.

**Attention :** « normaliser » ne signifie ni tout traduire en JSON, ni découper chaque phrase en dizaines de colonnes SQL, ni remplacer le langage naturel par des champs rigides. Le brut et sa provenance restent disponibles si autorisés ; l'extraction structurée est une **vue dérivée**, susceptible d'erreurs et de corrections. Un schéma uniforme peut réduire les conversions et les ambiguïtés, mais ne garantit pas un gain de latence : benchmark obligatoire.

## A. Interactions et événements canoniques

| ID | Priorité / nature | Amélioration proposée / résultat attendu |
| --- | --- | --- |
| NRM-01 | P2 / P | **Enveloppe d'événement interne unique et versionnée** : identifiant, type, version du schéma, source/transport, identités vérifiées, conversation/session, canal, audience et permissions, horodatage + ordre, corrélation/causalité, payload typé et références de contenus. À définir précisément avec ARC-03/ARC-04 ; ne pas perdre les spécificités de transport. |
| NRM-02 | P2 / P | **Adaptateurs d'entrée/sortie responsables de la conversion** : les formats externes Discord/Twitch/PC/PWA, API IA et média deviennent des événements internes cohérents à la frontière ; les sorties sont retransformées uniquement au dernier adaptateur. Aucun module central ne réinterprète des payloads propres à un fournisseur. |
| NRM-03 | P2 / P | **Payloads multimodaux typés** : texte libre, fragments STT avec indicateur provisoire/final, segments audio, images, frames vidéo horodatées, résultats de vision, intentions, commandes, accusés de réception. Les médias lourds restent référencés par identifiants contrôlés plutôt que copiés dans chaque événement. |
| NRM-04 | P2 / P | **Normalisation sémantique mesurée** : conventions sur langue, dates UTC/affichage local, unités, rôles, intentions, ID, scopes et statuts ; nettoyage/déduplication là où sûr, préservation des nuances, formulations originales et niveaux d'incertitude. Ne pas traiter une hypothèse STT comme un fait. |
| NRM-05 | P2 / P | **Validation et compatibilité** : contrats testables/versionnés (schémas et invariants), compatibilité fournisseur, migrations d'événements, gestion des champs inconnus, erreurs explicites, sérialisation efficace et absence de passage répété par LLM pour reformater. |
| NRM-06 | P2 / C | **Optimisation des parcours** : mesurer nombre de conversions, copies de buffers, tokens envoyés, étapes d'inférence, latence p50/p95, allocations et coûts ; comparer avant/après, éviter les transformations inutiles, préférer le streaming et le traitement incrémental lorsque pertinent. |

## B. Mémoire SQLite : structuration et recherche

L'**existant à préserver** sur `develop` comporte déjà un schéma SQLite v3 avec `persons`, `identities`, `memories` (dont ordinaires/Core), `jade_self_core`, `conversation_turns`, des contraintes de clés et des index par identité, portée et chronologie (voir `src/jade_runtime/memory_store.py`). La récupération actuelle reste principalement **chronologique et bornée**. Il ne faut ni présenter la base comme entièrement dénormalisée, ni détruire ces acquis.

| ID | Priorité / nature | Amélioration proposée / résultat attendu |
| --- | --- | --- |
| NRM-07 | P2 / E | **Audit de la structure SQLite réelle et des requêtes** : vérifier normalisation relationnelle appropriée (identités, entités, relations, souvenirs, provenance), duplication, contraintes, cardinalités, index composites, taille et requêtes coûteuses avec `EXPLAIN QUERY PLAN`. Ne changer que ce qui apporte un bénéfice démontré. |
| NRM-08 | P2 / P | **Souvenirs structurés et typés si utile** : représentation de faits/événements/préférences/relations avec sujet, prédicat ou catégorie, valeur, temporalité, auteur/source, confiance, statut (actif, remplacé, contesté), version et niveau de visibilité. Garder un résumé naturel et une référence vers les messages originaux ; éviter des catégories artificielles qui déforment les souvenirs. |
| NRM-09 | P2 / E | **Recherche rapide et hybride** : index B-tree pour clés, scopes et dates ; évaluer SQLite FTS5 pour texte, filtres de métadonnées et éventuellement recherche sémantique par embeddings, selon bénéfice et charge réelle. Indexer uniquement ce qui est interrogé ; choisir la stratégie par requête et budget. |
| NRM-10 | P2 / E | **Rappel de mémoire ciblé** : d'abord sélectionner les candidats par identité vérifiée, audience, portée et permissions ; puis combiner pertinence, actualité, importance, contradiction et provenance ; retourner un petit lot de souvenirs avec citations internes plutôt qu'un dump de la base dans le prompt. Prévoir la mémoire anticipée L1/L2/L3 (MEM-01 à MEM-04). |
| NRM-11 | P2 / P | **Déduplication et gestion des versions de faits** : fingerprint exact + rapprochement sémantique contrôlé, liens entre souvenirs confirmés/contredits/corrigés, fusion prudente, archivage/expiration explicites ; jamais de suppression silencieuse d'une nuance ou d'une relation. |
| NRM-12 | P1 / C | **Garanties de vie privée et d'effacement** : consentement opt-in, isolation personne/session/serveur, scopes par enregistrement et recherche, accès filtré avant classement, propagation des corrections/effacements aux index FTS/vectoriels, caches, résumés et exports prévus. Interdire la reconstitution indirecte de données supprimées. |
| NRM-13 | P2 / C | **Migration SQLite incrémentale** : plan de version, sauvegarde et restauration testée, transactions atomiques, migration des données existantes sans perte, compatibilité des anciens tours, tests de liaison/déliaison d'identité et rollback. Aucune réécriture en masse sans résultats de benchmark. |

## C. Contrat d'architecture envisagé

```text
Source externe (Discord / Twitch / PC / PWA / image / vidéo / API)
    -> Adaptateur de source (parsing + vérification identité / permissions)
    -> Événement canonique versionné + payload typé + référence au brut
    -> Pipeline de traitement / enrichissement facultatif
       -> Mémoire : faits structurés, provenance, index et permissions
       -> Dialogue : contexte ciblé (sans tout recharger)
    -> Événement de résultat normalisé
    -> Routeur d'audience / de modalité
    -> Adaptateur de sortie spécifique (texte / voix / avatar / média)
```

- **Une seule conversion nécessaire à la frontière**, pas d'analyses structurelles redondantes dans chaque module ; préserver les métadonnées de consentement et de provenance d'un bout à l'autre.
- **Distinction contenu brut / représentation canonique / interprétation IA / souvenir confirmé** : ne jamais prendre un résultat probabiliste pour une donnée sûre.
- **Modularité maintenue** : un fournisseur STT/TTS/LLM/vision/SQLite peut être échangé par adaptateur sans obliger tout le runtime à adopter son format natif. Voir [05-ARCHITECTURE-IA.md](05-ARCHITECTURE-IA.md).
- **Pas de sur-normalisation** : les données relationnelles peuvent être normalisées, mais des vues dénormalisées, caches et index spécialisés peuvent accélérer la lecture ; la performance réelle, pas la pureté du schéma, guide la décision.
- **Pas d'appel IA systématique pour convertir des données simples** : validation déterministe locale d'abord ; extraction IA asynchrone, limitée et utile quand l'information est ambiguë/non structurée.

## Critères d'acceptation à utiliser lors de la future implémentation

1. Ajouter une source, un fournisseur ou une sortie **sans nouvelle logique de parsing dans le cœur** ; événements validés par contrat, versions testées.
2. Pour une même personne consentante, retrouver un fait précis parmi un historique étendu et contextualiser une réponse **sans parcourir tout le texte** ; évaluer rappel, précision, conflits et faux souvenirs.
3. Requêtes et index mesurés sur volumes progressifs de données **synthétiques** puis données réelles autorisées : p50/p95, coût, taille disque/RAM, taux de cache, coûts d'écriture et d'invalidation.
4. Modification ou suppression d'un souvenir répercutée dans toutes les représentations dérivées ; aucune fuite entre identités, salons, transports ou audiences.
5. Fonctionnement multimodal avec événements arrivant en désordre, STT provisoire puis corrigé, annulation, coupure d'une source et reconnexion.
6. Aucun gain annoncé sans comparaison reproductible avec le `develop` précédent ; aucun changement non réversible de la base personnelle.

## Dépendances et phasage envisagés

1. Inventorier les vrais formats d'entrée/sortie, le schéma SQLite et les requêtes chaudes ; **mesurer**.
2. Définir les contrats canoniques minimaux et adapter progressivement les connecteurs, sans changer leurs comportements.
3. Améliorer recherche SQLite et récupération ciblée **avant** une refonte profonde de la structure.
4. Tester des faits structurés, la provenance et la gestion de conflits sur corpus de référence ; migrer ensuite seulement si bénéfique.
5. Étendre au multimodal (PER-01 à PER-10), aux moteurs substituables (ARC-13 à ARC-17) et aux caches mémoire (MEM-01 à MEM-04).

**Liens :** [mémoire et présence](02-MEMOIRE-PRESENCE.md), [architecture modulaire](05-ARCHITECTURE-IA.md), [perception multimodale](09-PERCEPTION-MULTIMODALE.md), [routage de sorties](03-CANAUX-ROUTAGE.md), [documentation technique](../handbook/TECHNICAL.md).

**Statut :** idée consignée uniquement, ni implémentation ni migration. Pas de modification du code, des secrets ni des données SQLite du poste.
