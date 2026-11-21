# Jade — plan produit et technique du profil économique (21 novembre 2026)

**Statut : cible produit fixée par le propriétaire ; PLAN UNIQUEMENT, aucun développement ou déploiement autorisé à cette étape.**
**Référence :** `goldaj/jade-vtuber`, branche `develop`, SHA consulté `58553c05e58374ff33f718bc3f404b654b7a40dc`. Les hypothèses techniques doivent être revérifiées au démarrage de chaque chantier. **La configuration privée actuelle ne change pas.**
**Finalité :** améliorer l'agrément d'usage de Jade sur mémoire, sociabilité, voix, mobile et personnalité, en évitant des appels IA permanents. Règle de priorité : conserver la qualité et la confidentialité, puis minimiser le coût réel mesuré, plutôt que viser « zéro token » à tout prix.

## 1. Décisions produit acquises (21/11/2026, révision : initiatives sans quota numérique)

1. **Curation mémoire : groupée par pertinence** : présélection locale, mises en lots ; les décisions d'inscription, notamment des Core Memories, restent exclusivement autonomes pour Jade. Pas de Core imposée par un humain.
2. **Initiatives spontanées : aucun plafond numérique journalier.** Jade peut prendre autant d'initiatives réellement pertinentes que la situation le justifie, toutes plateformes confondues ; elle n'a pas d'objectif minimal de messages. La décision est déclenchée **localement par des événements**, jamais par une interrogation LLM périodique en période inactive. Prévoir des cooldowns adaptatifs par contexte, de la déduplication et un **plafond de dépenses API dédié** configurable et contrôlé avant chaque génération payante. Sur budget épuisé : aucune nouvelle initiative payante, sans bloquer par défaut les réponses sollicitées, qui disposent d'un budget séparé. Distinguer les initiatives des réponses ordinaires et des interventions sociales spontanées. La sécurité des montants repose sur l'estimation prudente, les réservations persistantes et, lorsque possible, les limites côté fournisseur ; un coût exact n'est pas garanti.
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
- **ECO-00B : BudgetGuard** : enveloppes monétaires configurables par jour et par mois, **sous-budget dédié aux initiatives et à leur TTS**, budget distinct pour le classifieur social et les réponses sollicitées, comptage des tentatives et réservations prudentes **avant** appel, annulation/déduplication, horloge et redémarrage, repli sans LLM auxiliaire lorsque le budget concerné est épuisé. Ne jamais activer les initiatives numériques illimitées sans budget monétaire effectif et explicite. Un montant API exact ne peut pas être garanti à partir d'estimations locales ; prévoir marge et contrôle du plafond côté fournisseur.
- **ECO-00C : comparaison** : mêmes scénarios et modèles avant/après, mesurer coût par échange utile, consommation sur 24 h, latences p50/p95, nombre de sollicitations intempestives et erreurs ; distinguer gain théorique et relevé réel.

### Lot B — Mémoire intelligente et personnalité (MEM-11, MEM-15, NRM-10, NEW-18/36)
- **ECO-01 : contexte sélectif** : conserver la mémoire brute existante ; composer le prompt avec un budget de tokens, tours récents prioritaires et épisodes plus anciens récupérés localement selon question/scope/pertinence. Aucun résumé irréversible. Fallback prévisible si recherche indisponible. Tester la reprise de conversation sur 24 h sans perte de capacité de recherche historique.
- **ECO-02 : curation groupée** : file de candidats consentis, filtre local des banalités/doublons exacts, lots bornés par nombre de messages/délai ; au plus une requête de curation par lot ; sortie structurée attribuable à chaque événement. Les demandes explicites de souvenir continuent vers `ordinary` uniquement. Curation Core toujours autonome et indépendante de toute injonction.
- **ECO-03 : recherche et invalidation** : pertinence lexicale/FTS SQLite si supportée, récence, importance, provenance, correction et conflits ; filtrer identité/scope **avant** classement ; invalider caches et lots dès effacement/déliaison/opt-out. Sans embeddings API par défaut.
- **ECO-04 : personnalité** : préférences comportementales et retours explicitement autorisés, profil versionné compact chargé depuis la mémoire admissible, bornes de changement, possibilité de correction/reprise ; réutiliser la curation groupée au lieu de lancer un second LLM après chaque échange.

### Lot C — Sociabilité et initiatives (NEW-10, NEW-17, NEW-16)
- **ECO-05 : SocialDecisionPolicy locale** : état borné par conversation, signaux de participation/mention/contexte/cooldown/activité ; adresses directes et commandes prioritaires ; modèle existant de quotas comme repli.
- **ECO-06 : analyse LLM des ambiguïtés** : mini-contexte limité à la conversation autorisée, réponse JSON bornée `reply|silent` + justification technique, timeout court, budget de décisions **séparé** et cache d'événements déjà évalués. Sur quota épuisé ou erreur : heuristique locale ; jamais d'analyse de toutes les publications.
- **ECO-07 : InitiativeScheduler** : déclencheurs événementiels **locaux et non payants**, liste des destinations permises, heures de tranquillité et **cooldowns adaptatifs par conversation** configurables, anti-répétition et idempotence persistante après redémarrage. **Aucun quota numérique de messages/jour** : le BudgetGuard décide, avant chaque requête facturable et TTS éventuel, si l'initiative reste dans son enveloppe monétaire. Si le budget est épuisé, rester silencieuse pour les initiatives et conserver le traitement ordinaire des sollicitations autorisées. Ne pas créer de cycles de polling LLM, d'écoute STT permanente ou de TTS sans événement. Respecter les frontières entre Discord public, MP, mobile et Twitch.

### Lot D — Voix plus naturelle et streaming mobile (LAT-03, LAT-15, LAT-16, UX-05)
- **ECO-08 : audio bidirectionnel** : transport WebSocket ou équivalent privé au-dessus de Tailscale Serve, audio entrant en fragments bornés, sortie audio existante progressive, identifiants session/tour, ACK/cancel, backpressure, fermeture réseau et repli WAV actuel. L'analyse STT peut toujours attendre la fin de l'énoncé dans la première version : le transport streaming **n'implique pas** du STT continu.
- **ECO-09 : fin de tour et interruptions** : VAD local compatible navigateur/PC selon conditions, réduire l'envoi de silences, barge-in qui coupe effectivement synthèse/lecture/tour obsolète, reprise sans double facturation, pas d'écho de Jade.
- **ECO-10 : usage mobile réel** : Android Wi-Fi/4G/5G, suspension de page, micro refusé, batterie, reprise après réseau interrompu, absence de fuite entre sessions et support du texte sans voix. La recette matérielle appartient au propriétaire.

### Lot E — Intégration et validation transversale
- **ECO-11 : flags/rollback** indépendants pour contexte, curation, social LLM, initiatives et transport mobile, sans migration destructive de la mémoire.
- **ECO-12 : non-régression** : confidentialité deux utilisateurs/deux salons/DM/mobile/Twitch, mémoire liée/déliée, opt-out/oubli pendant tâches en cours, Core autonome, historique 24 h / purges, **absence de limite numérique journalière**, déclenchement événementiel, pertinence et anti-spam, budget monétaire persistant après redémarrage/changement d'heure, arrêt des initiatives payantes à budget épuisé, aucune requête en veille inactive, absence de double TTS et coûts auxiliaires sous plafond.
- **ECO-13 : preuve de recette** : CI et tests simulés offline puis recettes physiques Android/Discord/PC ; comparer au baseline. Ne pas déclarer `Done` pour une recette matérielle non exécutée.

## 4. Paramètres prévisionnels (propositions techniques, non décidés)

- `JADE_MEMORY_CURATION_MODE=batch` ; intervalle et taille des lots à caler sur trafic réel ; **4 lots payants maximum par jour comme point de départ indicatif** et conservation d'une file locale bornée. Une saturation doit se signaler, pas inventer des souvenirs.
- `JADE_SOCIAL_DECISION_MODE=hybrid` ; **6 classifications LLM maximum par jour, toutes conversations confondues** à essayer initialement ; ne pas consulter le LLM sur les décisions triviales. C'est un plafond d'essai des **appels auxiliaires de classification**, indépendant du nombre illimité d'initiatives et du budget monétaire de leur génération.
- `JADE_INITIATIVE_MODE=event_driven` ; **aucun paramètre de limite numérique quotidienne**. Proposer `JADE_INITIATIVE_BUDGET_DAILY_USD` et `JADE_INITIATIVE_BUDGET_MONTHLY_USD` (valeurs à définir après baseline, ne pas activer sans plafond), plus temporisations contextuelles configurables, identité des événements, déduplication, budget TTS et ledger persistant. Le calcul des budgets quotidiens utilise `Europe/Paris` avec tests DST ; aucune décision LLM régulière en période d'inactivité.
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
- Le coût pourrait **augmenter significativement** pendant les périodes très actives si les initiatives sont nombreuses, ou si la classification sociale sollicite trop souvent le LLM. L'absence de quota numérique **n'est pas** une absence de garde-fou : budget financier, déduplication, cooldowns et limites côté fournisseur sont requis. L'inactivité sans événements retenus ne génère aucun appel API **lié aux initiatives** ; la curation mémoire et d'autres traitements peuvent toujours consommer séparément. Les économies de mémoire et d'historique ne sont pas garanties avant mesures.
- Éviter une injection énorme de souvenirs/personnalité dans chaque tour, une session audio permanente, et un classifieur LLM pour chaque phrase publique. Ces trois erreurs annuleraient rapidement les gains.

## 6. Ordonnancement PO et critères de passage

**Jalon 0 :** baseline et BudgetGuard (ECO-00), indispensable avant activer des appels auxiliaires.
**Jalon 1 :** contexte sélectif puis curation groupée, recherche et personnalité (ECO-01 à 04). Seule source fiable de l'historique : SQLite actuel ; aucune perte des règles de 7j/365j/Core.
**Jalon 2 :** politique sociale locale, classifieur hybride limité, puis initiatives déclenchées par événements, à **nombre non plafonné**, conditionnées par un **budget financier global réservé aux initiatives** (ECO-05 à 07). Évaluer qualité, fréquence et coûts sur corpus synthétiques sans appels fournisseurs.
**Jalon 3 :** transport mobile et interruption vocale (ECO-08 à 10). Livraison seulement après essais réels Android/Discord.
**Jalon 4 :** régression globale, métriques avant/après, activation contrôlée et rollback (ECO-11 à 13).

**Critères de passage du lot vers `develop` :** code et tests vérifiés sur la base réelle ; aucune fuite d'une portée de mémoire ; modèles/API supplémentaires optionnels et plafonnés ; preuve des coûts plutôt qu'hypothèses ; validation suivant la DoD. Les chantiers sont planifiés, **aucun ECO-00 à ECO-13 n'a été développé ni testé dans ce document**.

## 7. Règles de lancement ultérieur

Ne pas traiter ce document comme une autorisation immédiate de développer ou déployer. Le propriétaire a explicitement demandé le 21/11/2026 : **« sans développer pour le moment »**. La future reprise devra vérifier le `HEAD` de `develop`, la configuration privée effective, la file d'autres agents, les nouveaux développements entre-temps, puis faire approuver les paramètres non décidés et le budget réel. Pas de modification de `main`, de secrets ou de configuration PC au titre du présent plan.
