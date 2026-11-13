# ChatGPT : chantier vocal parallèle à Terra, 13 novembre 2026

## Origine de la demande, couverture

Extraits disponibles dans la conversation courante, sans heure individuelle garantie. Cette note documente les demandes et la livraison; ce n'est ni un export exhaustif ni une transcription des appels vocaux.

**Utilisateur, verbatim :**
> Est-ce que tu arriverais à aider terra à avancer sur la branche de Jade qui a été modifiée en dernière ?
> Tu tires une autre branche et comme t'as déjà fait précédemment tu expliques dans la branche ce que t'as fait et ce qu'il reste à faire. Ça me fait gagner des tokens codex comme ça.

**Utilisateur, verbatim (précision de périmètre) :**
> Non non travaille sur ce sur quoi terra travaillait si tu peux l'aider à aller plus vite c'est une grande aide. Si tu peux pas, alors ok et travaille sur ce que tu peux, mais d'abord dis moi ce que tu comptes faire avant de le faire

**Utilisateur, verbatim (autorisation) :**
> T'inquiète. Vas-y tu peux faire ça.

**Utilisateur, verbatim (élargissement) :**
> Mais fait tout, tu peux reprendre après ce qui est directement en cours côté terra. Il fera un merge c'est tout.

**Utilisateur, verbatim (reprise après interruption) :**
> T'as crash reprends

## Réalisation par l'assistant, résumé vérifiable

- Lecture des consignes de projet et du plan latence, inspection de **develop** au commit `f1750f4da77fc8bdc0f7f85bd5bf5d7a55275b08`.
- Création de la branche indépendante `feat/tts-streaming-discord-parallel-20261113`, ouverture de la [PR #1 en brouillon](https://github.com/goldaj/jade-vtuber/pull/1) vers develop.
- Lot B : émission progressive des deltas Realtime 24 kHz, tampon borné, conversion en trames Discord 48 kHz stéréo, lecture dès les premières trames, arrêt et validation terminale.
- Lot C : connexion Realtime réutilisée entre réponses réussies et invalidée sur erreur/annulation.
- Lot D : streaming de phrases LLM vers TTS avec `JADE_EARLY_VOICE=1` **désactivé par défaut**, texte complet livré une fois, historique écrit une fois et arrêt des travaux si la session expire.
- Observateur avatar mis à jour pour suivre les trames lues et nettoyer la bouche à la fin.
- Tests ajoutés : `tests/test_jade_streaming_pcm.py` et `tests/test_jade_early_speech.py`.
- Le contrôle automatisé GitHub a confirmé un état vert sur le commit applicatif `8343b64dda09ffc46f68efdcbdc776172a80bf77` : **347 tests offline, 2 ignorés**, Windows et Linux réussis, scan de secrets et hygiène de publication réussis.
- Aucun lancement de Jade sur le PC, essai vocal humain, appel API payant, fusion sur develop/main ou modification des sources 2D. Les mesures de gain réel ne sont pas disponibles.

## Passation

Le document [HANDOFF-STREAMING-TTS-20261113.md](../gpt6-jade/HANDOFF-STREAMING-TTS-20261113.md) fait foi pour les fichiers, la validation et les risques. Terra doit reprendre ses travaux locaux en cours (notamment lot A bis voix / débit), fusionner cette branche après revue des éventuels conflits, puis tester la voix et la latence sur Discord/téléphone avant activation du lot D. La PR reste brouillon.

## Limites

Les détails des modifications locales non poussées par Terra ne sont pas visibles dans ce contexte. Les tests CI sont hors ligne et ne constituent pas une démonstration de vitesse, de coût ou de rendu audio réel. Le coût de plusieurs synthèses dans le mode phrases doit être comparé avant activation.
