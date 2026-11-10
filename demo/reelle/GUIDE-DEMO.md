# Jade — guide de la démonstration Windows

Cette démonstration présente un personnage Live2D animé accompagné d'un vrai
dialogue et d'une voix OpenAI. Une connexion Internet, une clé API OpenAI à
votre nom et un compte API disposant d'un budget sont nécessaires pour discuter.
Les appels sont facturés sur votre compte. L'utilisation de l'API est distincte
d'un éventuel abonnement ChatGPT. La voix est générée par intelligence artificielle.

## Installation

1. Extrayez le ZIP si l'installateur est dans une archive.
2. Lancez `Installer-Jade.exe` et suivez les indications. L'installation est
   prévue pour votre compte Windows, sans Python, Steam ou VTube Studio à installer.
3. Lancez Jade depuis le menu Démarrer ou le raccourci créé par l'installateur.
   Deux fenêtres s'ouvrent : le personnage animé et le panneau de discussion.

L'installateur de cette version n'est pas signé numériquement : Windows peut
afficher un avertissement. Avant son lancement, vérifiez sa provenance et
comparez son empreinte SHA-256 à celle communiquée séparément par l'auteur.
Le fichier `SHA256SUMS.txt` de l'archive aide à contrôler les octets ; à lui
seul, il ne prouve pas l'identité de l'expéditeur.

## Parler avec Jade

1. Dans le panneau de discussion, saisissez **votre propre clé API OpenAI**,
   puis cliquez sur **Commencer**. La clé est masquée et conservée uniquement
   en mémoire pendant cette session ; elle doit être saisie à nouveau au prochain
   lancement. Ne collez jamais votre clé dans la conversation elle-même.
2. Écrivez un message, puis cliquez sur **Envoyer**. Jade répond par texte et
   sa voix est jouée sur la sortie audio du PC. Sa bouche suit approximativement
   l'intensité de la voix : il ne s'agit pas d'une synchronisation phonétique.
   Si les mots fournis par la transcription de la voix diffèrent de la réponse
   écrite, la ligne « Jade (voix) » montre ce qui a été généré pour la voix.
3. Pour parler au micro, cliquez sur **Parler (3 s)**, puis parlez pendant la
   capture. Aucun microphone n'est activé avant ce clic. L'audio est envoyé à
   OpenAI pour transcription, puis une réponse est générée.
4. **Arrêter** interrompt la demande en cours lorsque le service ou le pilote
   le permet. Fermez le panneau pour fermer également la fenêtre du modèle.

Pour changer le visage, choisissez une expression dans la liste puis cliquez
sur **Expression**. Le choix **Neutre** remet le visage au repos. L'animation
d'attente, le souffle et les clignements se jouent automatiquement.

Les messages et l'audio des demandes sont transmis à OpenAI pour fournir les
réponses. L'application ne les enregistre pas volontairement dans un fichier ;
consultez les conditions et paramètres de votre compte OpenAI pour le traitement
par le service. Une requête commencée peut être facturée même si elle est arrêtée.

## À savoir

- La démo utilise le modèle Live2D **r20**. Le modèle r21 plus récent est encore
  en cours de travail et n'est pas présenté comme une version animée finalisée.
- Un pilote graphique compatible OpenGL et un périphérique audio fonctionnel
  sont nécessaires. Le microphone est facultatif pour le dialogue écrit.
- Le programme n'active pas automatiquement Twitch, Discord, une caméra ou un
  autre compte. Cette démo locale ne remplace pas leur configuration complète.
- Cette démo utilise `gpt-6-luna` pour le dialogue, `gpt-transcribe` pour la
  transcription et `gpt-realtime-2.1-mini` pour la voix. Les modèles utilisés par
  le runtime principal du projet sont configurés séparément et nécessitent leur
  propre migration. En cas d'échec, vérifiez votre clé, le crédit API, Internet,
  les périphériques et l'accès de votre compte aux modèles de la démo.
- Utilisez **Applications installées** dans Windows pour désinstaller Jade. La clé
  saisie pour la démo n'est pas stockée par l'application pour les sessions suivantes.
