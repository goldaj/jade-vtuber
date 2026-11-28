# Index des conversations Jade

Cet index est créé le 2 novembre 2026, avant les modifications documentaires de l’audit de migration. La couverture est **partielle** : aucune exhaustivité historique n’est revendiquée.

| Source | Couverture et fidélité | Limites |
| --- | --- | --- |
| [CHATGPT_PROJECT_HISTORY.md](../handoffs/CHATGPT_PROJECT_HISTORY.md) | Journal antérieur conservé ; citations et résumés étiquetés par leurs auteurs | Plusieurs exports et heures individuelles manquent |
| [CONVERSATIONS.md](../gpt6-jade/CONVERSATIONS.md) | Extraits utilisateur accessibles du chantier du 24 octobre ; réponses résumées | Ce fichier n’est pas une transcription complète |
| [Session du 2 novembre](2026-11-02-migration.md) | Demande de migration et réponses accessibles dans le présent chat ; rôles distincts | Date du chat connue, heures individuelles des messages non fournies |
| [Revue Astra du 2 novembre](2026-11-02-astra.md) | Demande utilisateur, avancement et résultat de la contre-lecture | Heures individuelles non fournies ; synthèse du résultat étiquetée |
| [Exécution Terra](2026-11-02-execution.md) | Demande et suivi de l’intégration actuelle | Heures individuelles non fournies ; exécution en cours |
| [Préparation publique](2026-11-02-publication.md) | Demande de nettoyage, suppression du clone et état de publication | Heures individuelles indisponibles ; ne présente pas les données privées |
| [Nouveau dépôt officiel](2026-11-02-nouveau-depot.md) | Demande de création d’un dépôt public sans historique et d’une sauvegarde privée | Échanges accessibles uniquement ; heures individuelles absentes |
| [Contrôle final Astra](2026-11-02-astra-final.md) | Demande de contrôle, instruction de suivi et synthèse de la vérification du dépôt public | Revue documentaire et technique ; pas de nouvelle recette réelle des connecteurs |
| [Reprise Terra du 3 novembre](2026-11-03-reprise-terra.md) | Demande de reprise, connexions Twitch/Discord et sécurité CI | Heures individuelles non fournies ; résultats consignés après vérification |
| [Reprise de la démo du 9 novembre](2026-11-09-reprise-demo.md) | Reprise de la démo animée et demande d'explication préalable | Échanges accessibles uniquement ; heures individuelles non fournies |
| [Plan MVP du 10 novembre](2026-11-10-plan-mvp.md) | Acceptation de la démo et demande de plan par métiers | Échanges accessibles uniquement ; heures individuelles non fournies |
| [Revue Astra MVP et relais du 10 au 13 novembre](2026-11-10-astra-mvp.md) | Revue, correctif DAVE, réponse réelle confirmée, portrait, plan latence et demande Aube/×1,5 pour Terra | Verbatim utilisateur et résumé assistant ; heures individuelles non fournies, enveloppes automatiques distinguées |
| [Chantier streaming parallèle du 13 novembre](2026-11-13-streaming-parallele.md) | Instruction et autorisation de l'utilisateur, lot vocal développé sur branche isolée et passation à Terra | Verbatim utilisateur accessible et résumé technique ; pas d'heure individuelle, de validation audio humaine ni d'accès aux modifications locales de Terra |
| [Reprise Terra latence et Discord](2026-11-13-reprise-terra-latence.md) | Développement, intégration du chantier parallèle et lancement local | Échanges accessibles uniquement ; heures individuelles non fournies |
| [Participation écrite Discord du 13 novembre](2026-11-13-discord-text.md) | Demande utilisateur, vérification du merge vocal et branche Discord textuelle | Verbatim utilisateur et résumé assistant ; recette réelle et merge encore à faire |
| [Launcher Windows personnel du 15 novembre](2026-11-15-jade-windows-launcher.md) | Demande initiale puis correction explicite : tous les supports simultanés, arbitrage des messages par Jade, sans modes ; modifications du launcher et du moteur | Résumé des décisions et du code, essai PC réel à faire |
| [Application privée mobile Jade du 15 novembre](2026-11-15-jade-mobile-pwa.md) | Développement PWA puis demande de passation opérationnelle : Codex devra installer/configurer sur le PC Windows et Android avec le [guide courant](../gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md) | Code fusionné dans develop ; tests de l'appareil et de Tailscale encore à faire |
| [Implémentation SQLite et idée de conversation unifiée du 15 novembre](2026-11-15-memory-implementation.md) | Demande de développement en PR séparée, transfert de PC, identification locale Goldaj et contexte Discord écrit/vocal à documenter pour Codex | Résumé de demandes visibles, statut d'essai distant uniquement |
| [Cadrage mémoire persistante / Core Memories du 15 novembre](2026-11-15-persistant-memory-core.md) | Demande de reconnaissance durable des personnes, contexte et choix autonome par Jade de souvenirs fondateurs sans purge automatique | Verbatim des demandes et synthèse documentaire ; pas d'implémentation |
| [Journalisation du 15 novembre](2026-11-15-conversation-logs.md) | Demande de provenance, contenu, intention et modalités de réponse dans les logs | Verbatim utilisateur et résumé assistant ; aucune conversation privée journalisée dans Git |
| [Plan professionnel du modèle du 13 novembre](2026-11-13-modele-plan-pro.md) | Nouvelle direction, recherche et feuille de route modèle et utilisation | Résumé des échanges accessibles ; vidéo non transcrite intégralement |
| [Reprise develop sur Windows du 20 novembre](2026-11-20-reprise-develop.md) | Extraits de la demande de lancement et des priorités Discord, mobile et backlog | Extraits visibles, heures individuelles indisponibles ; synthèse assistant étiquetée |
| [Évolution de la voix de Jade](2026-11-27-evolution-voix-jade.md) | Auditions, choix de Friponne, débit, comparaison mobile et Discord Live, retrait de la lecture accélérée et adoption de Friponne rapide | Extraits du chat courant, heures individuelles non fournies. Les enregistrements vocaux et identifiants de service sont exclus. |
| Documents supplémentaires de `develop` | Audits du 30 octobre et pistes migrées du 1er novembre : à conserver lors de l’intégration | Ces documents sont encore sur la branche cible ; leur provenance est décrite dans le dossier de migration |

## Relais technique en cours — voix et intentions

La [passation de nettoyage du dépôt](../../operations/handoffs/2026-11-27-codex-nettoyage-depot.md#échanges-accessibles) consigne la demande de conserver un point de retour sur `main`, de nettoyer les branches puis d’examiner tous les fichiers suivis.

Pour le chantier du **13 novembre 2026**, le [relais opérationnel Codex](../gpt6-jade/HANDOFF-CODEX-VOICE-INTENTS-20261113.md) récapitule les décisions d'Étincelle, les fichiers modifiés, le contrat de métadonnées d'intention, les tests, leurs limites et les étapes de recette réelle. Lire également la [spécification des voix](../../operations/reference/VOICE-PROFILES-20261113.md) et l'[audit PO/architecture/QA](../gpt6-jade/REVIEW-INTENT-ETINCELLE-20261113.md).

Il s'agit de documents de passation **synthétiques**, pas d'une transcription verbatim des échanges ; les notes précédentes restent historiques. `develop` est la branche concernée ; `main` n'a pas reçu ce lot.

Le chat antérieur « Analyser le projet AI VTuber » a été retrouvé. Seule une page récente a été consultée : elle concerne la modélisation 2D, hors périmètre de cette intervention. Son historique complet n’a pas été récupéré ni recopié. Les échanges ChatGPT ayant produit la refonte ne sont disponibles ici qu’à travers les documents du dépôt et les descriptions de PR ; aucune transcription supplémentaire n’est inventée.

Les journaux conservent les décisions successives, même contradictoires. La synthèse des instructions actuelles est dans [le dossier de migration](../migrations/2026-11-02/README.md) et ne réécrit pas les sources historiques. Les contenus privés, secrets, identifiants de compte, raisonnements internes, instructions système/développeur et sorties brutes d’outils sont exclus.

Après toute nouvelle intervention, ajouter les échanges effectivement accessibles, avec leur rôle et leur fidélité. Utiliser les heures réelles seulement lorsqu’elles sont attestées ; ne pas dater rétroactivement un propos à partir de l’heure d’une commande.

## Jade r21 par défaut dans la PWA le 26 novembre 2026

Le [diagnostic de chargement du 28 novembre](../../operations/handoffs/2026-11-28-codex-chargement-r21-mobile.md#échanges-accessibles) reprend le signalement du r21 indisponible sur le téléphone.

Les décisions du propriétaire et les réponses de cadrage accessibles figurent dans la [passation du raccordement mobile](../../operations/handoffs/2026-11-26-codex-mobile-r21.md#échanges-accessibles). Heures individuelles indisponibles. La passation ne reprend ni les données privées ni les sorties d’outils.

Les demandes suivantes de zoom et déplacement tactile, service indépendant sur VPS, application Android dédiée et réaction aux secousses figurent dans la [passation du lot mobile](../../operations/handoffs/2026-11-26-codex-backlog-mobile.md#échanges-accessibles), avec rôles distincts, extraits et synthèses.

L’autorisation de développer le push-to-talk en maintien et les secousses est consignée dans la [passation mobile du 26 novembre](../../operations/handoffs/2026-11-26-codex-mobile-ptt-shake.md#échanges-accessibles).

## Voix et interface du Live mobile le 27 novembre 2026

Le signalement et les décisions de réalisation sont consignés avec leurs rôles dans la [passation Live mobile](../../operations/handoffs/2026-11-27-codex-mobile-live-playback.md#échanges-accessibles).

La [suite du 27 novembre](../../operations/handoffs/2026-11-27-codex-mobile-live-playback.md#mise-à-jour-du-micro-et-de-la-pastille) consigne la confirmation du correctif puis la nouvelle demande de commande et d’indicateurs.

La [passation Discord Live](../../operations/handoffs/2026-11-27-codex-discord-live-control.md#échanges-accessibles) consigne le retrait demandé du salut, le suivi Discord dans Config, le signalement de couleur mobile et l’autorisation de publier.

La [passation de reprise du Live mobile](../../operations/handoffs/2026-11-27-codex-reprise-fermeture-live-mobile.md#échanges-accessibles) consigne le signalement du micro inactif et le diagnostic de fermeture non confirmée.

La [passation Pétillante et intentions](../../operations/handoffs/2026-11-27-codex-petillante-intentions-live.md#échanges-accessibles) consigne la confirmation du fonctionnement du Live, puis les demandes sur la voix, les intonations, le mouvement et le débit.

La [passation de la pastille Live](../../operations/handoffs/2026-11-27-codex-pastille-live.md#échanges-accessibles) consigne le signalement suivant sur le bleu qui persistait après la coupure du micro et la décision d’affichage.

## Synchronisation du clone de développement le 26 novembre 2026

- **Propriétaire** (extrait de la conversation) « Je veux que tu push le local, mais attention il va y avoir du merge à faire ».
- **Assistant** (synthèse) Conservation des sources du visage r21 et intégration des changements Live mobile sur `develop`. L’index réunit les deux passations. [Travail local sur le visage](../../operations/handoffs/2026-11-26-codex-volume-visage-r21.md) · [Live mobile](../../operations/handoffs/2026-11-26-chatgpt-live-mobile-implementation.md)

## Chambre portrait dans la PWA le 26 novembre 2026

Le signalement du propriétaire et la réponse technique sont résumés dans la [passation de la chambre portrait](../../operations/handoffs/2026-11-26-codex-chambre-portrait.md). Aucune heure individuelle n’est attestée.

## Préparation du modèle r21 le 25 novembre 2026

[Échanges sur la reprise et les MCP](2026-11-25-modele-jade-mcp.md), résumés avec rôles distincts et heures individuelles indisponibles. La [passation opérationnelle](../../operations/handoffs/2026-11-25-codex-jade-r21-reprise.md) et le [plan approuvé](../../../jade-modeling/MODEL2D_MASTER_PLAN.md) décrivent l’état applicable.

## Décisions du 15 novembre 2026 : modèle 2D et intentions

Le propriétaire a corrigé l'interprétation « modèle 3D » : Jade utilise bien un **modèle 2D Live2D**. Il autorise le branchement intention → modèle avec un toggle, demande une approche professionnelle multi-rôles et exige **deux réactions graphiques et deux représentations textuelles par intention**, puis **14 animations réellement différentes** une fois créées. Le lot de base sur la branche `feat/live2d-intent-expression-sync-20261115` utilise des expressions r20 existantes, et réserve les nouvelles motions à Codex jusqu'à validation complète. Cette synthèse ne prétend pas être le verbatim ni contenir des heures individuelles. Voir [passation Live2D](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).
