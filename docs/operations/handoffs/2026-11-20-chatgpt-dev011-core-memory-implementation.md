# DEV-011 : Core Memories sur instruction explicite de Goldaj (20/11/2026)

- Agent / rôle : ChatGPT, auteur du changement sur branche dédiée.
- Carte : **DEV-011**, P0, jalon A ; statut **À valider** pour la recette PC par Goldaj après tests automatisés réussis. Ne pas classer Done sans recette réelle et validation explicitement enregistrées.
- Départ : `develop` commit `209807c4a2de40f1604d63031e45cf732488cb7b`. Branche `feat/dev-011-explicit-owner-core-memories-20261120`.
- Objectif : demander oralement ou par texte à Jade de placer un souvenir en Core Memory, et obtenir une garantie réelle d'écriture SQLite.
- Implémentation :
  - `src/jade_runtime/owner_core_intent.py` : analyse déterministe à partir d'un verbe explicite et d'une mention « Core Memories » ou d'un équivalent français.
  - `src/jade_runtime/memory_service.py` : commande avant LLM, sans curation, refus des non-propriétaires, contenu vide/trop long/secret courant, confirmation après SQLite.
  - `src/jade_runtime/memory_store.py` : transaction vérifiant l'identité d'origine et l'association active à Goldaj ; stockage autobiographique `jade_self_core` ou relationnel `scope=person`, déduplication intercanaux et effacement par compte source.
  - `tests/test_jade_explicit_core_memory.py` : phrases naturelles, micro/mobile/Discord/Twitch, voix, faux Goldaj, liaison/déliaison, confidentialité, redémarrage, SQL en échec, doublons, runtime sans LLM, suppression.
- Confidentialité : ne jamais prendre un pseudonyme ou une déclaration verbale pour une identité ; l'écriture depuis les comptes liés exige que le même `person_id` soit attaché à l'identité locale vérifiée. Les souvenirs Core du propriétaire ne sont pas réinjectés dans les salons publics. Réponses de succès sans citer le souvenir.
- Commandes de consultation/suppression : `!jade-memoire autobiographie`, `!jade-memoire supprimer-self <id>`, `!jade-memoire lister-core`, `!jade-memoire supprimer-core <id>`, réservées au micro/PWA privée de Goldaj.
- Contraintes : mémoire SQLite activée et profil propriétaire créé ; l'instruction doit explicitement viser les Core Memories ; 400 caractères maximum par souvenir ; pas de réinitialisation/écriture sur le vrai PC.
- Vérifications réalisées : CI GitHub Actions **Linux et Windows réussies** (workflow `44816114240`, code/tests de la PR #29) et **scan secrets réussi** (workflow `44816114280`). La suite inclut des tests du runtime sans LLM ni appels facturés. Revue distincte du code : identité de transport vérifiée sous transaction SQLite, absence de fuite dans les réponses publiques, effacement et déduplication, sans anomalie bloquante observée. Cela ne constitue pas une validation Codex ou une recette PC. Recette réelle PC, PWA et Discord vocal laissée au propriétaire ; statut **À valider**, pas Done.
- Protocole de recette : après récupération de develop et redémarrage, dicter « Jade, je veux que tu gardes ceci dans tes Core Memories : notre première conversation sur Discord. » et vérifier la confirmation ; redémarrer Jade, utiliser `!jade-memoire autobiographie` en entrée propriétaire privée et vérifier la persistance. Vérifier aussi l'échec d'un compte Discord non lié puis la réussite d'un compte lié.
- Aucune modification de `main`, aucun secret, mémoire ni contenu privé publié sur Git.
