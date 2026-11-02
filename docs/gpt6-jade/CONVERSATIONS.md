# Historique de décision identifiable, 24 octobre 2026

Les messages ci-dessous sont des extraits exacts disponibles dans la conversation
courante ; les échanges historiques absents ne sont **pas** reconstruits en verbatim.
L'horodatage individuel n'a pas été fourni.

**Utilisateur (verbatim, extrait de la demande initiale) :**
> Tu vas regarder d'abord tous les docs et instructions qui sont déjà dans le github, faire un plan d'action, sélectionner ce qui est le plus pertinent pour toi, et l'ordonner dans l'ordre le plus pertinent pour le produit ensuite. Puis tu me listeras tout ce que tu as prévu et seulement quand je donnerai mon go tu démarreras les développements.

**Utilisateur (verbatim, précision et autorisation ultérieure) :**
> je suis d'accord avec tout ce que tu as mis. Je rajouterai juste une précision : on retire tous les TTS/STT qui ne sont pas openAI, pour les remplacer par celle d'openAI. On utilisera les meilleures IA du moment fournies par ces API et qui sont centrées sur la vitesse plutôt que la qualité.
>
> Intègre ça à ton plan, puis go. Lance toi tu as carte blanche tant que codex n'est pas passé dessus !

**Assistant (résumé non verbatim) :** plan de refonte modulaire en 11 étapes,
priorités : runtime texte puis voix OpenAI, Twitch, VTube Studio, Discord, mémoire/client léger.
Branche indépendante + coordination `develop` exclusivement documentaire,
rapport après chaque étape.

Voir `docs/CHATGPT_PROJECT_HISTORY.md` pour la mémoire antérieure partielle.
