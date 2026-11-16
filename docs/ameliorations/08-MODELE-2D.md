# Modèle artistique 2D, rig et animations originales

Le r20 peut servir de démonstrateur sous réserve de recette. **Le r21 intégral en pied n'est pas encore un rig final validé** ; les expressions r20 A/B et textes existants ne constituent pas les 14 animations corporelles demandées.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| ART-01 | P1 / R | Vérifier l'**intégrité visuelle du modèle en pied** : visage, corps, jambes, chaussures, masque, bordures et calques sans trous ou doublons. |
| ART-02 | P2 / E | Finaliser le **rig tête X/Y/Z**, diagonales, raccords cou/épaules et conservation du volume en poses extrêmes. |
| ART-03 | P2 / E | Finaliser les **yeux** (fermeture/réouverture, clignement continu), regard et sourcils ; transitions sans saut visible. |
| ART-04 | P2 / E | Finaliser **cheveux avant/arrière, frange, ahoge et oreilles**, couches indépendantes, racines stables et mouvement fluide. |
| ART-05 | P2 / E | Ajuster physique des **cheveux, oreilles, vêtements et épaules** : amortissement naturel, robe distincte des cheveux, absence de clipping. |
| ART-06 | P2 / P | Créer un **idle vivant mais sobre** : souffle, micro-mouvements, regard, blink et oreilles, sans surcharge CPU/GPU lorsque Jade n'est pas visible. |
| ART-07 | P2 / P | Produire **14 motions réellement distinctes**, deux pour chacune des sept intentions ; validation artistique comparant posture, regard, rythme, mouvement et lisibilité, pas simple renommage. |
| ART-08 | P2 / E | Exporter un **bundle r21 fiable** (moc3, model3.json, motions, expressions, textures, physique) et vérifier Git LFS/licences/SDK, calibration VTube Studio. |
| ART-09 | P2 / P | Synchroniser contrat d'intention v2, **StartMotion/Idle**, transitions, priorité et replis r20 lorsque les 14 animations ne sont pas complètes ; ne pas casser les canaux texte/voix. |
| ART-10 | P1 / R | Recette visuelle réelle Windows et Android : SDK graphique, WebGL/alpha, expressions, bouche sur audio consommé, neutralisation, reprise après arrière-plan, performance et éventuel partage Discord/OBS. |
| ART-11 | P2 / P | **Animations économes** : renderer suspendu quand invisible (voir VIS-06), cache d'assets prêt si affichage probable, réactivation sans saccade et mesures de GPU/RAM/FPS. |
| ART-12 | P3 / D | Compléter les **variations textuelles adaptées** à chaque intention et au support, uniquement si souhaité par le propriétaire, sans pollution de chat public ni métadonnées lues à voix haute. |

**Sources :** [plan r21](../../jade-modeling/PLAN_MODELE_JADE.md), [plan qualité professionnel](../../jade-modeling/PLAN_QUALITE_PRO_20261113.md), [état modèle](../../jade-modeling/MODEL2D_CODEX_STATE.md), [handoff intentions 14 motions](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md), [audit mobile](../gpt6-jade/AUDIT-REVUE-MOBILE-MEMOIRE-20261115.md).
