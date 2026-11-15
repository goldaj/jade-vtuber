# État réel : feat/turn-conversation-logs-20261115

Pointe contrôlée **a4320c482a3eb78624cc47a37ee0917f8f009b84** avant l'ajout des guides. **Branche divergente** de develop.

Journalisation des tours de conversation (messages, intentions et modalités de réponse), avec module turn_logging.py, adaptation de l'orchestrateur et tests de journalisation. Les dix commits propres recensés face à develop demandent une revue de contenu avant suppression. Pas de PWA mobile, de mémoire SQLite ou de launcher unifié.

## Fonctions effectivement présentes

Moteur Python/Poetry, CLI `--live --voice --mic --twitch --discord --discord-voice --http --vts --avatar --preflight` activables individuellement, Discord/Twitch/HTTP local/micro/STT/TTS OpenAI, avatar r20, VTube Studio optionnel. Queue asynchrone FIFO bornée, sessions RAM, intentions/pitch DSP et **journalisation structurée des tours**. Démo console hors ligne et Démo Express Windows hors ligne/WinForms (ajout documentaire).

## Fonctions absentes

**Pas** de `--all-channels`, de launcher Windows unifié, de `TurnArbiter`, de PWA Android Serve, ni de mémoire SQLite/Core Memories dans ce code. La démo Express n'appelle pas OpenAI et ne représente pas Live2D. Les tests GitHub ne prouvent pas les résultats sur matériel réel.

## Revue

Comparer au contenu actuel de develop : journaux, tests et informations de provenance ; ne supprimer cette branche que lorsque ses apports ont été récupérés et que sa destruction a été approuvée. Voir [BRANCH_MAINTENANCE.md](BRANCH_MAINTENANCE.md).
