# Passage de relais : participation écrite de Jade sur Discord (13 novembre 2026)

## Demande

L'utilisateur confirme que le chantier vocal GPT-6 a été intégré et demande une branche
isolée pour que Jade **lise les salons écrits de son serveur Discord et réponde par écrit
quand c'est pertinent, en complément de son fonctionnement oral**.

Le 13 novembre, la PR #1 du streaming vocal était fusionnée dans `develop`, pas
dans `main`. La nouvelle branche part du commit `4cd82a0` de `develop`.
Aucune modification de production ou des fichiers privés.

## Ajustements demandés ensuite

- Probabilité de participation spontanée portée à **30 %**. L'ancien
  pourcentage de 15 % ne s'applique plus, sauf si un fichier privé définit
  explicitement `JADE_DISCORD_TEXT_AUTO_RATE` avec une autre valeur.
- `prompt_chat.txt` : Goldaj est le père de Jade dans son univers de VTuber.
  Affection occasionnelle, timide et discrète. « papa » peut être utilisé
  parfois, sans répétition et seulement pour Goldaj.
- Le chargement d'un prompt externe via `JADE_PROMPT_FILE` ou
  `JADE_ASSETS_ROOT` reste prioritaire et inchangé. Si Jade utilise un tel
  fichier privé, y reporter la même relation pour qu'elle soit active.

## Comportement développé

- Le connecteur `--discord` reste le point d'entrée unique : un seul `discord.py`
  pour les messages et l'option vocale. Pas de second bot ni de second jeton.
- Jade lit le texte des salons accessibles à son compte, tout en ignorant ses
  propres messages. Les autres bots peuvent s'adresser explicitement à elle.
- Réponse directe aux mentions `@Jade` (ID réel Discord ou nom entier), réponses
  à un message de Jade, messages privés et commandes `!response`/`!rsp`.
- Après une réponse effectivement envoyée, relance du **même auteur** pendant
  90 secondes pour ses questions ou enchaînements textuels évidents.
- Participation spontanée sur une question publique : **30 % de chance**,
  maximum une sélection non sollicitée par salon toutes les 180 secondes.
  Pour supprimer complètement les interventions spontanées : définir
  `JADE_DISCORD_TEXT_AUTO_RATE=0`. Les bots ne déclenchent pas ce mode.
- Contexte passif en mémoire **uniquement**, six extraits courts au maximum,
  isolés par salon, supprimés après inactivité ou redémarrage. Aucun appel OpenAI
  pour les messages ignorés ; aucun enregistrement des discussions sur disque.
- Les réponses à un message écrit sont envoyées **par écrit**. La correction
  Terra conserve également la diffusion vocale antérieure lorsque la voix et un
  salon vocal sont actifs ; la hotkey VTube Studio configurée est conservée.
  Sans destination vocale active, la réponse écrite reste disponible.
- Envoi Discord avec mentions désactivées, fractionnement des textes longs
  (jusqu'à quatre messages) et abandon propre si le canal n'est pas en cache.
- Les messages de plus de 1 200 caractères ne déclenchent pas de génération.

Il s'agit d'un **filtre heuristique**, pas d'un jugement de pertinence du LLM.
La limite de coût et le rythme des interventions sont configurables.

## Paramètres privés

```dotenv
DISCORD_TOKEN=...                          # déjà configuré en privé
JADE_DISCORD_TEXT_AUTO_RATE=0.30          # 0 = réponses uniquement sollicitées
JADE_DISCORD_TEXT_COOLDOWN_SECONDS=180   # entre 30 et 3600
```

Ces paramètres sont optionnels ; les valeurs par défaut sont incluses dans le
code. Ne pas copier de jeton réel dans ce dépôt public.

## Commandes de recette (depuis l'environnement local de Jade)

- Texte seul : `python main.py --live --discord`
- Texte + voix : reprendre le lancement vocal déjà validé et conserver
  `--discord` ; ne pas démarrer un second processus Discord avec le même jeton.
- Dans le portail développeur Discord : le **Message Content Intent** doit
  être activé. Vérifier les droits View Channel, Read Message History et
  Send Messages dans les salons concernés.

## Scénarios à vérifier en réel

1. Une discussion normale sans adresse à Jade n'entraîne pas une réponse à
   chaque message.
2. `@Jade, tu peux expliquer ?` répond par écrit ; si la diffusion vocale est
   active, vérifier qu'elle peut aussi être entendue dans le salon vocal.
3. Une réponse à un message écrit de Jade est reconnue, y compris sans son nom.
4. Une relance du même auteur fonctionne pendant 90 s après un envoi réussi ;
   une relance d'un autre auteur n'hérite pas de cette fenêtre.
5. Les salons gardent des contextes distincts, y compris si deux utilisateurs
   parlent en parallèle ; une reconnexion du bot ne recopie pas les anciens textes.
6. Les messages contenant des mentions ne notifient personne dans les réponses.
7. Discord écrit et Discord vocal coexistent pendant la recette téléphone.

## Contrôles et limites

- Exécuter `python -m compileall -q src main.py` et
  `python -m unittest discover -s tests -v`, puis vérifier les contrôles du
  **dernier SHA** de la PR. Les tests automatiques sont hors ligne.
- Une recette sur le serveur Discord réel et l'écoute sur téléphone sont encore
  à faire après intégration. Aucun appel facturé / message Discord réel n'est
  déclaré validé par cette branche.
- La mémoire du salon est volontairement éphémère ; elle n'est pas une archive.
- La réponse spontanée est probabiliste. Pour un comportement plus fin, mesurer
  d'abord ses interventions dans le vrai serveur plutôt qu'ajouter immédiatement
  un second appel de classification LLM par message.
