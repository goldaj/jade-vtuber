# Manuel de Jade : test/intent-all-channels-20261115

**Point de code contrôlé : 3b59e86edc2570196b00e418a361bf5fb852d58f**, avant documentation. Branche **divergente** de develop, non assimilable à la version complète.

Branche expérimentale de tests de journalisation et d'intentions, avec deux commits propres face à develop lors du contrôle. Malgré son nom, main.py dans CETTE branche n'a pas --all-channels. Les tests supplémentaires doivent être comparés aux tests de develop avant toute suppression. Le tronc possède intent_engine.py, pitch_shift.py et turn_logging.py, sans PWA, launcher unifié ni SQLite.

- [Installation depuis un ordinateur neuf](INSTALLATION.md)
- [Démo Express Windows simulée et sans prérequis Python](DEMO.md)
- [Guide utilisateur de chaque fonction présente](USER_GUIDE.md)
- [Architecture/algorithmes/infra](TECHNICAL.md)
- [Passation agents et mise à jour obligatoire des docs](AI_HANDOFF.md)
- [État réel de la branche](BRANCH_STATE.md)
- [Nettoyage des branches Git](BRANCH_MAINTENANCE.md)

Ici aucune PWA mobile, aucun arbitrage LLM ni launcher --all-channels. La Démo Express répond avec des scripts, **pas** avec OpenAI.
