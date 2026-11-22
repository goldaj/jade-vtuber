# Passation — chantier Jade multicanal, mémoire, personnalité et latence (22/11/2026)

**Branche isolée :** `feature/jade-multicanal-memoire-observabilite-20261122`, issue de `develop`. **PR brouillon :** [#38](https://github.com/goldaj/jade-vtuber/pull/38). **Aucune fusion dans `develop` ou `main`.** Les validations fonctionnelles réelles ne sont pas déclarées acquises.

## Arbitrages fonctionnels confirmés par le propriétaire

- DEV-021 : **option A uniquement**, communications explicites autorisées entre canaux et continuité de tâches. Pas d'actions externes autonomes supplémentaires.
- DEV-026 : personnalité qui évolue avec ses observations et souvenirs, mais identité initiale stable. Jade choisit seule ses Core Memories ; aucune demande humaine ne peut les imposer.
- DEV-024 : mesurer latences, p50/p95 et coûts avant de fixer des objectifs de vitesse arbitraires.
- Recettes : tester automatiquement ce qui est simulable ; réserver les appareils, les connexions et l'expérience utilisateur aux validations humaines.

## Implémenté sur cette branche

- **DEV-022/023 :** `memory_relevance.py` (classement local pertinent, repli conservateur) ; `memory_store.py` (candidats SQL limités à l'identité et au scope, révision transactionnelle) ; `presence_memory.py` (TTL, expiration d'origine, révocation/écriture/liens), `memory_service.py` ; préchauffage du compte propriétaire au démarrage et des identités Discord existantes à l'arrivée en vocal. Aucune requête modèle supplémentaire.
- **DEV-026 :** `personality_evolution.py` produit un profil dérivé, versionné et reproductible depuis les seules mémoires visibles ; correction/suppression en SQLite modifie le profil. Aucun nouveau moteur d'apprentissage autonome en arrière-plan.
- **DEV-021 :** `cross_channel.py` persiste les tâches privées du propriétaire ; `!jade-tache ajouter|liste|reprendre|terminer` ; `!jade-transfert discord:ID message` seulement depuis un canal privé d'une identité propriétaire vérifiée vers un ID Discord **explicitement autorisé en configuration locale**. Les historiques ne sont pas publics. Les deux capacités sont intégrées au runtime.
- **DEV-025 :** `group_context.py`, `discord_text_policy.py`, `social_intelligence.py` reconnaissent les messages adressés à un autre humain et ajoutent des extraits bornés du même salon au contrôle social. Pas d'appel LLM sur chaque message.
- **DEV-024 :** `turn_metrics.py` enregistre les jalons techniques et les quantiles p50/p95 côté serveur sans contenu ni identité ; point de consultation privé `POST /api/metrics` avec corps `{}` ; **le premier son effectivement entendu et le coût fournisseur exact par tour restent `null` faute de preuve**, jamais inférés.
- **DEV-020 :** `deploy_supervisor.py` est un superviseur **séparé du processus Jade**, avec HTTP loopback + jeton privé, choix limité aux branches `origin/*` existantes, sauvegarde du SHA précédent et tentative de reprise après échec ; `deployment_client.py`, PWA et `POST /api/deployment` sont raccordés. Aucune commande shell, URL ou chemin ne vient de la requête mobile. L'exécution Windows en conditions réelles n'est pas validée.
- **DEV-010 :** le script `room-motion.js` ne déforme plus les pixels fixes du cadre. L'illustration reste **statique** jusqu'à la fourniture de deux vrais calques `room-backdrop.webp` et `room-curtain.webp`. Ces deux fichiers ne sont **pas inclus** et ne sont donc pas déclarés dans les routes statiques. La réparation artistique complète n'est pas livrée.
- **OPS-015 :** `tools/jade_art_asset_audit.py` est un inventaire en lecture seule des doublons binaires/noms apparentés. Ni suppression ni analyse visuelle sémantique.

## Paramètres privés et exploitation

- `JADE_CROSS_CHANNEL_DISCORD_TARGETS` : liste de snowflakes numériques Discord séparés par des virgules ; aucun envoi externe si la liste est vide.
- `JADE_DEPLOY_SUPERVISOR_TOKEN` : jeton privé distinct de 32 à 256 caractères ; à placer **hors Git**, dans les paramètres privés du poste. Si absent, l'administration mobile retourne « superviseur non configuré ».
- `JADE_DEPLOY_SUPERVISOR_PORT` : port loopback (8770 par défaut) ; ne jamais ouvrir l'interface sur le LAN, Internet ou via Funnel.
- Superviser Jade depuis un **checkout distinct du répertoire PyCharm/Codex** pour éviter qu'un changement de branche destiné à l'exploitation modifie le travail en cours. Démarrer et maintenir le superviseur via le planificateur Windows avec son interpréteur Python et sa commande de démarrage en arguments JSON locaux. Celui-ci doit être propriétaire du processus Jade. Il ne peut pas adopter un processus Jade démarré antérieurement.
- Après `git fetch`, le superviseur valide le nom parmi les branches distantes existantes puis passe sur un SHA en état détaché ; la branche Git distante n'est jamais modifiée.

## Vérifications réalisées et frontières

- Tests unitaires hors ligne ajoutés dans `tests/test_jade_chantiers_20261122.py` : recherche et portée, rafraîchissement du cache, expiration imminente, autonomie du profil, adressage de groupe, continuité privée, allowlist Discord, métriques et récupération locale après erreur.
- CI GitHub Actions PR #38 : voir les derniers runs **economic interaction offline tests**, **rebuild offline tests** et **secret scan**. Ne pas considérer un run annulé par de nouveaux commits comme réussi.
- **À recetter sur le vrai poste après intégration :** permissions Tailscale, accès MP du propriétaire lié, transferts Discord, plusieurs participants en vocal, latence vue par le client, coût fournisseur réel, lancement du superviseur via le planificateur, rollback Windows, et calques artistiques du rideau.
- Les cartes d'origine restent ouvertes sur `develop` tant que la branche n'a pas été intégrée et que la qualification/recette n'est pas conclue. Ni `Done` ni changement de statut artificiel.
- Aucun nouvel appel OpenAI facturé ou connexion Discord réelle n'a été effectué dans cette mission.

## Limites fonctionnelles explicites

Ce chantier constitue une **première implémentation testable**, pas une conformité intégrale déclarée aux attentes de toutes les cartes : DEV-021 n'orchestre pas encore spontanément une tâche sans commande explicite ; DEV-025 n'a pas de suivi sémantique complet des fils parallèles ; DEV-024 ne sait pas corréler chaque facture fournisseur ni confirmer le rendu sonore côté appareil ; DEV-010 attend ses vrais calques ; DEV-020 doit être validé sur Windows. Traiter ces différences comme **reste à faire**, pas comme erreurs de documentation effacées.

## Compléments de la reprise : stabilité prioritaire (22/11/2026)

**Consigne propriétaire nouvelle :** si un résultat demande une refonte disproportionnée, des appels modèle permanents ou menace le comportement actuel, **ne pas forcer** ; documenter l'écart, ne pas annoncer `Done`.

### Actions intercanaux, option A uniquement

- `CrossChannelContinuity` dispose désormais de quelques formulations françaises non ambiguës en plus des commandes `!jade-` : « Jade, ajoute une tâche : ... », « Jade, liste mes tâches en cours », « Jade, reprends la tâche ID », « Jade, termine la tâche ID », « Jade, envoie ce message sur Discord dans le salon 123 : ... ». Il n'exécute **pas** une intention ambiguë, n'effectue aucune action externe autre que l'envoi explicitement autorisé et ne déclenche pas d'appel LLM.
- La sélection de la tâche active est persistée pour le **propriétaire vérifié**, accessible depuis un MP Discord **réellement lié** ou la PWA privée, jamais un salon public. La lecture ne prend plus systématiquement un verrou SQLite d'écriture.
- **Limite délibérée :** ne pas interpréter toutes les formulations libres comme des actions, ni confier au LLM des outils d'envoi arbitraire : cela exigerait davantage de contrats, de tokens et de recettes de sécurité. Une commande floue aboutit à une conversation ordinaire sans action implicite. Cela ne remplit donc pas encore la promesse d'une orchestration intercanaux pleinement autonome et universelle.

### Personnalité évolutive

- Recalcul déterministe à partir des souvenirs autorisés, sans deuxième LLM ; le profil tient compte de la récence et évite d'énoncer plusieurs préférences contradictoires sur un même sujet.
- Une mémoire L2 explicitement **imposée par le propriétaire** ne devient plus automatiquement un goût personnel de Jade : sa personnalité et ses Core Memories restent de son ressort.
- **Limite délibérée :** ne pas créer un nouvel entraînement, une IA d'auto-évaluation permanente ou un agent autonome de modification de prompt. Un jugement fiable de son « évolution réelle » nécessite une recette longitudinalement observée sur plusieurs sessions. Le profil mémoriel est une base contrôlée, pas une preuve d'apprentissage humain ou d'expérience indépendante.

### Objectifs de performance

- Les métriques serveur conservent p50/p95, statuts et étapes ; désormais les **tokens d'entrée/sortie réellement rapportés par le fournisseur** sont attribués au tour actif, et la **durée STT mobile** est capturée avant l'entrée dans la file.
- **Limite technique incontournable :** le serveur peut voir le premier PCM transmis ou joué par un périphérique logiciel, mais **ne peut pas confirmer que le son a été réellement entendu** (volume matériel, système muet, écouteurs, Bluetooth). L'application mesure déjà première trame reçue et première programmation audio ; ne pas rebaptiser cette métrique « audible ».
- **Limite économique :** les compteurs de tokens ne constituent **pas un prix par tour confirmé** ; les API/budgets du compte peuvent être agrégés ou différés. `cost_usd=null` est préférable à une estimation affichée comme facture exacte.
- **Aucune cible chiffrée arbitraire** ni nouvelle invocation OpenAI pour profiler, évaluer la personnalité ou interpréter les groupes. La mesure de base sur vrais dispositifs appartient à la recette.

### Garantie de non-régression

- La suite GitHub Actions sert de garde-fou. Une régression transitoire des tests vocaux PWA a été identifiée après l'ajout des métadonnées STT (import `math` manquant dans `messages.py`) puis corrigée sur la branche isolée. Ne jamais propager cette version intermédiaire en production.
- Les tests hors ligne couvrent maintenant la compréhension restreinte des ordres, l'association/révocation de comptes, la confidentialité des salons publics, l'expiration mémoire, les préférences corrigées et l'attribution des tokens au tour en cours. Les versions intermédiaires échouées ne sont pas déclarées validées.
- Priorité d'acceptation : **tout le fonctionnement existant continue de répondre avant d'augmenter la couverture du backlog**. Aucune fusion ni clôture de carte avant les contrôles finaux.
