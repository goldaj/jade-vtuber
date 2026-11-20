

- **DEV-009** · Le test d'intégration micro fournit 100 ms de PCM synthétique au moteur TTS simulé. Trois tests passent avec Rubber Band disponible et avec le repli simulé. Changement local à valider puis à intégrer ultérieurement dans develop.
- **REC-009** · Neuf tests hors ligne couvrent notamment l'ordre par conversation, la sélection multi-canaux, le repli FIFO et les échéances. La contention sur canaux réels reste à recetter.
- **OPS-006** · La compilation passe. La suite locale initiale a exécuté 499 tests avec un échec dans le contrôle d'export autonome. Cet export omet les fichiers de la chambre PWA. Le problème a été identifié séparément de DEV-009. Le préflight tous canaux exécuté avec la configuration privée de base relève une sortie locale, l'émission Twitch, l'API HTTP et le client mobile à configurer pour ce mode. Le lanceur Discord/PWA emploie une configuration mobile distincte et son propre préflight passe.

- **Export de contrôle** · Le script mobile et l'illustration WebP approuvée rejoignent la liste explicite de l'export, avec vérification d'empreinte et de format avant écriture. Sept tests ciblés de l'export passent. La suite complète a ensuite exécuté 500 tests avec succès, y compris le contrôle dans l'export autonome.

- **Validation distincte Codex** · Sur Windows, le test microphone et les contrôles d'export passent après correction. La suite hors ligne complète passe (500 tests), y compris sa copie exportée. La validation OPS-006 reste partielle en attente du mode tous canaux et du contrôle des assets dans l'environnement de livraison. Les changements sont préparés sur la branche de travail et attendent leur intégration à develop.
