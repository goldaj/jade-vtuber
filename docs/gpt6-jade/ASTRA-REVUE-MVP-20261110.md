# Revue Astra du MVP — relais Terra

Revue du 10 novembre 2026, code examiné : `9242d6c` sur `develop`.
Le propriétaire demande une revue et un plan, sans développement sous Astra.
**Revue terminée : reprendre les corrections sous Terra.** Si le chat est
relancé sous Astra sans nouvelle instruction, demander simplement le passage
sous Terra.

## Verdict et périmètre

L'intégration moteur / Discord / avatar r20 est cohérente pour poursuivre la
recette. Deux défauts liés à **silence / arrêt vocal** doivent être corrigés.
Il n'est pas nécessaire de refaire l'architecture, la démo ou le système de
sécurité. Conserver l'accès de tous les participants et bots tiers, sans
consentement supplémentaire, liste d'autorisation ou filtrage de salons.

La CI du commit examiné est verte sous Windows et Linux, ainsi que le contrôle
de secrets existant. Les 328 tests locaux sont le résultat consigné par Terra ;
Astra n'a pas relancé cette suite. La revue a lu les sources et exécuté une
reproduction synthétique ciblée, sans réseau, microphone ni appel OpenAI.
Le rendu r20 et son animation approximative ne nécessitent pas de refonte.

## 1. Faire fonctionner « silence » pendant la lecture — nécessaire

**Preuve :** `OpenVoiceBridge._capture_authorized`
(`src/jade_runtime/discord_voice.py:1030`) rejette les trames pendant
`_playback_active`. `_begin_playback` (ligne 723) vide également les segments
et annule la transcription. Une phrase synthétique « silence » injectée pendant
la lecture n'atteint donc jamais STT : **zéro appel au faux transcripteur**.
La commande fonctionne entre les réponses, mais ne peut pas interrompre Jade.

**Travail Terra :**

1. Réutiliser la segmentation et la transcription existantes pour laisser
   reconnaître une commande courte d'arrêt pendant la lecture. Conserver le
   traitement borné et l'exclusion de la propre voix du bot ; ne pas ouvrir
   une nouvelle chaîne de conversation normale pendant que Jade parle.
2. À la réception de « silence / arrête », couper la lecture et annuler les
   travaux vocaux en cours ou en attente de cette session. Réutiliser
   `Runtime.cancel_work` et les fonctions d'arrêt existantes ; ne pas arrêter
   le runtime ni déconnecter le bot.
3. Maintenir la possibilité de dire « reprends » après l'arrêt. Vérifier le
   retour de la bouche au repos et des sous-titres au vide.
4. Adapter un scénario synthétique existant : lecture en cours → « silence »
   → lecture arrêtée → « reprends » → nouvelle réponse. Vérifier aussi qu'une
   parole ordinaire reçue pendant la lecture ne déclenche pas une boucle.

Le simple retrait de tous les garde-fous demi-duplex serait insuffisant :
préserver la prévention de l'écho, en particulier sur haut-parleur de téléphone.
Pas besoin d'un nouveau moteur STT, d'une infrastructure de streaming ou d'un
classifieur supplémentaire pour cette correction.

## 2. Appliquer le silence à la diffusion vocale des autres sources — nécessaire

**Preuve :** après transcription synthétique de « silence », l'état du décideur
est bien `muted=True`, mais `OpenVoiceBridge.delivery_context()` renvoie toujours
une destination valide. `SpeechOutput._play_other_source` peut donc diffuser une
réponse texte Discord, Twitch ou HTTP dans le même salon. L'état muet n'est
consulté que pour l'admission des tours vocaux.

**Travail Terra :**

1. Exposer l'état silencieux de la session sans recopier un second état métier.
2. Faire respecter cet état par les entrées de lecture du salon, y compris
   `delivery_context_valid` / `play_for_context`. Arrêter la diffusion déjà
   engagée lorsque la commande arrive, quelle que soit son origine.
3. Conserver les réponses textuelles et les connecteurs. Le silence est un
   contrôle de la voix de Jade dans sa session, pas une nouvelle autorisation
   d'accès. Éviter de synthétiser une voix s'il ne reste aucune sortie audible.
4. Compléter le test existant de diffusion intersources : silence → réponse
   externe sans son dans Discord → reprise → son à nouveau. Préserver les
   contrôles existants de déplacement et de reconnexion.

## 3. Fermer la recette réelle — reste connu, pas nouveau chantier

Une connexion au vocal ne prouve pas le passage **DAVE → PCM → STT → réponse →
audio Discord**. Après les deux correctifs :

1. Exécuter une seule fois la suite existante et la compilation sur le code
   final, puis laisser les contrôles GitHub habituels s'exécuter. Ajouter
   seulement les régressions ciblées ci-dessus, pas une nouvelle campagne.
2. Avec le propriétaire disponible, lancer la commande du
   [guide existant](UTILISATION-AVATAR-DISCORD.md), vérifier une vraie phrase
   entendue et une vraie réponse depuis le téléphone, puis les dix tours
   variés déjà prévus : suivi sans nom, silence pendant parole, reprise,
   changement de salon / reconnexion et retour normal.
3. Vérifier ensemble voix unique, modèle visible et bouche acceptable. Pour
   le partage manuel, utiliser au besoin un compte PC distinct de celui du
   téléphone ; couper le micro et la capture du son du compte PC. Ne pas
   remplacer ce parcours par une nouvelle application mobile.
4. Corriger seulement les défauts observés, noter les résultats et limites
   dans `TASKS.md`. Ne pas annoncer la recette complète sans cet essai.

## Livraison Git par Terra

- Travailler dans le dépôt officiel, sur `develop` ; conserver les sources et
  assets actuels. Ne pas toucher à `main` sans décision du propriétaire.
- Corriger les deux points dans le même lot si cela simplifie l'état de silence,
  actualiser le guide et les statuts du plan, puis commit et push sur `develop`.
- Ne pas réintroduire les restrictions de participants, refaire les scans
  historiques ou développer r21, WebRTC, une nouvelle UI ou le benchmark LFM3.
- La note LFM3 est déjà identique dans `develop` et `main` ; aucune branche GPT-6
  supplémentaire n'est à fusionner.

La reprise de conversation et la préparation de la recette doivent attendre
Terra. Aucun correctif runtime n'a été appliqué pendant cette revue Astra.
