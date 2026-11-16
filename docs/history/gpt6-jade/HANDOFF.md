# Jade : passation GPT-6 Chat → Codex

> **Reprise actuelle, 2 novembre 2026 :** consulter [le dossier de migration](../migration/2026-11-02/README.md).
> La PR #2 consolide la PR #1, sans être fusionnée. Les anciennes indications de
> branche et de divergence ci-dessous sont historiques. Le propriétaire confirme
> qu’aucune production n’est active ; le visuel 2D est laissé de côté. Documentation
> préparée pour revue manuelle Astra, corrections et intégration différées sous Terra.

Branche : `codex/chat-gpt6-jade-rebuild`.
Document de coordination sur `develop` : `docs/CODEX_PARALLEL_GPT6.md`.
Ne pas fusionner ni déployer automatiquement.

## Nouvelle consigne du propriétaire — choix de modèle (29 octobre 2026)

Pour Jade, **utiliser Tera 6.1 principalement et par défaut**, notamment
pour toutes les tâches qui manipulent le poste, les outils graphiques, le
modèle Live2D et ses assets : dessin, rig, animation, physique, exports,
tests Cubism/VTube Studio. Astra n'est pas la voie d'exécution habituelle.

En cas de doute nécessitant Astra, **Tera termine et documente la sous-tâche
courante tant que cela reste sûr**, puis **demande lui-même à l'utilisateur
une bascule manuelle vers Astra** en précisant le doute et la décision à
examiner. Si continuer peut endommager les sources ou révéler des secrets,
il préserve le dernier état sûr et demande l'escalade sans action risquée.

**Les revues Astra ultérieures et systématiques éventuellement souhaitées
par le propriétaire sont organisées par le propriétaire hors du processus
Tera.** Tera ne les programme pas, ne les demande pas par routine et ne
s'auto-contrôle pas avec Astra après chaque livraison.

Lire `docs/gpt6-jade/TERA-ASTRA-WORKFLOW.md` avant de planifier une session.
Cette consigne n'autorise ni déploiement, ni publication, ni suppression
d'assets ou de secrets.

## Avant de reprendre
1. Lire `AGENTS.md`, `README.md`, `docs/CHATGPT_PROJECT_HISTORY.md`, puis `docs/gpt6-jade/DECISIONS.md` et `TASKS.md`.
2. Vérifier que tous les STT et TTS actifs sont OpenAI ; aucun service vocal externe ne doit appeler ElevenLabs, Google, ou autre fournisseur.
3. Exécuter les tests hors ligne, puis un démarrage en mode mock, **sans clé ni appel payant**.
4. Valider les adaptateurs avec micro/casques, Discord, Twitch et VTube Studio sur le PC de l'utilisateur, sans streamer publiquement pendant les essais.
5. Préserver `jade-modeling/**` et son Git LFS (pas de retouche binaire involontaire). Vérifier indépendamment `jade-modeling/verify_assets.py` avec LFS téléchargé.
6. Les anciens tokens vivent toujours dans l'historique Git : garder le dépôt privé ; ne jamais journaliser secrets/transcriptions.

## État et limites
- Le code applicatif 2025 est technique-dette, documents/rig 2026 plus récents.
- Seule `speechtotext-discord` contient 7 commits propres, mais inclut des bouts non fonctionnels : aucune fusion brute.
- Pas de preuve runtime voix/stream depuis Chat. Les tests sans matériel et API payantes sont la base de l'assurance qualité.
- Plan produit, étapes testées, CI et blocages : consulter `TASKS.md`.

## Fichiers livrés et commandes de vérification
- Runtime : `src/jade_runtime/` (messages, conversation, queue, OpenAI
  chat + STT + TTS, capture micro, audio/OBS, Twitch, Discord, VTS, HTTP loopback).
- Exécution : `python main.py` pour **démo hors ligne** ;
  `python main.py --live` facturé avec clé valide ;
  `python -m unittest discover -s tests -v` pour les tests sans compte.
- CI : `.github/workflows/jade-rebuild.yml` ;
  consulter la **dernière exécution du HEAD exact**, pas seulement une CI plus ancienne.
- Nettoyage : `LEGACY-AUDIT.md` inventorie les seize modules retirés.
- Blocages matériels, sécurité et recette fonctionnelle dans `NEXT-PRIORITIES.md`.
- Le nouveau code Python n'a **pas** modifié `jade-modeling/**` ; les 202
  assets conservés et ~435 Mo LFS restent soumis au contrôle `verify_assets.py`.
- **Aucune validation réelle** de microphone, TTS, STT, Twitch, Discord,
  websocket VTube Studio ou téléphone distant n'a été exécutée par GPT-6 Chat.

## Recommandation de première reprise
1. Conserver la PR en brouillon et auditer les hypothèses des adaptateurs.
2. Vérifier le lock / les installations Windows puis la démo hors ligne.
3. Tester les appels OpenAI avec plafonds de facturation et les appareils
   avant d'ouvrir les connecteurs.
4. Garder le dépôt privé et nettoyer/révoquer les anciens secrets par une
   procédure distincte si une publication est décidée.
