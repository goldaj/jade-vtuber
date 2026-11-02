# Codex : priorités restantes après la refonte de Jade

Toutes les 11 étapes de code préparatoires sont livrées en branche indépendante,
avec tests **hors ligne**. Elles ne constituent **pas** la certification de
fonctionnement du produit en réel.

| Priorité | Travail réel restant | Preuve attendue | Confiance aujourd'hui |
| --- | --- | --- | --- |
| P0 | Revue de la PR brouillon, comportement et sécurité | CI HEAD, revue du diff, aucune fuite de secrets | Élevée sur tests simulés |
| P1 | Windows/PyCharm : régénérer le lock, installer les extras nécessaires, `python main.py --preflight` puis démo | Installation reproductible, diagnostics sans compte, essais réels | Moyenne |
| P2 | Tester **OpenAI** LLM/STT/TTS avec petites entrées, quotas et mesures de latence | Texte/français, WAV lisible, micro, facture contrôlée | Non mesurée |
| P3 | Valider Twitch en direct à faible volume | Scopes IRC, OAuth, PING, message ID, reconnexion, envoi si souhaité | Moyenne |
| P4 | Vérifier VTube Studio API et mappings r20 | Autorisation plugin, ID de hotkey, expression physique visible | Moyenne |
| P5 | Tester Discord guild texte/voix avec autorisations et participants informés | Portail intents, audio PCM reçu, TTS entendu, absence de feedback | Faible à moyenne |
| P6 | Améliorer les tours de parole et latence duplex | Silence, chevauchement, interruption, segments temporels pertinents | Faible |
| P7 | Suivre `PHONE_TAILSCALE.md` sur le PC Jade, limiter les ACL, tester le client mobile HTTPS | Tunnel Serve et essais depuis téléphone, aucun Funnel/public | Faible (tunnel non activé ici) |
| P8 | Livrer vraie mémoire persistante opt-in si besoin | Confidentialité, suppression contrôlée, tests de continuité | À cadrer |
| P9 | Si rigging repris : terminer r21 dans Cubism/VTS séparément | Gate natif candidat r02, export r21 validé, manifestes LFS | Non testé ici |
| P10 | Avant toute publication du dépôt : rotation secrets, droits/licences des assets | Historique assaini dans copie dédiée, accord explicite | Non effectué |

## Limites historiques
- Branches 2025 préservées. `speechtotext-discord` comporte des changements
  non fusionnés directement, pas un module utilisable tel quel.
- `develop` a reçu **seulement** le fichier de coordination et la ligne AGENTS.
  Les changements de runtime restent isolés sur `codex/chat-gpt6-jade-rebuild`.
- Aucun appel API payant, aucune connexion Twitch/Discord, aucun fichier modèle
  natif Cubism modifié par GPT-6 Chat.
- Un `poetry.lock` périmé a été retiré, sans verrouillage des dépendances reconstruit.
- Les tests de voix/Discord/VTS utilisent des mocks et ne certifient pas
  l'intégration aux logiciels externes.

## Critère de clôture de la mission GPT-6 Chat
Livrer le code testé en CI, la PR en brouillon, la documentation de passation
et les limites. **Ne pas merger ni déployer automatiquement.**
