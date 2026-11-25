# Jade r21 — travail restant

Le modèle utilisé dans VTube Studio est **Jade v45.1**, avec les iris retouchés sur le rig de parole v43. Le tableau conserve les jalons de construction depuis le v32. Le [point de reprise](CONTINUATION.md) donne le paquet, les gestes et l’atelier actuels. Le [plan directeur approuvé](MODEL2D_MASTER_PLAN.md) décrit la préparation du paquet de livraison et sa calibration.

| État | Étape et composants | Critère de fin |
|---|---|---|
| Fait v23 | Rattachements `EYE_*_CLOSED`, `MOUTH_OPEN`, tête | Branches sous Head Z, position neutre conservée |
| À faire | Affichage neutre : visibilités, masques, raccords | Aucun œil blanc, trou, double dessin ou fragment de tissu parasite |
| Fait v25, jalon natif | Yeux A : intérieur stationnaire, masque animé, cadre paupières rogné à clipping inversé ; 4 ArtMeshes ajoutés, rasters intacts | Iris non aplati ; vrais CLOSED_TRUE à zéro ; .08 et mi-fermeture observés sans les anciens fragments/fondu fantôme |
| À finir, après le premier paquet utilisable | Yeux B : fluidité des transitions sur toute la course et réouverture | Aucun saut en lecture continue. Comparaison Ironmouse/Neuro-sama encore non observée image par image ; ne pas prétendre connaître leur rig privé |
| À faire | Regard et sourcils | Regard centré et extrêmes propres, émotions lisibles |
| Première version native v24 | Bouche `ParamMouthOpenY` × `ParamMouthForm` ; 4 meshes ouverts subdivisés de 4 à 49 sommets | Sourire/neutre/triste combinables à six ouvertures ; expressivité à renforcer, pas encore phonèmes complets |
| Fait v26 : assemblage natif initial | Jupe courte, jambes et chaussures, haut conservé | Cinq ArtMeshes visibles dans Cubism ; canevas étendu sans réduction du visage |
| À faire | Finition bas du corps : contours, chevilles, ceinture et jonctions bras | Aucun décroché, frange colorée ou trou ; recouvrements propres aux poses extrêmes |
| Fait v27 | Hiérarchie corps complet, bassin/jupe, jambes R/L et chaussures R/L | 7 nouveaux déformeurs, neutre conservé à <0,001 px, pieds dans les grilles |
| Fait v27, premières poses | Appuis et balancement : ParamJadeWeightShift + ParamJadeSkirtSway | Cinq clés chacun ; déplacements et combinaisons observés natifs, pieds stables |
| Fait v28, premières poses | Détente indépendante genoux R/L | Trois clés 0/.5/1 ; détente légère vers l'intérieur, raccord haut préservé, pieds stationnaires |
| Fait v28, première amplitude | Respiration thoracique ParamBreath | Trois clés 0/.5/1 ; expansion douce et montée des épaules, tête déplacée sans écrasement |
| CMO3 fait ; KRA/PSD à synchroniser | Réintégration des cinq pièces dans la source art et mise à jour du lien PSD | Réimport sans substitution par l'ancienne ceinture |
| Intégré v29 ; raccords arrière à finir | Robe et épaules séparées des cheveux ; quatre textures de tissu/cou remappées | Le col ne suit plus les mèches ; finition des espaces derrière cou/épaules restante |
| Fait v29, jalon limité | Inclinaison tête Z et pointes avant d'origine | -30/0/+30 observés ; pointes blanches suivent la tête sans rester peintes sur le col |
| Partiel v30 | Cheveux A1 : six segments arrière + deux recouvrements derrière le cou | Matière restaurée depuis le maître ; neutre et HeadZ ±30 observés |
| Intégré au v31/v32, raccords combinés à vérifier | Cheveux A2 : deux LOWER reconnectés et deux bandes TEMPLE arrière | Aucune pointe détachée ni découpe claire parasite près des manches |
| Intégré au v31/v32, mouvement combiné à finir | Cheveux B1 : neuf feuilles indépendantes avant/frange/ahoge | Une feuille par mèche, pointe blanche et haut solidaires, racine stationnaire |
| 45 poses créées ; LockL±1 observé natif | Cheveux B2 : cinq poses souples par feuille | Courbes progressives, amplitudes différenciées, neutre inchangé |
| À faire | Cheveux B3 : masses arrière réparties et ahoge | Pas de déplacement en bloc ; recouvrements et volume préservés |
| À faire | Tête X/Y puis diagonales X×Y×Z | Volume visage conservé, raccords cou/épaules cohérents |
| À compléter après premières poses v27 | Torse, bassin et coordination des jambes | Déhanchement/rotation complémentaires, appuis naturels et raccords stables |
| À faire | Cheveux arrière puis frange/avant/ahoge | Mèches distinctes, racines stables, volumes souples sans effet de bloc |
| Deux contrôles de pointes dans v32, mouvement à valider | Oreilles normales | Pointes externes mobiles avec amplitude lisible ; Surprise sans art spécial |
| Physique candidate pour les neuf sorties avant et ahoge, calibration et autres familles à faire | Physiques cheveux/oreilles/vêtements | Retards et amortissement naturels, aucun tremblement ou collision gênante |
| Smile et Sad préparés localement, à assembler | Expressions et raccourcis | Expressions combinables, retour au neutre fiable |
| Boucle de 36 s préparée localement, à activer et calibrer | Idle vivant : blink, tête, souffle et tressautements d'oreilles espacés | Boucle discrète non mécanique, compatible avec suivi et expressions |
| Premier export après contrôle du v32 et feu vert | Export `.moc3`, `.model3.json`, textures et physiques | Bundle autonome complet installé dans VTube Studio |
| À faire | Paramètres et lissages VTube Studio | Commandes et suivi effectifs, calibration stable |
| Fait en v45 | Deux motions corporelles par intention | Quatorze clips éditables, joués en parole dans VTube Studio. Bascule entre deux intentions, suivi, appuis et reprise de l’idle contrôlés. |
| À faire | Contrôle final et livraison | Observation en direct dans VTube Studio du visage, du corps, des cheveux, des expressions, de la parole et des 14 motions originales |

Copies de travail sur D: avec les sources préservées. Utiliser Cubism PRO 5.3.05 avec Turboism et PSD2Live sur un projet séparé. Reprise dans [CONTINUATION.md](CONTINUATION.md).
