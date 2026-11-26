# DEV-054 · Live mobile par défaut, sans plafond financier

- **Date :** 26 novembre 2026, Europe/Paris.
- **Demande :** activer Live par défaut dans l'application mobile et publier sur develop ; retirer tous les plafonds financiers mobiles et quotidiens introduits par erreur. Le seuil de 50 EUR/mois, ou 40 EUR si le suivi est incomplet, concerne exclusivement le futur moteur Discord et le total toutes API confondues.
- **Branche :** `fix/mobile-live-default-no-budget-20261126`, départ `origin/develop@48a675b3bca1f562d3e426ed4901668a33eb01ff`. Les évolutions concurrentes r21 sont préservées.
- **Responsables :** coordination ChatGPT/Codex ; sous-agents architecture/sessions, mobile/QA, usage/API. GitHub develop est autorisé par la demande ; main n'est pas concernée.
- **Suivi :** correctif DEV-054 ; critères de REC-044 à REC-050 corrigés, sans prétendre réaliser la recette matérielle. DEV-041 conserve la voix originale, DEV-052 l'adaptateur et l'automatisme Discord après fonctionnement mobile.

## Décisions et changements

1. Live global et mobile ON par défaut ; préférence absente = `live`. Un choix `classic` explicitement enregistré reste respecté. Le démarrage et le chargement du Profil ne capturent rien ; geste micro puis parole nécessaires.
2. Suppression des plafonds quotidien/mensuel mobiles, de la réserve financière backend, des refus d'ouverture et arrêts pour budget. Les anciennes variables de montant sont ignorées, même à zéro ou invalides. Aucun remplacement par un plafond élevé implicite.
3. `LiveUsageLedger` remplace le budget par une mesure passive. Réutilisation du fichier et du schéma historiques sans effacer les données ; le nom de fichier ancien n'est pas une politique financière. Les défauts d'observabilité ne bloquent ni la voix ni les outils. Les registres de sessions/effets restent nécessaires à la fermeture et à l'idempotence.
4. Frontend initialisé avec la préférence serveur avant un geste vocal, sans activation accidentelle du PTT classique. Indisponibilités expliquées dans Profil, échec de module visible et reprise ciblée ; aucun message de budget mobile.
5. Erreurs fournisseur publiques distinctes, avec extraction d'une catégorie de quota strictement autorisée et sans corps HTTP privé. La voix de prototype reste Brise, explicitement nommée ; le préparateur de voix respecte la limite de prompt de 2 000 caractères.
6. La future configuration Discord possède un diagnostic isolé et ne rend pas le mobile indisponible. DEV-052 conserve exactement les seuils mensuels 50/40 EUR sur toutes les API ; aucun plafond quotidien ajouté.
7. Backlog, manuel, architecture, plan et consignes corrigés. Les deux passations initiales sont conservées comme historique avec un avertissement d'abrogation des anciennes limites.

## Vérifications

- Suite complète hors ligne : **884 tests réussis, 12 skips** de transports Discord optionnels dans cet environnement, en 41,524 s (Python 3.12). La suite inclut l’export autonome et l’exécution de ses propres tests ; les deux fichiers renommés sont bien inclus dans l’index Git.
- **25 commandes navigateur du workflow vérifiées.** Le nouveau nettoyage après authentification a révélé un double d’avatar incomplet dans le test de gestes ; il expose maintenant les trois méthodes réellement présentes dans l’avatar, et le scénario est passé sans modifier le runtime.
- Régressions discriminantes : choix Live par défaut, OFF sauvegardé conservé, anciens montants ignorés, usage élevé/panne d’observation sans blocage, outils sans réserve financière, reprise SQLite, cumul sans double compte, callbacks d’authentification périmés ignorés, aucune capture ou création par défaut ON.
- Vérifications ciblées root : 41 tests fournisseur/préflight/pont réussis. Vérification indépendante : 55 tests config/sessions/runtime relancés et 29 tests usage/voix réussis. Compilation, contrôle documentaire/backlog et `git diff --check` réussis.
- **Passe distincte de validation Codex du 26/11 : positive pour DEV-054.** `/root/live_api_costs` valide l’isolement comptable du backend ; `/root/live_architecture` valide le frontend après reproduction puis correction de la course de réauthentification ; `/root/live_mobile_qa` contrôle les critères produit documentaires. Les deux phrases résiduelles sur une admission dépendant du ledger ont été corrigées et revérifiées par root.
- Les appels fournisseur et la capture physique ne sont pas exécutés par cette mission ; les tests utilisent des doubles et des sockets locales. REC-044 à REC-050 restent À valider pour ces observations. La CI Linux/Windows du commit publié doit être suivie séparément ; aucune réussite distante n’est supposée par les résultats locaux.

## Mise en service sur le poste

Après mise à jour develop, redémarrer Jade puis recharger la PWA. Aucun montant mobile à renseigner. Si la configuration privée contient explicitement un ancien `JADE_LIVE_ENABLED=0` ou `JADE_MOBILE_LIVE_ENABLED=0`, le passer à `1` ou retirer la surcharge ; les valeurs du processus/PyCharm restent prioritaires. Si un choix classique avait été enregistré dans Profil, choisir Live une fois. Le diagnostic hors réseau est `poetry run python main.py --preflight --live --mobile`, avec la configuration du lancement habituel.

Les accès du projet OpenAI, la négociation WebRTC et l'audio sur Redmi doivent encore être observés. La clôture en cas de coupure reste supervisée et doit être vérifiée côté fournisseur. Une fermeture incertaine n'est jamais effacée pour faciliter une nouvelle admission.
