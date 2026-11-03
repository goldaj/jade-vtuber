# Note de R&D — modèle local pour Jade et piste LFM3 (2026-11-03)

**Origine :** demande prospective du propriétaire, 3 novembre 2026.
**Statut :** piste de veille/benchmarks futurs, sans modification du moteur actuel ni changement de fournisseur.

## Question

Lorsqu'un **PC dédié** sera disponible pour Jade, réexaminer l'état de l'art des modèles locaux pour envisager un moteur d'inférence autonome. L'architecture **LFM3, annoncée comme tri-hybride**, est identifiée comme candidate actuelle intéressante pour son rapport performances/ressources.

Le propriétaire mentionne une comparaison favorable à LFM3 face à **Qwen 3.5 9B**, malgré une taille environ six fois inférieure. **Ce résultat est une affirmation à vérifier**, pas un benchmark effectué par le projet. Ne pas figer le choix du modèle aujourd'hui : une autre architecture pourrait être meilleure au moment de l'achat du PC et de l'intégration.

## Critères à mesurer lors de l'étude

- Licences, disponibilité effective des poids, comportement en français, capacités de raisonnement, dialogues, continuité du personnage et maintien du contexte.
- Qualité pour les usages de Jade ; latence premier token, tokens/seconde, RAM/VRAM, consommation, intégration avec Python et composants de voix/VTuber.
- Benchmark comparatif reproductible contre les meilleurs petits modèles pertinents **au moment de la reprise**, sur le matériel cible, à tâches et budgets équivalents.
- Budget total et coûts locaux/amortissement versus les solutions API (sans supposer qu'un chiffre de benchmark général prédit la qualité de Jade).
- Séparation et bascule sûre entre moteur local, moteur API et fonctions voix ; ne pas activer de service ou de dépense automatiquement.

**Décision :** aucune. Conserver cette piste pour la revue d'architecture de Jade après disponibilité du PC dédié.

Le verbatim privé de l'utilisateur est conservé dans le dépôt privé Notepad ; ce document public est une synthèse technique sans transcription de la conversation.
