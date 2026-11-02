# Jade r21 — travail restant

Dernier jalon natif : **v30, matière arrière restaurée et raccords derrière le cou**, sauvegardé le 13 septembre à 07:51 dans Cubism 5.2.03 PRO. Les commandes corporelles v28, HeadZ v29, iris stables et plein pied sont conservés. Petits fragments bas et raccords latéraux restent ; le modèle r21 n'est pas prêt pour le stream. Relance automatique déjà active toutes les 5 h 10.

| État | Étape et composants | Critère de fin |
|---|---|---|
| Fait v23 | Rattachements `EYE_*_CLOSED`, `MOUTH_OPEN`, tête | Branches sous Head Z, position neutre conservée |
| À faire | Affichage neutre : visibilités, masques, raccords | Aucun œil blanc, trou, double dessin ou fragment de tissu parasite |
| Fait v25, jalon natif | Yeux A : intérieur stationnaire, masque animé, cadre paupières rogné à clipping inversé ; 4 ArtMeshes ajoutés, rasters intacts | Iris non aplati ; vrais CLOSED_TRUE à zéro ; .08 et mi-fermeture observés sans les anciens fragments/fondu fantôme |
| Poses clés et réouverture observées ; contrôle continu final restant | Yeux B : fluidité des transitions sur toute la course et réouverture | Aucun saut en lecture continue. Comparaison Ironmouse/Neuro-sama encore non observée image par image ; ne pas prétendre connaître leur rig privé |
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
| Candidat r02 intégré, contrôle natif en cours | Cheveux A2 : deux LOWER reconnectés et deux bandes TEMPLE arrière | Aucune pointe détachée ni découpe claire parasite près des manches |
| Créé, sauvegarde native à faire | Cheveux B1 : neuf feuilles indépendantes avant/frange/ahoge | Une feuille par mèche, pointe blanche et haut solidaires, racine stationnaire |
| 45 poses créées ; LockL±1 observé natif | Cheveux B2 : cinq poses souples par feuille | Courbes progressives, amplitudes différenciées, neutre inchangé |
| À faire | Cheveux B3 : masses arrière réparties et ahoge | Pas de déplacement en bloc ; recouvrements et volume préservés |
| À faire | Tête X/Y puis diagonales X×Y×Z | Volume visage conservé, raccords cou/épaules cohérents |
| À compléter après premières poses v27 | Torse, bassin et coordination des jambes | Déhanchement/rotation complémentaires, appuis naturels et raccords stables |
| À faire | Cheveux arrière puis frange/avant/ahoge | Mèches distinctes, racines stables, volumes souples sans effet de bloc |
| À faire | Oreilles normales | Pointes externes mobiles avec amplitude lisible ; Surprise sans art spécial |
| À faire | Physiques cheveux/oreilles/vêtements | Retards et amortissement naturels, aucun tremblement ou collision gênante |
| À faire | Expressions et raccourcis | Expressions combinables, retour au neutre fiable |
| À faire | Idle vivant : blink, tête, souffle et tressautements d'oreilles espacés | Boucle discrète non mécanique, compatible avec suivi et expressions |
| À faire | Export `.moc3`, `.model3.json`, textures et physiques | Bundle autonome complet installé dans VTube Studio |
| À faire | Paramètres et lissages VTube Studio | Commandes et suivi effectifs, calibration stable |
| À faire | Contrôle final et livraison | Visage/corps/cheveux/expressions vérifiés ensemble ; preuve finale et consignes d'utilisation |

Contraintes : copies versionnées, sources préservées, aucune mise à jour de Cubism, aucun changement du code applicatif. Reprise exacte dans `CONTINUATION.md`.
