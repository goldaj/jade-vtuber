# Reprise Terra : latence et lancement local

Journal partiel du chat accessible ; heures individuelles non fournies. Aucun
secret, identifiant privé, enregistrement ou transcription vocale n'est reproduit.

## Utilisateur — verbatim

> on est sous terra, tu peux y aller.
> Tu lanceras aussi le projet en local une fois terminé, pour que je puisse faire des tests sur mon téléphone via discord de nouveau

## Assistant — résumé de la reprise

Exécution sur `develop` du [relais latence et voix](../gpt6-jade/PLAN-LATENCE-20261110.md),
puis lancement du parcours local Discord pour la recette depuis le téléphone.
La confirmation audio/vidéo et les mesures au téléphone doivent provenir d'un
essai réel ; elles ne sont pas déduites des tests automatisés.

## Instruction de relance — enveloppe du 13 novembre 2026 à 08:50:17 UTC

Vérifier une éventuelle branche GPT-6, la challenger puis l'intégrer et la
supprimer si pertinente. Terminer le chantier, mettre Jade sur Discord et tenter
le partage d'écran. Une fois le travail terminé, répondre « OK » aux prochaines
relances planifiées sans nouvelle demande. L'heure est celle de l'enveloppe,
pas celle d'un message individuel reconstruit.

## Utilisateur — verbatim, reprise

> Go!

## Assistant — état de coordination

La branche GPT-6 sur le streaming existe et chevauche la réalisation locale ;
les deux travaux doivent être conservés et intégrés. Leur validation ne peut
pas être déduite de la CI d'un autre commit.

## Assistant — état de la réalisation

La réalisation parallèle GPT-6 et le travail local Terra ont été réunis :
diffusion progressive, session TTS réutilisée, phrases facultatives et vitesse
×1,5. Plusieurs erreurs de transition et d'arrêt détectées pendant la fusion
ont été corrigées. Un essai OpenAI synthétique court a confirmé le texte par
flux, le PCM progressif, le débit réglé à 1,5 et la réutilisation de session.
Cet essai ne prouve pas l'audition ni la latence sur téléphone. Aucune
correspondance API documentée d'Aube n'a été trouvée ; la voix précédente reste
utilisée. Le lancement et le partage Discord sont à constater séparément.
La suite complète de l'intégration compte 391 tests hors ligne réussis sous
Windows, ainsi qu'une compilation réussie ; cela ne remplace pas la recette réelle.

Le merge `4ee1879` est sur `develop` : CI Windows/Linux et scan de secrets
réussis. La branche GPT-6 et le checkpoint local ont été supprimés après contrôle
de leur présence dans l'historique. Le processus Jade a été lancé, la connexion
du bot au vocal et l'existence de la fenêtre r20 ont été constatées. La capture
de la fenêtre Discord a expiré ; le partage d'écran n'a donc pas été commencé.
La réponse vocale et la vidéo de cette nouvelle version restent à vérifier par
le propriétaire sur son téléphone.

## Utilisateur — demande de nouvelle reprise, verbatim

> Gpt 6 a push de la nouveauté sur develop. Contrôle si c'est ok pour toi. Push ce que t'as en local si t'as du local, dès que t'es prêt tu mets tout sur develop et tu redeploie Jade sur mon poste sur sa nouvelle version

## Assistant — contrôle de la reprise

Le dépôt local était propre ; `develop` distante contenait l'évolution de
participation écrite Discord et la personnalité demandées dans le
[journal dédié](2026-11-13-discord-text.md). La branche de travail distante
présente le même contenu que le squash déjà sur `develop`. L'ancienne instance
Jade a été arrêtée proprement avant la mise à jour locale ; aucune autre
application ou service n'a été arrêté. Le redémarrage et la recette sont à
consigner après leur constat réel.

## Utilisateur — décision sur les branches, verbatim

> Ah et j'ai confiance à cette branche develop une fois que tu auras fini ça. Donc on mergera develop dans main, pour le mettre à jour. On continuera quand même de travailler sur develop par la suite. On ne mergera dans main que quand je te le dis à chaque fois

Le propriétaire autorise la fusion actuelle après vérification et redéploiement ;
cette autorisation ne vaut pas pour les fusions ultérieures. Préserver les
commits propres à `main` lors de la fusion et rester sur `develop` localement.

## Assistant — résultat de la reprise

La diffusion vocale des réponses Discord écrites a été conservée tout en
intégrant la participation textuelle. Le code `98126e9` est sur `develop` ;
405 tests hors ligne et la compilation ont réussi. Jade a été relancée sur le
PC : son processus, la connexion au vocal Discord et la fenêtre r20 ont été
constatés. La recette humaine, les réponses écrites réelles et le partage
d'écran ne sont pas déduits de cette observation. La fusion `main` demandée
reste à effectuer après les vérifications Git correspondantes.
