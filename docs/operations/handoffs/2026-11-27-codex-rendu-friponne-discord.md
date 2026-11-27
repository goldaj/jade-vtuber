# Rendu de Friponne sur Discord Live

Le 27 novembre 2026, le propriétaire a signalé une différence audible entre Friponne dans l’application mobile et dans le salon Discord, tous deux en Live. Il préfère le rendu mobile. Le lot part de `develop` à `82c83d4`. L’écoute comparative reste dans [REC-052 · À valider](../../backlog/02-RECETTE.md#rec-052--voix-friponne-avec-lavatar-de-jade-ancienne-dev-041). [Échange accessible](../../history/conversations/2026-11-27-evolution-voix-jade.md#comparaison-de-friponne-entre-le-mobile-et-discord-live)

## Chaîne audio

Les sessions GPT-Live 1.1 des deux canaux demandent Friponne avec les mêmes consignes vocales. L’application mobile joue la piste WebRTC. Le lecteur Discord reçoit du PCM 24 kHz mono, le convertit en 48 kHz stéréo, puis transmet des trames de 20 ms à Discord pour l’encodage. Le contexte conversationnel et la sortie audio peuvent aussi influer sur la perception du timbre. [Configuration Live](../../../src/jade_runtime/live_config.py) · [Contrat Discord](../../architecture/DISCORD_LIVE.md)

Le lecteur applique une interpolation de Lagrange à huit points aux sessions Discord Live. L’état du filtre est conservé entre les blocs et la taille des trames est maintenue. Le filtre introduit un retard de quatre échantillons d’entrée, soit environ 0,17 ms à 24 kHz. [Conversion PCM](../../../src/jade_runtime/discord_pcm.py) · [Raccordement au lecteur](../../../src/jade_runtime/discord_voice.py)

## Vérification

Une passe distincte a mesuré un signal synthétique à 6 kHz, fractionné à l’intérieur d’un échantillon, à la sortie de la conversion PCM locale avant encodage Discord. L’amplitude de la fréquence d’origine baisse de 1,375 dB avec l’interpolation linéaire et de 0,097 dB avec le filtre Live. Les deux versions sortent quatre trames de 3 840 octets pour un signal de 80 ms.

L’écoute des deux canaux dans l’application reste ouverte. Comparer Friponne sur la même réplique et le même casque autant que possible. Écouter la clarté, les consonnes et le rythme.
