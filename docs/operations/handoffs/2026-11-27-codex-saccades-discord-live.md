# Continuité de la parole sur Discord Live

Le 27 novembre 2026, le propriétaire a signalé des saccades régulières quand Jade parle sur Discord et une variation de timbre sur le haut-parleur du téléphone quand il coupe le micro au milieu d’une phrase. Lot entrepris sur `codex/discord-live-smooth-playback` depuis `develop` à `c473a94`. [Échange accessible](../../history/conversations/2026-11-27-evolution-voix-jade.md#coupure-du-micro-sur-mobile-et-saccades-sur-discord)

## Saccades sur Discord

La boucle de réception attendait le traitement d’un événement de transcription ou d’usage avant de remettre au lecteur les fragments PCM déjà arrivés. Le lecteur pouvait manquer d’audio à jouer pendant cette attente. En solo, une seule trame de 20 ms au-dessus du seuil pouvait aussi interrompre la réponse.

Une file bornée traite les transcriptions, les délégations et les relevés d’usage dans l’ordre. Les fragments PCM rejoignent le lecteur dès leur réception. Le début d’une nouvelle parole pendant la réponse doit rester au-dessus du seuil pendant 60 ms pour être transmis et interrompre Jade. Le traitement des demandes d’arrêt reconnues reste immédiat. [Adaptateur Discord](../../../src/jade_runtime/discord_live.py)

Deux tests de régression échouent sur l’ancien code et passent avec le correctif. Ils vérifient la livraison du second fragment PCM pendant un blocage du journal et la distinction entre un bruit de 20 ms et une interruption volontaire. Les 44 vérifications ciblées passent. Le test local de la politique financière a dépassé son délai dans la suite plus large, avant la sortie audio. Ce dépassement s’était déjà reproduit sur la version antérieure. L’écoute du correctif dans le salon du propriétaire reste ouverte. [REC-051](../../backlog/02-RECETTE.md#rec-051--live-discord-automatique-et-interrupteur-global-ancienne-dev-052)

## Coupure du micro sur mobile

Le client arrête les pistes locales dès la coupure, tandis que la piste WebRTC distante continue la réponse engagée. Chromium Android peut quitter le mode audio communication lorsque la dernière entrée est libérée. Le passage au mode média peut modifier la restitution sur le haut-parleur pendant cette même phrase. C’est une piste de diagnostic à confirmer sur le téléphone. Le navigateur Android ne donne pas à cette PWA un moyen fiable de garder ce mode audio après l’arrêt physique du micro. [Client mobile](../../../src/jade_runtime/mobile_web/live-client.js) · [Mode audio Android dans Chromium](https://chromium.googlesource.com/chromium/src/media/+/master/audio/android/audio_manager_android.cc#811) · [REC-048](../../backlog/02-RECETTE.md#rec-048--valider-la-capture-live-le-pré-roll-les-pauses-et-les-interruptions-sur-redmi-ancienne-dev-047)
