# Friponne rapide sur GPT-Live

Le 28 novembre 2026, le propriétaire écoute **Jade H - Friponne rapide** dans le Playground et choisit cette variante pour `develop`. Il demande de garder les consignes de débit des prompts précédents. Le lot part de `9cf642b`. [Décision du propriétaire](../../history/conversations/2026-11-27-evolution-voix-jade.md#variante-friponne-rapide-le-28-novembre-2026)

Le profil `friponne` utilise la description de création de la variante, avec un débit régulier dès la première syllabe, le registre très aigu et l’accent francilien. Le serveur envoie aussi la consigne « rap god » validée précédemment, y compris pour les réponses déléguées. Le prompt d’origine de Jade continue de définir le débit rapide comme un trait de sa personnalité. L’identifiant de la voix enregistrée se renseigne dans `JADE_LIVE_VOICE_ID` dans la configuration privée du Run, hors Git. [Description et consignes](../../../src/jade_runtime/live_voice.py) · [Passation de la consigne initiale](2026-11-28-codex-friponne-debit-rapide.md)

Les 19 tests ciblés passent hors réseau. Ils couvrent la sélection de la voix et du prompt de chaque transport ainsi que la reprise du débit rapide dans les réponses déléguées.

La [REC-052](../../backlog/02-RECETTE.md#rec-052--voix-friponne-avec-lavatar-de-jade-ancienne-dev-041) reste **À valider** pour le rendu mobile avec l’avatar et l’écoute dans Discord Live. La sélection du Playground valide la préférence de voix.
