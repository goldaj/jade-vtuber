# Jade — plan produit et technique du profil économique (21 novembre 2026)

**Statut : cible produit confirmée ; développement autorisé ensuite par le propriétaire et engagé sur la PR #34 vers `develop`. Le plan garde les lots de recette et limites restant à traiter.**
**Référence :** `goldaj/jade-vtuber`, branche `develop`, SHA consulté `58553c05e58374ff33f718bc3f404b654b7a40dc`. Les hypothèses techniques doivent être revérifiées au démarrage de chaque chantier. **La configuration privée actuelle ne change pas.**
**Finalité :** améliorer l'agrément d'usage de Jade sur mémoire, sociabilité, voix, mobile et personnalité, en évitant des appels IA permanents. Règle de priorité : conserver la qualité et la confidentialité, puis minimiser le coût réel mesuré, plutôt que viser « zéro token » à tout prix.

## 1. Décisions produit acquises (21/11/2026, révision : initiatives sans quota numérique)

1. **Curation mémoire : groupée par pertinence** : présélection locale, mises en lots ; les décisions d'inscription, notamment des Core Memories, restent exclusivement autonomes pour Jade. Pas de Core imposée par un humain.
2. **Initiatives spontanées : activées par défaut, sans plafond numérique et sans obligation d'un budget monétaire.** Jade peut saluer sur un événement fiable comme l'arrivée d'un humain dans son vocal, **même si personne ne lui a parlé avant**. Elle n'a pas d'objectif de messages et ne vérifie jamais périodiquement via l'API si elle devrait intervenir. **Après une initiative sans réponse humaine, Jade ne se relance pas elle-même** dans ce salon ; elle attend une réaction, ou une nouvelle session si le salon s'est vidé. Seuls les vrais événements et prises de parole peuvent déclencher des coûts. Des plafonds USD sont **facultatifs** et deviennent actifs s'ils sont configurés ; aucune réservation estimative ne garantit le montant définitif facturé par le fournisseur. Les réponses ordinaires ne sont pas bloquées par un plafond d'initiative.
3. **Décision de participation sociale : hybride règles locales + LLM** : le LLM est réservé aux situations réellement ambiguës ; aucun appel de classification sur chaque message observé.
4. **Audio : pipeline actuel STT -> LLM -> TTS**, et **streaming réseau bidirectionnel** sur mobile ; ne pas remplacer automatiquement par un moteur de dialogue Realtime ni changer les modèles facturés.
5. **Historique : conserver la fenêtre des dernières 24 h dans SQLite et la session, mais envoyer un contexte sélectif au modèle**. Ce changement d'assemblage du prompt est explicitement approuvé par cette décision. La rétention niveau 1 reste 7 jours, niveau 2 ordinaire 365 jours, niveau 3 Core sans purge automatique. L'historique n'est pas supprimé ou résumé de manière destructive pour économiser des tokens.
6. **Personnalité évolutive (NEW-18, NEW-36)** : identité centrale stable ; enrichissement à partir de retours et souvenirs autorisés, sans réentraînement automatique ni altération silencieuse des Core.

## 2. État technique constaté avant développement

- `memory_service.py::schedule/_curate` : un appel LLM de curation peut être lancé après **chaque échange admissible** quand l'option de curation est active ; la file asynchrone est bornée, mais ce n'est pas une mise en lots.
- `memory_store.py` : SQLite contient identités, liens, souvenirs, Core de Jade et échanges complets. Les scopes et consentements sont déjà présents ; conserver ces fondations et le rappel privé entre comptes liés.
- `dialogue.py::respond` : la session rechargée depuis SQLite peut transmettre tous les tours des dernières 24 h au LLM, sans plafond de messages. `memory_service.py::context_for` limite déjà les résumés mémoriels distinctement de l'historique.
- `discord_text_policy.py` et `voice_decision.py` : règles d'adresse directe, historique local, quotas/cooldowns et probabilités ; pas de classifieur LLM social systématique. Le comportement Discord vocal dépend également de l'état de session.
- `mobile_gateway.py` : la voix entrante est actuellement capturée en WAV terminé puis transcrite ; la sortie vocale dispose déjà d'une réponse partiellement progressive via `mobile_audio_stream.py`. Ne pas réimplémenter ce qui fonctionne.
- `billing.py` : coûts d'organisation consultables avec une clé admin et cache, mais sans attribution fiable de chaque appel aux fonctionnalités Jade et sans garantie de solde prépayé exact.

## 3. Plan de chantiers et tâches atomiques

### Lot A — Mesure et maîtrise des dépenses (prérequis commun)
- **ECO-00A : baseline** : instrumenter/recueillir par composant (dialogue, curation, classifieur social, initiative, STT, TTS) le nombre d'appels, tokens entrée/sortie si exposés, durée audio, prix calculable et erreurs, sans contenu privé. Séparer mesure locale et relevé de facturation décalé ; garder un mode sans coûts réels pour les tests.
- **ECO-00B : BudgetGuard** : enveloppes monétaires **optionnelles** par jour et mois, distinctes pour les initiatives et le classifieur social, réservations estimatives avant appel, déduplication persistante et coupure de la seule catégorie au plafond si configuré. **Aucun plafond numérique et initiatives actives par défaut**, avec gate événementiel et attente de réponse ; un montant API exact ne peut pas être garanti sans retour de facturation fournisseur. Reste à compléter : coûts réels par fonctionnalité et marge par modèle.
- **ECO-00C : comparaison** : mêmes scénarios et modèles avant/après, mesurer coût par échange utile, consommation sur 24 h, latences p50/p95, nombre de sollicitations intempestives et erreurs ; distinguer gain théorique et relevé réel.

### Lot B — Mémoire intelligente et personnalité (MEM-11, MEM-15, NRM-10, NEW-18/36)
- **ECO-01 : contexte sélectif** : conserver la mémoire brute existante ; composer le prompt avec un budget de tokens, tours récents prioritaires et épisodes plus anciens récupérés localement selon question/scope/pertinence. Aucun résumé irréversible. Fallback prévisible si recherche indisponible. Tester la reprise de conversation sur 24 h sans perte de capacité de recherche historique.
- **ECO-02 : curation groupée** : file de candidats consentis, filtre local des banalités/doublons exacts, lots bornés par nombre de messages/délai ; au plus une requête de curation par lot ; sortie structurée attribuable à chaque événement. Les demandes explicites de souvenir continuent vers `ordinary` uniquement. Curation Core toujours autonome et indépendante de toute injonction.
- **ECO-03 : recherche et invalidation** : pertinence lexicale/FTS SQLite si supportée, récence, importance, provenance, correction et conflits ; filtrer identité/scope **avant** classement ; invalider caches et lots dès effacement/déliaison/opt-out. Sans embeddings API par défaut.
- **ECO-04 : personnalité** : préférences comportementales et retours explicitement autorisés, profil versionné compact chargé depuis la mémoire admissible, bornes de changement, possibilité de correction/reprise ; réutiliser la curation groupée au lieu de lancer un second LLM après chaque échange.

### Lot C — Sociabilité et initiatives (NEW-10, NEW-17, NEW-16)
- **ECO-05 : SocialDecisionPolicy locale** : état borné par conversation, signaux de participation/mention/contexte/cooldown/activité ; adresses directes et commandes prioritaires ; modèle existant de quotas comme repli.
- **ECO-06 : analyse LLM des ambiguïtés** : mini-contexte limité à la conversation autorisée, réponse JSON bornée `reply|silent` + justification technique, timeout court, budget de décisions **séparé** et cache d'événements déjà évalués. Sur quota épuisé ou erreur : heuristique locale ; jamais d'analyse de toutes les publications.
- **ECO-07 : InitiativeScheduler** : déclencheurs événementiels locaux, sans polling LLM ; première intégration : arrivée dans le vocal Discord, réponse parlée via le TTS existant si le membre et la connexion sont toujours présents, sinon texte du chat natif du même salon. **Un premier message est permis sans sollicitation préalable.** Attendre ensuite une réponse/prise de parole humaine ; ne pas relancer si Jade est ignorée. Le salon vidé réarme une nouvelle session. Aucun quota numérique par jour ; budget monétaire **facultatif** et déduplication SQLite. Prévoir d'autres types d'événements et une recette du vrai vocal et du repli écrit.

### Lot D — Voix plus naturelle et streaming mobile (LAT-03, LAT-15, LAT-16, UX-05)
- **ECO-08 : audio bidirectionnel** : transport WebSocket ou équivalent privé au-dessus de Tailscale Serve, audio entrant en fragments bornés, sortie audio existante progressive, identifiants session/tour, ACK/cancel, backpressure, fermeture réseau et repli WAV actuel. L'analyse STT peut toujours attendre la fin de l'énoncé dans la première version : le transport streaming **n'implique pas** du STT continu.
- **ECO-09 : fin de tour et interruptions** : VAD local compatible navigateur/PC selon conditions, réduire l'envoi de silences, barge-in qui coupe effectivement synthèse/lecture/tour obsolète, reprise sans double facturation, pas d'écho de Jade.
- **ECO-10 : usage mobile réel** : Android Wi-Fi/4G/5G, suspension de page, micro refusé, batterie, reprise après réseau interrompu, absence de fuite entre sessions et support du texte sans voix. La recette matérielle appartient au propriétaire.

### Lot E — Intégration et validation transversale
- **ECO-11 : flags/rollback** indépendants pour contexte, curation, social LLM, initiatives et transport mobile, sans migration destructive de la mémoire.
- **ECO-12 : non-régression** : confidentialité deux utilisateurs/deux salons/DM/mobile/Twitch, mémoire liée/déliée, opt-out/oubli pendant tâches en cours, Core autonome, historique 24 h / purges, **absence de limite numérique journalière**, arrivée vocale pouvant initier sans parole préalable, **aucune nouvelle relance sans réponse humaine**, nouvelle session après salle vide, coupure budgétaire si un plafond optionnel est configuré, aucune requête périodique en veille inactive, absence de double TTS.
- **ECO-13 : preuve de recette** : CI et tests simulés offline puis recettes physiques Android/Discord/PC ; comparer au baseline. Ne pas déclarer `Done` pour une recette matérielle non exécutée.

## 4. Paramètres prévisionnels (propositions techniques, non décidés)

- `JADE_MEMORY_CURATION_MODE=batch` ; intervalle et taille des lots à caler sur trafic réel ; **4 lots payants maximum par jour comme point de départ indicatif** et conservation d'une file locale bornée. Une saturation doit se signaler, pas inventer des souvenirs.
- `JADE_SOCIAL_DECISION_MODE=hybrid` ; **6 classifications LLM maximum par jour, toutes conversations confondues** à essayer initialement ; ne pas consulter le LLM sur les décisions triviales. C'est un plafond d'essai des **appels auxiliaires de classification**, indépendant du nombre illimité d'initiatives et du budget monétaire de leur génération.
- `JADE_INITIATIVES_ENABLED=1` par défaut et **aucun paramètre de quota numérique journalier**. `JADE_INITIATIVE_BUDGET_DAILY_USD=0` et `JADE_INITIATIVE_BUDGET_MONTHLY_USD=0` par défaut signifient **aucun plafond**, mais l'idempotence, le silence après absence de réponse et les événements locaux restent obligatoires. Des valeurs USD positives rendent les plafonds actifs. Le calcul des journées suit `Europe/Paris`.
- `JADE_MOBILE_AUDIO_TRANSPORT=stream` avec repli `wav`, sans nouvelle session Realtime conversationnelle facturée.
- `JADE_CONTEXT_MODE=selective` ; fenêtre source de 24 h, budget de contexte à définir par mesures ; ne pas changer les délais de purge SQL.
- `JADE_COST_GUARD` : limites monétaires à déterminer après baseline et sur le tarif du **modèle réellement configuré**. Aucun plafond financier fictif fixé sans chiffres de consommation.
- Chaque flag nouveau doit être désactivé ou repasser au comportement stable tant que les validations requises ne sont pas obtenues.

## 5. Modèle budgétaire et risques

Pour un mois de 30 jours et des enveloppes auxiliaires atteintes :
- initiatives : **aucune limite numérique, donc aucun plafond de 300 tours par mois**. Le volume dépend des événements pertinents, des cooldowns et du budget monétaire effectivement autorisé. Chaque initiative réalisée coûte une génération de réponse et, en voix, éventuellement du TTS ; la détection locale n'ajoute pas d'appel LLM et une initiative ne déclenche pas de STT. Le coût maximal dépend du budget déclaré et d'une estimation prudente, pas du seul nombre de messages.
- analyse sociale proposée : **au plus 180 appels auxiliaires/mois** si le plafond exploratoire de 6/jour est retenu ; chaque requête inclut des tokens d'entrée et de sortie, même si la décision finale est de ne pas répondre.
- curation proposée : **au plus 120 lots/mois** si le plafond exploratoire de 4/jour est retenu, mais ils *remplacent* les appels de curation aujourd'hui potentiellement faits après chaque échange admissible.
- **Formule de comparaison** : `delta ≈ coûts(social) + coûts(initiatives LLM + TTS) + coûts(curation par lots) - coûts(curation actuelle évitée) + écart de tokens de dialogue après contexte sélectif`. Les durées STT/TTS réellement traitées comptent : ne pas assimiler « streaming » à gratuité.
- **Aucun montant mensuel en USD sérieux sans** coût réel par modèle, minutes audio, nombre d'échanges, taux de classification et mode de sortie. Le tableau actuel des coûts organisationnels n'isole pas ces composantes.
- Référence tarifaire publique au 21/11/2026 : `gpt-transcribe` ~**0,0045 USD/min**, `gpt-live-transcribe` ~**0,017 USD/min**. Le choix approuvé n'exige pas ce second modèle. Source : https://developers.openai.com/api/docs/pricing
- Le coût peut **augmenter** avec une forte activité événementielle ; en l'absence de plafonds USD configurés, aucun seuil financier ne stoppe les initiatives. La règle non négociable est leur arrêt après un message sans réponse et l'absence de polling payant en veille. Les limites fournisseur restent recommandées. La curation mémoire peut finir un lot déjà déclenché par une conversation, sans activité autonome continue.
- Éviter une injection énorme de souvenirs/personnalité dans chaque tour, une session audio permanente, et un classifieur LLM pour chaque phrase publique. Ces trois erreurs annuleraient rapidement les gains.

## 6. Ordonnancement PO et critères de passage

**Jalon 0 :** baseline et BudgetGuard (ECO-00), indispensable avant activer des appels auxiliaires.
**Jalon 1 :** contexte sélectif puis curation groupée, recherche et personnalité (ECO-01 à 04). Seule source fiable de l'historique : SQLite actuel ; aucune perte des règles de 7j/365j/Core.
**Jalon 2 :** politique sociale locale, classifieur hybride facultatif, puis initiatives déclenchées par événements, à **nombre non plafonné**, mais arrêt de relance après absence de réponse humaine. Budget financier facultatif. Évaluer qualité, fréquence et coûts sur corpus synthétiques sans appels fournisseurs.
**Jalon 3 :** transport mobile et interruption vocale (ECO-08 à 10). Livraison seulement après essais réels Android/Discord.
**Jalon 4 :** régression globale, métriques avant/après, activation contrôlée et rollback (ECO-11 à 13).

**Critères de passage du lot vers `develop` :** code et tests vérifiés sur la base réelle ; aucune fuite d'une portée de mémoire ; aucun appel fournisseur dans les tests automatisés ; validation suivant la DoD. **Implémentation engagée sur PR #34** : contexte sélectif, lots mémoire, personnalité par souvenirs, décision hybride, initiatives événementielles et transport PCM mobile. **Restent sans preuve matérielle** : Discord/Tailscale/Android réels et coût réel par fonctionnalité ; les ECO non couverts demeurent ouverts.

## 7. Règles de lancement ultérieur

Le propriétaire a ensuite **autorisé explicitement l'architecture et le développement complet** dans la conversation du 21/11/2026. Cette autorisation concerne le code sur une branche de travail puis l'intégration à `develop`, **pas** la modification de `main`, des secrets ou de la configuration privée du PC. Vérifier les protections et la recette physique avant tout passage en production.
