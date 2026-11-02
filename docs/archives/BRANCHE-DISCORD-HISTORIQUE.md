# Travail historique : branche Discord et reconnaissance vocale

La version active de Jade se trouve sur `main`. Les anciennes branches ont été
consolidées après examen : leur contenu déjà intégré ou remplacé reste dans la
version courante ; la sauvegarde privée conserve l'historique original.

La branche historique `speechtotext-discord` contenait un travail distinct sur
le vocal Discord, une procédure manuelle d'obtention d'un jeton Twitch et une
intégration vocale ElevenLabs. Son [delta historique assaini](speechtotext-discord-historique.patch.txt)
est conservé ici comme document de référence, avec les valeurs et identifiants
privés retirés. Ce fichier n'est pas chargé par l'application et ne doit pas
être appliqué automatiquement : il décrit un code expérimental ancien.

La version actuelle possède un pipeline vocal Discord et utilise OpenAI pour
la transcription et la synthèse. Elle n'envoie une réponse vocale Discord que
pour une demande issue du vocal Discord, alors que l'ancien travail visait un
envoi plus large. La procédure manuelle Twitch historique n'est pas intégrée :
elle affichait des jetons en clair. Ces différences sont conservées ici pour
permettre une évolution explicite si nécessaire ; le vocal Discord réel reste
à valider et les tests simulés ne prouvent pas un fonctionnement en direct.
