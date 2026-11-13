# Réduire la latence de Jade — relais Astra → Terra

**État : documentation prête, développement à reprendre sous Terra.** Travailler
sur `develop`, sans fusion automatique vers `main`. Ne pas rouvrir les audits de
migration, la démo terminée, le rig r21 ou l'application mobile. Aux simples
relances avant le passage sous Terra, répondre seulement **« doc latence ok »**.

**Complément du 13 novembre :** le propriétaire souhaite la nouvelle voix
française Aube dès que possible, et un débit ×1,5. Disponibilité et mise en œuvre
documentées au lot A bis ; aucun changement vocal encore appliqué. Le fichier
garde la date du début du plan, pas celle d'une recette ultérieure.

## 1. Point de départ et clôture du correctif

- Le propriétaire confirme entendre les réponses de Jade sur Discord depuis son
  téléphone et avoir vu le modèle bouger localement. Le partage vidéo vers le
  téléphone reste volontairement différé. Cela ne valide pas encore la recette
  complète : arrêt pendant parole, reprise, changement de salon et synchronisation
  perçue restent à vérifier ensemble.
- Panne corrigée : `discord.py 2.7.1` attend l'ancienne API de transition MLS.
  Avec `davey 0.2.0`, les paquets arrivaient mais les clés de déchiffrement n'étaient
  pas installées. Le verrou est revenu à **davey 0.1.7**, puis la réponse réelle a
  été confirmée. Mettre à jour ces deux dépendances ensemble seulement après
  vérification de leur contrat. La rupture est décrite dans les
  [notes officielles davey](https://github.com/Snazzah/davey/releases/tag/py-0.2.0).
- Validation du correctif : **330 tests hors ligne réussis**, compilation et
  `pip check` réussis ; verrou Poetry régénéré et cohérent. Ces contrôles ne
  remplacent pas l'essai réel confirmé par le propriétaire.
- Photo Discord : nouveau [portrait r21](../../assets/branding/README.md) appliqué
  au bot et confirmé par relecture API. Le modèle animé du MVP demeure r20.
- Au contrôle de clôture, le processus temporaire de diagnostic Jade n'est plus
  actif. Aucun nouvel appel vocal payant ni essai téléphone n'est lancé. VTube
  Studio reste ouvert ; les autres services ne sont pas modifiés.
- **Point visuel à reprendre avec le propriétaire :** VTube Studio est installé
  avec le package r20, mais `--avatar` est la fenêtre autonome effectivement
  essayée. La configuration active n'active pas VTS et ne contient pas son jeton.
  Le compte Discord PC demandait une reconnexion lors du dernier contrôle : il
  doit partager la fenêtre, le bot ne réalise pas ce partage. Le
  [guide avatar](UTILISATION-AVATAR-DISCORD.md) distingue ces parcours. Ne pas
  annoncer que le rendu VTS ou le partage téléphone sont validés.

## 2. Diagnostic utile, sans chiffres inventés

Références au code du correctif, repères par fonction pour résister aux décalages
de lignes. Les délais réseau, de modèle et du téléphone n'ont pas été chronométrés
ensemble. Les anciens essais synthétiques séparés consignés dans `TASKS.md`
(texte 2,20 s, voix 4,80 s, STT 0,83 s) ne sont pas une mesure de conversation.

| Étape actuelle | Source | Effet sur l'attente |
| --- | --- | --- |
| Clôture après 700 ms de silence, polling 100 ms | `voice_turns.py:PcmTurnSegmenter`, `discord_voice.py:_poll_turns` | Délai fixe avant transcription, plus quantification du polling |
| STT sur WAV terminé | `discord_voice.py:_consume`, `openai_services.py:transcribe_wav` | Pas de transcription progressive pendant la parole |
| LLM complet avant TTS | `openai_services.py:complete`, `dialogue.py:respond` | Attente du dernier token pour commencer la voix |
| Connexion TTS neuve à chaque réponse | `realtime_tts.py:RealtimeTTS.synthesize` | Connexion et configuration sur le chemin critique |
| Tous les deltas audio accumulés jusqu'à `response.done` | `realtime_tts.py:_request` | « Realtime » ne signifie pas encore lecture progressive dans Jade |
| WAV temporaire puis FFmpeg | `output.py:SpeechOutput`, `discord_voice.py:play` | Lecture seulement après disponibilité de tout l'audio |
| Worker global attend la lecture entière | `orchestrator.py:Runtime` | Les tours suivants et autres sources peuvent rester en file |

Le principal levier est d'**entendre le début pendant que la suite est encore
produite**. Baisser le silence de 700 à 500 ms économise environ 200 ms ; cela ne
supprime pas l'attente de générations complètes. La cible technique devient :

```text
Aujourd'hui : fin parole → silence → STT complet → texte complet → audio complet → lecture
Cible       : fin parole → silence → STT complet → première phrase → premiers PCM → lecture
                                                          suite du texte/TTS en parallèle ↗
```

Les envois de texte avant audio dans `main.py:on_reply` concernent Twitch et
Discord texte ; la source `discord_voice` les saute. Une hotkey VTS peut en
revanche ajouter une attente si activée. Ce sont des optimisations secondaires.

## 3. Ordre d'exécution sous Terra

### A — Quelques mesures pour choisir et comparer

1. Ajouter aux points existants une horloge monotone et un numéro local de tour,
   sans identifiant utilisateur, transcription ni contenu de réponse. Relever :
   dernière trame vocale, clôture de tour, début/fin STT, entrée/sortie de file,
   début/premier token/fin LLM, connexion TTS, premier PCM reçu, première trame
   non silencieuse fournie à Discord, fin de lecture. Pour le code actuel,
   « premier token » sera simplement indisponible tant que le flux n'existe pas.
2. Distinguer durée de service et attente de file. La trame fournie au lecteur
   n'est pas encore le son arrivé à l'oreille du téléphone.
3. À la prochaine recette, prendre 5 à 10 phrases courtes, longues et avec une
   pause naturelle. Comparer les mêmes cas avant/après, médiane et étendue,
   premier tour et suivants séparés. Aucun percentile prétendument fiable avec
   un si petit échantillon, aucun tableau de bord ou service de télémétrie.

**Livrable :** petit relevé local et causes dominantes, pas une nouvelle campagne
de benchmark. Ne pas consommer d'appels pour mesurer tant que le propriétaire
n'est pas revenu pour la recette différée.

### A bis — Nouvelle voix française et vitesse ×1,5 en priorité

**Disponibilité vérifiée le 13 novembre 2026 dans les sources officielles :**

| Demande | Ce qui est établi | Décision de mise en œuvre |
| --- | --- | --- |
| Aube | Voix française proposée dans [ChatGPT Live](https://help.openai.com/fr-fr/articles/20001274-chatgpt-voice), pas dans les voix intégrées documentées de Realtime/Speech API | Ne pas configurer `aube` en supposant sa compatibilité ; aucun identifiant API ou alias confirmé à ce jour dans les pages consultées |
| Voix française dans l'API Live | [Brise (`brise`), féminine, et Sillage (`sillage`), masculine](https://developers.openai.com/api/docs/guides/live-conversations#voice-options) | Brise est une candidate à écouter si Aube n'est pas exposée ; aucune équivalence Aube = Brise établie, et Live est un autre transport |
| Vitesse ×1,5 dans Realtime | `session.audio.output.speed` accepte 0,25 à 1,5 ; changement entre réponses | Implémentable sans attendre une nouvelle voix ; vérifier la confirmation et la qualité à l'écoute |

La [référence Realtime](https://developers.openai.com/api/reference/resources/realtime/client-events)
décrit ce réglage comme un traitement de l'audio après génération. Accélérer
réduit la durée de parole, pas nécessairement l'attente avant le premier son.
Ne pas promettre une économie proportionnelle sur la génération ou la facture.

1. Après la mesure initiale A, ajouter `JADE_TTS_SPEED` à `Settings` et à son
   chargement/validation : valeur finie, plage commune 0,25–1,5, réglage souhaité
   1,5 pour Jade et retour à 1,0 possible. Documenter le défaut choisi ; conserver
   le timbre actuel tant que la nouvelle voix n'est pas réellement disponible.
2. Faire passer la vitesse dans `OpenAIServices.synthesize_speech` puis
   `RealtimeTTS.__init__/_request`, sous `session.audio.output`. Vérifier le
   réglage de `session.updated`. L'ancien chemin Speech API impose aujourd'hui
   `speed=1.1` : remplacer ce nombre par la même configuration, sans accélération
   additionnelle dans FFmpeg/le lecteur. Ne jamais accélérer le STT.
3. La démo réexporte le même transport, mais `demo/reelle/session.py:DemoSession`
   le construit directement avec `coral`. Propager aussi le réglage public de
   débit à ce point, sans charger les secrets privés du développeur dans la
   démo. Compléter `.env.example` et, si utilisé dans un profil, les listes de
   clés publiques de `src/utility/public_profile.py` et `tools/jade_ci_preflight.py`.
4. Adapter les tests existants `test_demo_realtime_tts.py`,
   `test_jade_runtime_realtime.py` et `test_demo_reelle_session.py` : paramètre
   transmis/confirmé, valeur invalide, compatibilité des appelants. Aucun appel
   réel nécessaire à ces tests. À la recette, écouter une phrase à 1,0 puis 1,5,
   vérifier intelligibilité française, absence de double accélération et bouche
   pilotée par le PCM réellement joué ; conserver le choix du propriétaire.
5. À la reprise Terra, revérifier une fois la disponibilité officielle d'Aube.
   Si son identifiant est désormais supporté par le modèle/transport choisi,
   effectuer un essai court, puis configurer `JADE_TTS_VOICE` et la démo. Une
   session Realtime déjà utilisée doit être recréée pour changer de voix.
6. Si Aube reste propre à ChatGPT, poursuivre vitesse et latence sans bloquer
   tout le lot. Présenter cette limite et la candidate Brise au propriétaire ;
   ne pas remplacer silencieusement Aube, utiliser son compte ChatGPT comme
   serveur TTS, ni migrer tout le dialogue vers Live pour un simple changement
   de nom. La migration éventuelle reste l'option distincte du §5. Les pages
   Live doivent être vérifiées séparément pour le débit ; ne pas leur attribuer
   automatiquement le schéma `speed` de Realtime.

**Terminé quand :** ×1,5 réellement appliqué une seule fois et voix sélectionnée
identifiée honnêtement. Une indisponibilité d'Aube doit rester visible dans
`TASKS.md`, avec le choix conservé en attente ; ce n'est pas un succès de changement
de timbre. Aucun sondage payant ou suivi périodique de catalogue n'est nécessaire.

### B — Lire le TTS dès ses premiers blocs (gain principal)

1. Faire évoluer `RealtimeTTS` et `OpenAIServices` avec un flux asynchrone PCM,
   métadonnées de format et terminaison/erreur explicites. Garder l'adaptateur
   WAV pour la démo et les sorties qui l'exigent ; partager le décodage existant.
2. Consommer les événements `response.output_audio.delta` au lieu d'attendre
   `response.done` pour rendre l'audio disponible. Ce dernier reste nécessaire
   pour connaître le succès final. L'API documente bien ces
   [deltas audio en WebSocket](https://developers.openai.com/api/docs/guides/realtime-conversations#handling-audio-output-with-websockets).
3. Ajouter une source Discord progressive : PCM 48 kHz, stéréo, 16 bits,
   trames de 20 ms (3 840 octets). Convertir le PCM 24 kHz mono avec un
   rééchantillonnage **continu**, pas une remise à zéro entre chaque delta.
   Un FFmpeg alimenté par pipe ou un convertisseur existant suffit ; ne pas
   ajouter un moteur audio complet.
4. Utiliser une passerelle bornée entre boucle async et thread `AudioSource.read`.
   Ne pas partager directement une `asyncio.Queue` avec ce thread. Prébuffer
   initial proposé : 100–200 ms, à ajuster à l'écoute. File momentanément vide :
   fournir un silence de 20 ms ; renvoyer `b''` seulement à la vraie fin. Borner
   durée de sous-alimentation et taille totale avec les délais/limites existants.
   Distinguer attente du service et durée de lecture : une file pleine ou un
   `yield` ralenti par la consommation ne doit pas épuiser le timeout API de
   synthèse. Conserver un délai d'absence de progrès et l'échéance globale plus
   longue de la sortie ; ne pas supprimer l'annulation pour éviter ce problème.
5. Un producteur TTS alimente les sorties actives ; ne pas dupliquer les appels
   OpenAI pour Discord et la sortie locale. Garder `JADE_AUDIO_OUTPUT=none` pour
   le parcours téléphone afin d'éviter le doublon sonore.
6. Déclencher la bouche depuis les trames effectivement consommées par le lecteur,
   avec communication vers l'avatar hors du thread audio. La production en avance
   ne doit pas faire bouger les lèvres en avance. Repos sur fin, arrêt et erreur.
7. Après le premier son émis, une erreur ne doit pas relancer la réponse entière.
   Arrêter le flux et signaler l'échec sans répétition. Préserver la réponse texte.

**Point de contrat à ne pas manquer :** `RealtimeTTS` peut vérifier le transcript
à la fin. Le runtime principal désactive déjà cette comparaison stricte ; un
appelant qui l'exige doit garder le chemin intégralement tamponné. On ne peut pas
garantir une validation complète avant lecture tout en diffusant les premiers
blocs. Ne pas changer silencieusement le comportement de la démo.
La comparaison désactivée ne supprime ni transcript final non vide, ni statut
`completed`, ni corrélation des événements. Les sous-titres utilisent actuellement
ce transcript final : dès B, les différer ou identifier un affichage provisoire,
sans présenter le texte demandé comme déjà confirmé par la synthèse.

**Terminé quand :** les premiers sons arrivent avant la fin de synthèse, sans
troncature, arrêt prématuré en cas de petit trou réseau, double voix ou bouche en
avance. Mesurer le gain obtenu ; aucune promesse en secondes avant ce constat.

### C — Réutiliser la connexion vocale

1. Après stabilisation de B, faire posséder un transport TTS durable à
   `OpenAIServices`, au lieu de créer `RealtimeTTS` pour chaque réponse.
2. Sérialiser les réponses sur la connexion, garder la conversation TTS isolée
   du dialogue (`conversation: none`) et corréler les événements par réponse.
   Les événements tardifs d'une réponse annulée ne doivent jamais alimenter
   la suivante.
3. Annuler la réponse courante, vider son tampon puis attendre la terminaison
   attendue ; fermer/recréer la connexion si son état devient ambigu. Fermer
   normalement à l'arrêt du runtime, reconstruire si le modèle ou la voix change.
4. Reconnecter après panne/expiration avec les délais existants. Aucun appel de
   synthèse factice pour « chauffer » la session ; pas de retry payant illimité.

**Terminé quand :** deuxième réponse sans nouveau handshake en fonctionnement
normal, puis annulation/reconnexion sans ancien son. Le gain est le temps de
connexion/configuration évité, à relever séparément.

### D — Commencer la voix avant la fin du texte

1. Étendre le contrat `ChatBackend` avec une capacité de streaming optionnelle,
   garder `complete` comme repli pour les backends existants et hors ligne.
   Exposer les deltas de texte depuis le fournisseur déjà configuré.
2. Constituer des phrases ou propositions parlables ; traiter ponctuation,
   abréviations, nombres et dernier fragment. Ne pas synthétiser chaque token.
   Première proposition courte, puis blocs plus longs pour préserver la prosodie.
3. Pour Realtime, envoyer chaque bloc par une requête TTS prise en charge ; ne
   pas supposer qu'on peut ajouter du texte à une réponse audio déjà lancée.
   Conserver une synthèse à la fois, et limiter l'avance à un ou deux blocs.
4. Adapter ensemble `Dialogue.respond`, `Runtime` et `SpeechOutput` pour que le
   premier bloc puisse parvenir au lecteur avant la réponse complète. Garder
   l'ordre d'une même session, la réponse texte complète une seule fois et le
   contrat HTTP existant. Pas besoin d'une refonte générale multiworkers.
5. Distinguer texte généré, texte livré et partie prononcée. Aujourd'hui
   `Dialogue.respond` mémorise la réponse entière avant lecture : après une
   interruption, ne pas traiter la fin jamais jouée comme entendue. Mettre à jour
   l'historique une seule fois ; les sous-titres suivent le bloc joué, puis
   s'effacent à l'arrêt. En cas de coupure au milieu d'un bloc, indiquer la coupure
   sans prétendre disposer d'un alignement mot/temps exact.
6. Comparer coût, continuité du timbre et répétitions sur les mêmes phrases. Si
   les requêtes par petits blocs dégradent ces points, augmenter leur taille ou
   revenir à B+C ; ne pas empiler un deuxième pipeline coûteux.

**Terminé quand :** une réponse longue commence avant son dernier token, avec
texte/historique cohérents et une seule voix audible.

### E — Ajustements seulement après ces gains

- Essayer 450–500 ms de silence au lieu de 700 ms, avec phrases françaises
  hésitantes. Conserver 700 ms comme repli si les tours sont coupés ; ne pas
  confondre ce VAD local avec le VAD du serveur OpenAI.
- Demander des réponses orales naturelles et courtes par défaut. Ne pas baisser
  brutalement le plafond de tokens : une phrase tronquée n'est pas plus utile.
- Garder les modèles actuellement configurés pour isoler l'effet du streaming.
  Ne comparer un autre modèle qu'en présence d'un temps LLM encore dominant.
- Ne sortir la lecture du worker global que si le relevé montre une attente
  intersources gênante ; préserver ordre, échéances et exclusivité de la voix.
- STT streaming ensuite seulement si sa durée résiduelle le justifie : garder
  les identités de tours, aucun dialogue sur transcript provisoire, pas une
  session facturée en permanence par participant. Vérifier la compatibilité du
  modèle avant d'ajouter du VAD serveur. Les
  [réglages officiels VAD](https://developers.openai.com/api/docs/guides/realtime-vad)
  dépendent du mode/modèle ; `semantic_vad` n'est pas une garantie de latence
  inférieure. Aucun deuxième détecteur de fin de tour concurrent sans besoin.

## 4. Ce qui doit rester correct à chaque lot

- Préserver `generation`, `session_id`, `audio_epoch`, l'échéance et l'annulation :
  annuler producteurs et lecteur, purger le PCM et fermer les sous-processus
  correspondants sur arrêt, déplacement, reconnexion et extinction. Ces états
  évitent les vieux sons, ils ne réintroduisent aucune autorisation utilisateur.
- « Silence / arrête » reste accessible pendant la voix, puis « reprends ».
  Le mode silencieux couvre aussi les autres sources. Aujourd'hui, la parole
  pendant lecture passe au STT uniquement pour reconnaître un arrêt ; ce n'est
  pas encore une interruption conversationnelle libre. Ne pas la développer
  implicitement dans ce lot. Observer le coût STT et l'écho lors de la recette.
- Tous les participants et bots tiers restent admis ; seule la propre voix de
  Jade est exclue pour éviter la boucle. Pas de nouveau consentement, liste de
  salons ou filtre de participants.
- Garder STT/TTS OpenAI et dialogue interchangeable, les extras facultatifs,
  l'usage texte et la démo hors ligne. Aucun secret, enregistrement ou transcript
  dans le dépôt ou dans les nouvelles mesures.

## 5. Alternative à fort potentiel, sans décision de développement

Une session Realtime **audio → audio** persistante supprimerait les trois appels
séquentiels STT → dialogue → TTS. Le potentiel est supérieur à quelques réglages
de silence, mais elle couplerait la conversation au fournisseur vocal et impose
de reprendre historique, pertinence, interruptions et autres sources. C'est une
option produit distincte à décider si B–E ne suffisent pas, pas le plan par défaut.
Le principe audio natif et les flux sont décrits dans les
[conversations Realtime](https://developers.openai.com/api/docs/guides/realtime-conversations).

Le plan retenu applique d'abord streaming, traitement par blocs et réduction des
attentes successives, cohérents avec le
[guide officiel OpenAI de latence](https://developers.openai.com/api/docs/guides/latency-optimization).
Les gains et le coût sur Jade restent à mesurer ; ne pas reprendre les chiffres
génériques du fournisseur comme une garantie pour Discord sur téléphone.

## 6. Validation et livraison sans surenchère

Adapter les tests déjà présents de TTS/sortie/Discord pour couvrir seulement les
nouveaux risques : première lecture avant terminaison, trou temporaire distinct
de fin, annulation sans vieux son, erreur après première émission, repli WAV.
Compléter pour D le cas texte/historique après interruption. Éviter les tests qui
recopient l'implémentation et les batteries redondantes.

À la prochaine recette avec le propriétaire : quelques phrases identiques
avant/après, pause naturelle, arrêt en synthèse puis lecture, reprise,
reconnexion et deux origines sans chevauchement. Vérifier bouche/son et terminer
le partage écran téléphone différé. Consigner observations et limites dans
`TASKS.md`. Pas de session d'écoute ou de diagnostic laissée active sans usage.

Par lot cohérent : tests ciblés pendant le développement ; suite existante et
compilation sur le code final ; contrôles GitHub habituels si disponibles, sinon
résultats locaux et CI indisponible clairement indiqués. Commit/push `develop`,
documents à jour, aucune fusion `main` automatique.

**Contre-lecture des métiers :** audio — début rapide sans hachures ni décalage ;
développement — interfaces compatibles et annulation avant parallélisme ;
qualité — preuve sur téléphone distincte des mocks ; utilisateur — moins
d'attente sans couper ses phrases ; utilisateur payant de Codex — B puis C avant
les changements plus chers, une mesure utile, pas de refonte ou d'audit répété.
