# Passation ChatGPT — quick wins VIS-04 et RTE-12 (22 novembre 2026)

## Décision, branches, règles

Le propriétaire a demandé de promouvoir d'abord le `develop` courant sur `main`, puis de réparer la CI si nécessaire avant les nouveaux développements. **PR #41**, fusion normale sur `main` en `6afbe0c`, conserve le baseline validé. Tous les changements suivants sont limités à `develop`. Aucun force-push, aucune activation de modèle ou connexion externe.

Le catalogue d'idées a été dédoublonné par promotion unique :
- **VIS-04 → DEV-027 (P1)** ; entrée active retirée de `docs/ameliorations/04-AVATAR-VISIBILITE.md`.
- **RTE-12 → DEV-028 (P1)** ; entrée active retirée de `docs/ameliorations/03-CANAUX-ROUTAGE.md`.
Le catalogue contient désormais 114 idées prospectives, dont 23 P1.

## Correctif de CI préexistant

Avant le lot, les workflows `Jade rebuild offline tests` étaient rouges : 13 échecs et 5 erreurs Linux, avec divergence entre contrat de mémoire approuvé et vieux tests, plus deux modules utilisant `pytest` pendant la découverte `unittest`. Les tests ont été convertis en `unittest` et alignés sur les décisions validées : Core L3 volontaire par Jade depuis toute identité enrôlée, lectures de souvenirs globales, L2 obligatoire seulement sur demande ordinaire du propriétaire authentifié, pas de citation littérale exigée. L'isolement des écritures, l'absence d'écriture sans identité et les erreurs JSON restent recettés. Les assertions de version SQLite se réfèrent au schéma v8 courant. La publication privée a aussi été corrigée pour copier les deux nouveaux calques WebP de DEV-010 tout en validant leurs en-têtes RIFF/WEBP.

Les corrections ne modifient pas le moteur de mémoire runtime. La suite Windows a déjà terminé avec succès sur le commit pré-développement `fe4a99d` ; une exécution complète Linux/Windows sur le HEAD final du lot doit encore servir de preuve définitive.

## DEV-027 — Live2D mobile en visibilité réelle

- `src/jade_runtime/mobile_web/avatar.js` suspend le ticker PixiJS et, quand exposé par le SDK, le `model.autoUpdate` lors du masquage de l'onglet, de l'absence de composant ou de la sortie de l'avatar hors fenêtre via `IntersectionObserver`.
- Le rendu démarre seulement après chargement complet, visibilité et attachement, puis reprend sans recréer l'avatar ni rejouer l'animation Idle. L'absence d'`IntersectionObserver` utilise au minimum `visibilitychange`.
- Aucun changement de génération des réponses, lecture audio, transport, mémoire ni API. Gain GPU/batterie attendu, **pas de mesure matérielle attestée**.
- `tests/mobile_avatar_visibility_test.js` contrôle démarrage, onglet caché, retour, hors champ, démontage et absence d'API d'observation.

## DEV-028 — preuve de livraison granulaire

- `turn_logging.py` garde `reply_planned` et `delivery_outcome` et ajoute `delivery_evidence` pour **transport_accepted** (Discord texte après réponse API) ou **playback_completed** (ffplay succès / consommation de flux audio Discord).
- `orchestrator.py` recoupe les confirmations rendues par `on_reply` avec les seules destinations planifiées, et consigne la fin des tours PCM Discord anticipés lorsqu'ils ont effectivement été consommés.
- `main.py` confirme l'envoi Discord uniquement après `send_chat` réussi ; un callback mobile/HTTP, l'envoi IRC Twitch non confirmé, la simple planification, le handoff ou l'interruption ne sont **jamais assimilés à une lecture complète**.
- `output.py` sépare « stream géré » de « stream effectivement consommé » pour ne pas confirmer une destination révoquée. Le fait qu'un lecteur audio ait consommé le signal ne prouve jamais qu'un humain l'a entendu.
- Zéro texte, secret, identité, token ou extrait de mémoire dans les nouveaux événements.
- Tests ciblés dans `tests/test_jade_turn_logging.py`, `tests/test_jade_economy_delivery.py` et CI Javascript mobile.

## Validation et suite

Aucun appel OpenAI ni Discord/Twitch réel lancé par les tests. Après CI complète : transférer les deux cartes DEV dans REC au statut `À valider` si seul l'essai réel du propriétaire reste (sans doublon DEV/REC actif). Recette : masquer/remontrer le Live2D mobile et vérifier la reprise de voix/expressions ; observer les journaux d'une réponse Discord, d'une lecture vocale et d'une interruption, et vérifier que les simples handoffs restent non confirmés.

Les tests unitaires et les mesures de coût ne constituent pas une preuve de gain de FPS, de batterie ou de vraie livraison mobile. Ne pas clôturer en `Done` sur seule absence de régression.
