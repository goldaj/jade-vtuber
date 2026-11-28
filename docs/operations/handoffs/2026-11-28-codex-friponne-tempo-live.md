# Essai de lecture accélérée de Friponne

## Retrait après écoute

Le 28 novembre 2026, le propriétaire demande de retirer l’essai `cd437aa` car le timbre est trop modifié et les transitions de ×1,10 vers ×1,00 sont audibles. Le retrait sur `develop` ramène le code et les tests audio à la référence `01351b1`. La consigne de parler vite dans les prompts de Jade et de Friponne reste en vigueur. Le Worklet de sortie mobile, le rééchantillonnage adaptatif Discord et le paramètre de vitesse associé sont retirés.

Le contrôle de l’arbre Git, la compilation et les 43 tests ciblés de configuration, de voix, du lecteur mobile et de PCM Discord passent. La décision du propriétaire clôt l’essai de post-traitement. La [REC-052](../../backlog/02-RECETTE.md#rec-052--voix-friponne-avec-lavatar-de-jade-ancienne-dev-041) reste ouverte pour le rendu de Friponne avec l’avatar.

## Historique de l’essai

Le 28 novembre 2026, le propriétaire autorise l’essai d’une lecture plus rapide sur mobile et Discord Live et accepte que la voix monte dans les aigus. Il demande d’abord la publication de l’état de `develop` sur `main`. Le commit `ad1e1e64676107bbbb1cd24fef53078ee963d14c` sur `main` a le même arbre que `develop@01351b1`. Cette révision sert de référence pour écouter Friponne avant l’ajout du traitement audio. [Échanges accessibles](../../history/conversations/2026-11-27-evolution-voix-jade.md#essai-de-lecture-accélérée-de-friponne-le-28-novembre-2026)

Dans l’essai publié sur `develop`, la lecture du signal GPT-Live de Friponne pouvait accélérer jusqu’à ×1,10 sur les deux canaux, ce qui remontait la hauteur d’environ +1,65 demi-ton à la vitesse cible. L’essai utilisait le profil `friponne` et sa consigne de débit rapide.

Le mobile traitait en Web Audio la piste distante reçue par WebRTC. Discord adaptait sa lecture PCM avant de former les trames destinées au salon vocal. Les lecteurs revenaient progressivement vers ×1,00 lorsque leur réserve diminuait.
