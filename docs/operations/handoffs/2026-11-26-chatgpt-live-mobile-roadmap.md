# Mission : préparer la migration GPT-Live mobile

> **Correction propriétaire ultérieure du 26/11 :** les plafonds quotidiens/mensuels mobiles, la réserve backend et le défaut OFF décrits dans cette passation historique sont abrogés. Live mobile est désormais activé par défaut et sans plafond financier ; 50/40 EUR est exclusivement une règle mensuelle future pour Discord, toutes API confondues. Voir [la passation corrective](2026-11-26-chatgpt-live-mobile-default-no-budget.md) et les critères courants de REC-044 à REC-050.

- **Agent / rôle :** ChatGPT, coordination produit et revue du dépôt ; trois sous-agents experts : `/root/live_api_costs` (API OpenAI et coûts), `/root/live_architecture` (runtime, mémoire, outils et concurrence), `/root/live_mobile_qa` (PWA, audio Android et recette).
- **Demande propriétaire :** lire et corriger la backlog sur `develop`, challenger les implications, préparer une feuille de route exécutable. Activation initiale uniquement dans le Profil mobile ; prévoir un paramètre Discord désactivé. Aucun développement du moteur vocal demandé pour cette mission.
- **Branche / base :** branche de travail isolée `docs/live-mobile-roadmap-20261126`, issue de `develop` au SHA `990dfbe043f16619359d86405f5c128b435d0bb8`. Lot initial publié dans `bb09690d21a276eb80bc5ed187dd655abb31d7a1`. Complément sur l'accord propriétaire et Aube préparé depuis ce commit et intégré sur `develop` avec contrôle du SHA parent. Aucun changement de `main`.
- **PR / ticket :** demande directe du propriétaire ; références canoniques ci-dessous. Pas de nouvelle carte de développement pour le seul travail de cadrage.

## Cartes et résultat du cadrage

| Carte | Vue / statut conservé | Modification et résultat documentaire |
| --- | --- | --- |
| DEV-040 | DEV / À faire | Recentrée sur le choix Profil, la préférence persistante et l'intégration classique/Live ; mécanismes techniques répartis une seule fois dans les nouvelles US. |
| DEV-041 | DEV / À faire | Voix originale française, prompt de départ, protocole d'écoute et choix utilisateur ; Aube souhaitée pour le prototype si accessible par API, Brise comme recours technique explicite, aucune voix créée. |
| DEV-046 | DEV / À faire | Nouvelle US : adaptateur Live, contrats, configuration par canal, signalisation, contrôle serveur et tests sur doubles. |
| DEV-047 | DEV / À faire | Nouvelle US : capture/lecture, parole naturelle, pré-roll, permissions, interruption et preuve Redmi. |
| DEV-048 | DEV / À faire | Nouvelle US : baux, générations fournisseur, arrêt confirmé, kill, inactivité et réconciliation. |
| DEV-049 | DEV / À faire | Nouvelle US : personnalité, contexte, mémoire, journal, délégations, outils et idempotence. |
| DEV-050 | DEV / À faire | Nouvelle US : projection chat, lecture observée, interruptions et avatar privé. |
| DEV-051 | DEV / À faire | Nouvelle US : budgets durables, réservations, coût total et mesure A/B de fluidité. |

**Critères d'acceptation :** les critères détaillés sont écrits et vérifiés pour cohérence dans chaque US. Ils restent **à réaliser et à prouver**. Cette mission ne valide aucune fonctionnalité Live, acoustique ou facturation réelle. Aucune de ces cartes n'est passée En cours, À valider ou Done.

**Existant préservé :** DEV-039 est déjà livrée et suivie seulement par REC-042 ; aucun nouveau PTT à développer. DEV-030 conserve les deadlines classiques. DEV-037 conserve les sous-titres synchronisés, avec événements préparés par DEV-049/050. DEV-038 reste le registre général des capacités. DEV-043/044 ne sont pas des prérequis. Les autres statuts, cartes et travaux parallèles sont conservés.

## Décisions et raisons

1. **Cibler `gpt-live-1.1`, API Live.** Les docs officielles du 26/11 distinguent cette API du TTS Realtime déjà utilisé. WebRTC mobile → fournisseur, signalisation authentifiée et sideband de contrôle côté Jade ; délégation `client`, contexte textuel borné et `store=false`.
2. **Séparer préférence, capture et session facturable.** ON dans Profil ne crée rien ; un geste micro acquiert d'abord un bail client exclusif. Une fermeture d'inactivité ne détruit pas l'autorisation locale encore visible ; un arrêt fort révoque les deux niveaux. OFF depuis un autre client du propriétaire arrête aussi le Live actif.
3. **Préserver une Jade commune.** Même identité mobile, persona, mémoire, provenance, outils et historique ; mise à jour/invalidation du cache `Dialogue.history`. Les délégations passent par l'arbitre existant. La parole native peut coexister avec un autre canal : aucune sérialité absolue de toute parole n'est prétendue, aucun verrou métier pendant toute la session.
4. **Exiger une fermeture fournisseur observée.** Watchdog serveur indépendant et surveillance réciproque sur le téléphone ; aucun callback Android supposé garanti. Distinguer arrêt local, clôture demandée et terminal `session.closed`. Fermeture incertaine ou création ambiguë bloquent un nouveau Live. Les verrous d'ouverture n'empêchent jamais le nettoyage interne.
5. **Traiter coût et audio froid avant exposition.** Budget privé explicite, ledger durable, réservations sans double comptage ; aucun seuil positif décidé dans ce document. Tester la première syllabe et la vidange du tampon WebRTC sur Redmi, avec timeout et capacité bornés. Aucun appel IA permanent pour surveiller le silence.
6. **Préparer Discord honnêtement.** Paramètre `JADE_DISCORD_LIVE_ENABLED=false` et interface par canal ; si l'adaptateur manque, une activation explicite échoue au préflight, sans modifier Discord classique.

Le [plan détaillé](../../backlog/PLAN-LIVE-MOBILE.md) contient les fichiers à toucher, routes, états, valeurs initiales modifiables, événements fournisseur, sources officielles et matrice de recette. Les valeurs de 2/5 s de bail, 8/30 s d'inactivité, 15 s de fin après mute et 600 s de connexion sont des propositions d'ingénierie à mesurer, pas des résultats ni garanties fournisseur.

## Changements du lot initial (`bb09690`)

- `docs/backlog/PLAN-LIVE-MOBILE.md` : nouveau plan d'architecture et feuille de route.
- `docs/backlog/01-DEVELOPPEMENT.md` : deux US révisées, six créées, liens de responsabilité et critères détaillés.
- `docs/backlog/README.md` : ordre P1, liens et compteurs recalculés à partir des vues canoniques (108 cartes : DEV 36, REC 43, OPS 16, ART 13).
- `docs/ameliorations/README.md`, `01-LATENCE-VOIX.md`, `05-ARCHITECTURE-IA.md` : correspondances historiques LAT-17/ARC-01/ARC-05 et périmètres résiduels, sans créer de suivi actif en double.
- Cette passation et `docs/operations/handoffs/README.md` : relais de mission.

Aucun fichier de runtime, configuration livrée, dépendance ou secret modifié. Aucun changement technique ne justifie une entrée `CHANGELOG.md` pour ce lot documentaire seul.

## Accord propriétaire et préférence Aube, 26 novembre 2026

Après présentation, Goldaj confirme que le reste du cadrage lui convient et que les US pourront évoluer au fil du développement. Il demande Aube comme voix de prototype jusqu'à la création de la voix originale. Cet accord valide la direction produit et la publication ; aucune fonctionnalité non codée n'est déclarée acceptée ou Done.

Vérification officielle complémentaire : [ChatGPT Voice](https://help.openai.com/fr-fr/articles/20001274-chatgpt-voice) cite Aube ; [le catalogue API Live](https://developers.openai.com/api/docs/guides/live-conversations) et [la référence de création](https://developers.openai.com/api/reference/resources/live/methods/create) citent `brise`, sans `aube` ni correspondance officielle trouvée. Aube est donc prioritaire **si son accès API est confirmé** ; aucune promesse de disponibilité, aucun alias ni équivalence inventés. Brise reste le recours technique explicite pour les essais si Aube n'est pas exposée.

Complément limité à trois fichiers : vue DEV (DEV-041 et contrôle dans DEV-046), plan Live (préférence, paramètre, source) et cette passation. La vérification indépendante du sous-agent API/coûts confirme cette distinction et l'absence de correspondance officielle trouvée ; l'absence dans la liste publique ne constitue pas une preuve d'indisponibilité absolue pour tous les comptes. Aucun appel vocal ni coût engagé ; statut des huit US inchangé.

## Vérifications et passe distincte de validation

- `python scripts/check_docs.py` : **réussi** ; fichiers canoniques, liens locaux, cohérence des cartes, dépendances, index et contrat documentaire.
- `python -m unittest tests.test_docs_backlog_contract -v` : **2 tests réussis**, dont le rejet d'une dépendance absente.
- `git diff --check` : **réussi** ; aucun défaut d'espacement.
- **Contre-revue distincte après rédaction :** les trois experts ont relu le plan et les US par rapport à leurs analyses et au code. Les corrections intégrées concernent notamment le cache d'historique, les limites de contexte et permissions du data channel, le suivi d'effet métier après crash, la séparation bail client/session fournisseur, le OFF partagé, la borne non prolongeable après mute et le calcul consommation/réservation.
- La dernière contre-revue mobile a confirmé explicitement la cohérence des contrats corrigés et des scénarios associés. Avis positif sur la préparation du code ; aucune preuve Android ou fournisseur présumée.
- **Validé par, uniquement pour Done :** sans objet. La préparation documentaire est revue, les huit US restent À faire et suivent la DoD après implémentation.

## Limites et reprise

Pas de session OpenAI Live ouverte, voix créée, micro activé, dépense engagée ni essai matériel pendant ce cadrage. La disponibilité du compte, les schémas/SDK courants, les budgets privés du pilote, la qualité acoustique et le choix final de voix restent des contrôles d'exécution assignés. La recette micro PC/Twitch/OBS suspendue n'est pas réactivée.

**Prochaine action : DEV-046.** Persona backend/intégration : établir les interfaces fournisseur, session et ledger avec des doubles ; poursuivre DEV-048/051 (supervision et coûts), puis DEV-049/047 (continuité Jade et audio), DEV-050/040 (restitution et Profil). Persona voix/UX : préparer DEV-041 en parallèle, écouter lorsque le chemin audio est sûr. Persona QA mobile : produire ensuite les preuves Redmi et fournisseur du plan, avec REC-042 pour le classique. Les dépendances livrent des mécanismes testés utilisables sans Done prématuré ; les recettes finales restent ouvertes jusqu'à preuve.

Documentation canonique : [vue DEV](../../backlog/01-DEVELOPPEMENT.md), [plan Live](../../backlog/PLAN-LIVE-MOBILE.md), [index](../../backlog/README.md), [DoD](../../backlog/DEFINITION_OF_DONE.md). Après code, transfert unique DEV → REC si l'acceptation reste à faire ; aucune recette concurrente précréée par ce cadrage.
