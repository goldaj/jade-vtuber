# REC-006 : instrumentation du streaming PCM Discord, 22/11/2026

- **Mission :** instrumentation sur `develop` demandée par le propriétaire, sans activer Early Voice et sans clôturer REC-006.
- **Base :** `2fb08201c0d0d5a4936e263dfec9a543cf2a64aa`. Publication : commit direct sur `develop`, non sur `main`.
- **Architecture :** portée par tentative PCM Discord (ContextVar isolé par tâche), horloge monotone commune au lecteur 20 ms et au terminal TTS `response.done`. Résumé `rec006_pcm_progress` écrit en console et journal privé de session, sans données utilisateur.
- **Verdicts :** `progressive_confirmed` uniquement si premier PCM non silencieux antérieur à `tts_completed` et lecture terminée ; `progressive_observed_playback_incomplete` si interruption ; `no_overlap_observed` si fin TTS antérieure à la première trame ; `inconclusive` si mesure manquante.
- **Contrôles :** tests unitaires sans service réel ajoutés pour classement, confidentialité des champs et réception de `response.done`. Vérifier la CI sur le commit publié et réaliser l'essai Discord réel : un tour long avec `JADE_EARLY_VOICE=0`, puis rechercher `rec006_pcm_progress` dans la console. L'audition réelle à distance reste une observation humaine distincte.
- **Limites :** aucune mesure physique, TTS facturée ou validation REC-006 lors de cette mission. La première trame est consommée par le lecteur local Discord, non confirmée audible à l'autre extrémité. Aucune modification de `main`.
