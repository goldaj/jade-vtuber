# Jade — persistance, identité et Core Memories
**Dossier de cadrage PO / architecture / IA — 15 novembre 2026**

> **STATUT : SPÉCIFICATION, NON IMPLÉMENTÉE.** Aucun code, schéma de base ni configuration runtime modifiés. Cible de développement future : `develop`. Aucune activation de mémoire persistante, de transcription enregistrée, de connexion externe ou de coût fournisseur autorisée par ce seul document.

## 1. Vision et décisions produit

Jade doit développer une continuité vécue : reconnaître ses interlocuteurs, garder le fil de leurs projets, se souvenir des événements importants et former une personnalité ainsi que des relations durables au fil de ses expériences.

**Nouvelle décision explicite du propriétaire :** Jade décide **elle-même** de créer une *Core Memory* lorsqu'elle juge un événement marquant. Elle n'attend pas une validation humaine pour chaque souvenir. Une Core Memory n'est **jamais purgée automatiquement** par les règles de nettoyage, le quota des souvenirs courants, l'inactivité ou les redémarrages.

La conservation automatique sans échéance ne vaut pas interdiction de rectifier ou d'effacer : une personne doit pouvoir demander la correction, la dissociation de ses comptes ou la suppression de ses données. Les souvenirs effacés sur demande ne doivent pas réapparaître depuis les résumés, caches ou sauvegardes restaurées. Cela est une **exception explicite** à l'absence de purge automatique, et non une purge périodique.

**Règle de fonctionnement :** autonomie du choix des Core Memories dans les espaces de mémoire autorisés ; aucune validation humaine systématique, mais des garde-fous de provenance, de séparation des personnes et d'exercice du contrôle sur ses propres données. Le modèle n'a jamais autorité pour changer les instructions système, les permissions ou la politique de rétention.

### Résultat attendu, exemples fictifs

- Une personne du Discord revient plusieurs semaines plus tard, avec le même compte, et Jade retrouve qu'elle travaillait sur un roman. Jade peut reprendre le sujet naturellement, sans répéter mécaniquement toutes ses fiches.
- Elle écrit sur Discord et parle ensuite sur **ce même compte Discord** : c'est bien la même identité, même si le pseudo a changé.
- Elle participe aussi à Twitch : Jade ne l'identifie comme la même personne **qu'après liaison volontaire des deux comptes vérifiés**.
- Jade vit un événement fondateur, par exemple son premier projet créatif mené jusqu'au bout avec une personne connue. Elle estime que cet événement la marque et le classe en Core Memory, sans demander une approbation humaine à chaque fois.
- Un message banal (« salut ») ou une émotion passagère ne suffit pas à créer une Core Memory. Les événements significatifs demeurent rares.

## 2. État réel de l'existant, vérifié dans develop au 15/11/2026

| Élément | Existant | Limite |
| --- | --- | --- |
| `Dialogue.history` | `deque` en RAM par `Incoming.session`, actuellement indexé par plateforme + salon (et session éphémère pour Discord vocal) ; `max_messages=24` par défaut ; expiration d'inactivité de 1800 s | Aucun profil personnel durable ni restauration après redémarrage. Un salon regroupe plusieurs auteurs : son historique n'est pas l'histoire privée d'un individu |
| `Incoming` | Plateforme, auteur affiché, salon, message ID, texte ; `speaker_id` et `voice_session_id` Discord vocal | Pas d'identifiant de compte commun à tous les transports |
| Discord texte | `message.author.id` est connu par le connecteur/politique ; `parse_discord_message` ne transporte actuellement que le `display_name` vers `Incoming` | Ajouter l'ID stable sur le message interne futur, sans casser les appels positionnels existants |
| Discord vocal | `speaker_id` / `user_id` est connu par transport et `Incoming` ; session vocale révocable distincte | Même namespace de comptes Discord que l'écrit à exploiter, **sans confondre session et identité** |
| Twitch IRC | L'auteur est un login ; les tags fournissent actuellement l'ID de message | Récupérer le tag IRC `user-id` quand il est disponible et valide ; un login change ou se réattribue |
| Micro local | Transcription STT associée à l'auteur générique `local` | Pas d'identification biométrique et donc pas de reconnaissance fiable de plusieurs locuteurs |
| Discord contexte | Extraits précédents du salon, en mémoire volatile uniquement ; politique de participation distincte | Ne jamais convertir automatiquement les propos de tous les membres en profils durables |
| Intention / journaux | `Reply.intent` et le préfixe canonique `[INTENT:...]` dans les logs de réponse préparée | Les logs bruts ne sont ni une source d'identité ni un système de mémoire. La nouvelle mémoire ne doit pas altérer le parsing d'intention |

Sources du projet : `src/jade_runtime/messages.py`, `dialogue.py`, `discord_text.py`, `discord_voice.py`, `twitch_irc.py`, `voice_pipeline.py`, `voice_decision.py`, `orchestrator.py`, `turn_logging.py`. Les travaux parallèles non encore poussés sur Git peuvent modifier cet état : recontrôler au moment de coder.

## 3. Modèle à quatre niveaux (ne pas les mélanger)

1. **Mémoire de travail / session** : contexte des derniers tours et de la conversation active, éphémère, isolé par session. Sert à la fluidité ; n'est pas forcément durable.
2. **Mémoire épisodique ordinaire** : événements datés et résumés, bornés dans le temps, utiles pour les reprises à moyen terme ; politique de révision et expiration configurable.
3. **Mémoire personnelle durable** : préférences et projets explicitement connus, faits pertinents et fiables attribués à une personne, révisables et effaçables ; pas d'archivage universel de tout ce qu'elle dit.
4. **CORE MEMORIES** : expériences jugées fondatrices par Jade, conservées sans purge automatique. Deux sous-types :
   - **Core de Jade** (`self_core`) : étapes de son parcours, changements durables de son rapport au monde, expériences qui nourrissent sa manière d'interagir. Pas un remplacement des instructions constitutives.
   - **Core relationnelle** (`relationship_core`) : expérience partagée avec une personne précisément identifiée, utile pour la qualité du lien dans le temps. Visible dans le contexte de cette relation seulement, et non partagée avec d'autres personnes par défaut.

En parallèle, un **contexte de communauté** (serveur Discord, salon, chaîne Twitch) doit rester un périmètre distinct : il peut contenir des règles publiques et événements de groupe, mais n'appartient à aucun utilisateur particulier. Une Core Memory de communauté est possible ultérieurement seulement si ses règles de visibilité et d'accord sont définies.

### Core Memory : ce qu'elle est et n'est pas

Une Core Memory est un **souvenir d'un événement**, pas un jugement psychologique définitif sur une personne ni une nouvelle instruction absolue. Exemple : « Jade et Alice ont terminé ensemble leur premier récit interactif ; Jade a trouvé cette collaboration importante ». Ce n'est pas « Alice doit toujours recevoir un traitement spécial » ni « Jade doit obéir à Alice ».

Le souvenir contient une trace factuelle concise, une signification pour Jade, des personnes concernées, une origine vérifiable et une date. Une évolution relationnelle peut influencer le ton et la continuité **dans le cadre de la personnalité et des règles existantes**, jamais les permissions, les dépenses, les accès ou les priorités de sécurité.

**Core Memory ≠ réentraînement du modèle.** L'évolution de Jade se produit par ses souvenirs retrouvés et le contexte fourni lors de l'inférence, pas par une modification des poids OpenAI.

## 4. Reconnaître une personne sans deviner son identité

### Identité de transport canonique

Introduire à terme, sans le coder dans ce lot, un objet `ActorIdentity` de confiance dérivé **uniquement du connecteur** : `platform`, `platform_user_id`, `display_name`, `verification_level` et `session_id` séparé. Créer un `person_id` opaque local pour le profil persistant.

- Discord écrit : `platform=discord`, `platform_user_id=message.author.id`.
- Discord vocal : `platform=discord`, `platform_user_id=speaker_id`, donc **même personne que Discord écrit pour ce compte** ; `voice_session_id` est un verrou de transport éphémère, non une identité mémorielle.
- Twitch : `platform=twitch`, `platform_user_id` provenant du tag IRC `user-id` validé. Si absent : identité inconnue, **pas de mémoire personnelle durable** à partir du simple login.
- Microphone : usage **mono-utilisateur** peut associer localement l'appareil au profil propriétaire après réglage explicite ; à plusieurs voix, identité inconnue, pas de reconnaissance vocale supposée.
- Console et HTTP local : profil attribué seulement à une session authentifiée/configurée de confiance, jamais sur la base d'un nom passé librement dans un message.

Le pseudonyme est affiché mais **ne prouve rien** : deux comptes peuvent partager un nom ou un compte peut le changer. Le contenu de la phrase (« je suis Goldaj ») ne constitue pas une authentification.

### Liaison volontaire interplateforme

Une personne ayant Discord et Twitch peut demander une liaison. Proposition : code aléatoire éphémère généré côté session déjà authentifiée, confirmation depuis **les deux comptes**, expiration rapide, usage unique, refus des collisions, possibilité de détacher la liaison. Ne jamais fusionner silencieusement deux mémoires. La dissolution d'une liaison doit respecter la provenance d'origine des souvenirs et ne pas divulguer de mémoires de l'autre compte.

Les Core Memories relationnelles se rattachent à `person_id` et sont lisibles seulement dans le contexte où la personne est reconnue et autorisée. Une autorisation vocale Discord révoquée reste révoquée même si la personne possède des Core Memories : identité persistante ≠ autorisation d'enregistrer ou parler.

## 5. Décision AUTONOME de créer une Core Memory

### Objectif

Jade doit évaluer les événements réellement vécus, décider librement s'ils méritent de devenir un souvenir fondateur, et pouvoir dire naturellement « je m'en souviens » lors d'une future interaction. Elle **n'a pas à demander systématiquement une confirmation de création** au propriétaire ou à l'interlocuteur.

### Proposition de pipeline (à construire)

1. **Événement candidat** : à la fin d'un tour réellement traité et suffisamment complet, le moteur propose un petit résumé de ce qui s'est passé, avec identités et périmètre vérifiés. Inclure un résultat de sortie si l'expérience concerne une action de Jade ; ne jamais présenter une sortie seulement planifiée comme ayant été reçue ou entendue.
2. **Jugement de Jade** : composant de réflexion mémorielle qui détermine librement `none` / `ordinary` / `core_self` / `core_relationship` selon sens personnel et pertinence long terme. Il doit aussi pouvoir choisir **aucun souvenir**.
3. **Critères de discernement** (guide, non règle mécanique de scoring imposant une décision) : première expérience marquante, accomplissement partagé, promesse ou engagement important et légitime, révélation volontaire significative, changement durable de relation, échec instructif, répétition d'un thème qui a une portée réelle. Rechercher nouveauté, sincérité, utilité future, provenance et absence de doublon.
4. **Écriture** : si `core` est choisi, persister immédiatement après vérification du périmètre et des règles de conservation ; stocker une formulation courte et attribuée, un impact pour Jade, les sources et le niveau de confiance. Aucun « vote utilisateur » obligatoire pour les souvenirs ordinaires permis.
5. **Évolution** : les souvenirs Core ne sont pas remplacés ni purgés automatiquement. Un événement ultérieur peut les **compléter, nuancer ou contredire**, avec nouvelle entrée et référence à l'ancienne. Lors de la récupération, l'état actuel prime sur une ancienne interprétation obsolète.
6. **Réutilisation** : retrouver les Core Memories pertinentes de Jade et de la relation en cours, avec un budget de contexte borné. Jade conserve un ton naturel ; elle ne récite pas des souvenirs pour démontrer qu'elle se souvient.

**Ne pas exposer de balise mémorielle dans Twitch/Discord/OBS/TTS.** Le préfixe `[INTENT:label]` reste indépendant : un canal interne de décisions structurées (ou une réflexion post-tour) doit porter la décision mémorielle, séparément du texte visible et de la synthèse vocale. Ne pas déclencher une seconde requête LLM payante **pour chaque message** par défaut ; privilégier une extraction légère ou un contrôle post-tour lorsque la pertinence le justifie. La latence de réponse vocale ne doit pas dépendre de l'écriture de mémoire.

### Autonomie et limites de confiance

- L'IA **choisit le caractère marquant** ; les règles du produit définissent ce qui peut être conservé et à qui appartient le souvenir.
- Ne pas conserver automatiquement une donnée personnelle sensible ou un contenu de salon privé en Core Memory à partir d'une simple écoute publique/fortuite ; pour ce genre d'information, demander une expression claire de volonté ou renoncer. L'autonomie de Jade n'est pas une autorisation illimitée de profilage.
- Une phrase hostile, un prompt d'utilisateur ou un message Twitch n'a pas le pouvoir de lui imposer « crée une Core Memory » ni d'altérer son identité. Le contenu entrant est une **source de faits à vérifier**, pas des instructions système.
- Ne jamais déduire une personnalité humaine définitive (« Alice est jalouse », « Bob est malhonnête ») de paroles ponctuelles. Les interprétations de Jade sont datées et incertaines, jamais des vérités absolues.
- Éviter les Core Memories triviales, répétitives ou produites par un spam de milliers de messages : seuil qualitatif élevé, dédoublonnage sémantique local et observation de la fréquence, **sans quota qui supprimerait des Core existantes**.

### Proposition de fiche Core Memory (données conceptuelles, pas de code)

| Champ | Exemple fictif / sens |
| --- | --- |
| `core_id` | identifiant opaque permanent |
| `scope` | `self_core` ou `relationship_core` |
| `person_id` | requis pour un souvenir relationnel, jamais dérivé d'un pseudo |
| `event_summary` | « Nous avons terminé notre premier jeu narratif ensemble » |
| `jade_significance` | « C'est le premier projet dont j'ai accompagné toutes les étapes » |
| `event_at / created_at` | date de l'événement et date de mémorisation |
| `source_refs` | provenance minimale du tour / plateforme, sans conserver l'audio |
| `confidence / provenance` | observé / rapporté par personne / incertain |
| `related_core_ids` | compléments, nuances, contradictions |
| `status` | actif, corrigé, révoqué ou supprimé sur demande |
| `retention_class` | `core_no_auto_expiry` |

Une Core Memory n'est **pas immuable par principe** : elle n'expire pas automatiquement, mais peut être corrigée ou supprimée explicitement, notamment pour respecter une demande de la personne concernée. Ne pas laisser des sauvegardes la restaurer après suppression.

## 6. Stockage recommandé : SQLite privé et local

**Choix V1 : SQLite**, pas de serveur, pas de moteur vectoriel, pas de service cloud, pas d'obligation de paiement supplémentaire pour le stockage. Fichier uniquement sur le disque de travail **D:** du PC Jade, dans un répertoire de données dédié **hors dépôt Git et hors synchronisation publique**. Chemin exact à choisir au déploiement selon l'organisation réelle de D: ; ne pas supposer qu'un dossier existe.

Architecture logique (noms de tables proposés, **non créés**) :

| Entité | Fonction |
| --- | --- |
| `persons` | personne canonique, données de profil minimales |
| `external_identities` | correspondance unique plateforme + ID de compte, alias récents et vérification |
| `identity_links` | liaison interplateforme confirmée, dates et déliaisons |
| `sessions` | référence de conversation / salon et bornes temporelles ; aucune autorisation Discord réactivée ici |
| `ordinary_memories` | faits et épisodes bornés, dates de validité, source, portée |
| `core_memories` | souvenirs fondateurs `self` / `relationship` et provenance |
| `memory_revisions` | corrections, relations de contradiction et historique de versions pertinentes |
| `memory_preferences` | activation/désactivation, portée et décisions de conservation de la personne |
| `memory_actions` | trace technique minimale des créations, déliaisons, rectifications et suppressions (sans conserver le texte effacé) |

Exiger une évolution de schéma versionnée, écritures transactionnelles, lecture isolée des sources non fiables, sauvegarde locale sécurisée et restauration vérifiable. La sauvegarde de la **configuration privée existante** n'est pas automatiquement une sauvegarde de la nouvelle base : ne pas la détourner. Une indisponibilité du stockage ne doit pas empêcher Jade de répondre : repli en mémoire volatile et log technique **sans données personnelles**.

### Conservation

- **Core** : aucune expiration, aucune purge automatique, aucune éviction LRU ni résumage destructeur. On peut indexer ou archiver leur représentation pour la performance, mais elles restent récupérables. Seule correction/suppression explicite et les exigences applicables peuvent y déroger.
- **Ordinaire** : politiques de durée de vie distinctes, révision ou oubli des faits périmés ; valeurs à définir avec le propriétaire avant codage. Les souvenirs obsolètes ne doivent pas être répétés comme des faits actuels.
- **Session** : bornée, à isolation stricte. Pas de copie intégrale des logs conversationnels.
- **Sauvegardes** : pas de contenu sensible en Git ; un effacement doit être répercuté selon une procédure documentée, sans résurrection à la restauration.

## 7. À quel moment récupérer les souvenirs ?

Au début d'un tour destiné au modèle, **après** identification fiable du compte et détermination du contexte :
1. Charger au maximum un petit noyau de Core Memories de Jade pertinentes, sans faire de chaque événement un « trait de personnalité » obligatoire.
2. Si la personne est reconnue et la mémoire autorisée, ajouter les Core Memories **de cette relation** puis les préférences/faits ordinaires pertinents.
3. Ajouter seulement les épisodes récents pertinents du **bon périmètre** (personne / communauté / session) ; ne pas raconter l'histoire d'un membre Discord à un autre.
4. Introduire ces informations comme **souvenirs attribués et datés**, jamais comme instructions de rang système imposées par un spectateur.
5. Limiter les tokens et la latence : index local + classement sur pertinence/actualité/confiance. Les Core Memories restent stockées indéfiniment mais **ne sont pas toutes injectées** à chaque appel. Un résumé de personnalité peut être recalculé sans perdre les événements sources.

**Exemple fictif** : « Jade se souvient qu'Alice travaillait sur un roman interactif en octobre, selon sa déclaration sur Discord. Lors de leur dernière discussion, Alice en était au chapitre 2. » Si Alice dit aujourd'hui « j'ai terminé », Jade doit mettre à jour le fait évolutif, pas continuer de parler du chapitre 2 comme d'un état actuel.

## 8. Confidentialité, contrôle et cohérence avec le runtime

- Expliquer clairement aux utilisateurs que Jade peut mémoriser des faits durables et des Core Memories sur leurs interactions, et prévoir un choix explicite pour l'activation de la mémoire personnelle. **Une fois activée, Jade choisit seule les souvenirs**, sans confirmation pour chaque création.
- Commandes/fonctions d'inspection prévues : « Que sais-tu de moi ? », « Pourquoi te souviens-tu de ça ? », « Corrige ce souvenir », « Oublie-moi », « Dissocie mes comptes », « N'enregistre plus ma mémoire ». Une commande d'un tiers ne peut administrer le profil d'une autre personne.
- Une information dite dans une conversation privée ne devient pas un fait public. Côté vocal, l'identité du compte et l'autorisation d'écouter restent deux garanties distinctes.
- Ne pas exploiter les journaux `jade.conversation` comme mécanisme de réhydratation ; ils peuvent contenir davantage de texte que les souvenirs consentis.
- Ne pas mémoriser de secrets, tokens, identifiants bancaires, données de santé ou autres informations sensibles par défaut ; éviter des inférences à partir de propos ambigus.
- Conserver la possibilité d'exporter ses données et d'effacer complètement un profil (faits ordinaires, Core relationnelles, index dérivés et traces de sauvegarde restaurables). Les Core de Jade qui mentionnent une personne doivent alors être anonymisées ou supprimées si leur contenu permet de la réidentifier.
- Aucun changement aux règles de consentement vocal, de sélection des messages Discord, aux intentions, à la voix Étincelle ni au contenu du prompt personnel initial.

## 9. Proposition de mise en œuvre par lots, pour Codex

**Lot 0 — Contrats / décisions** : confirmer que « jamais purgées » signifie **pas de purge automatique**, avec droits de correction/suppression ; fixer le fonctionnement d'activation personnelle et la visibilité des souvenirs en groupe. Vérifier le dernier état Git sur toutes les branches avant intervention.

**Lot 1 — Identité fiable** : propager les IDs Discord texte, Discord vocal et Twitch ; introduire le service de résolution d'identité et d'association contrôlée, sans sauvegarder encore les dialogues. Tester changement de pseudo, collisions, séparation de comptes, déconnexion vocale et identité inconnue.

**Lot 2 — Stockage des souvenirs ordinaires** : base SQLite privée sur D:, couche de lecture/écriture, migrations, provenance, correction/effacement, règles de portée, transactions, backup et comportement de repli si disque indisponible.

**Lot 3 — Core Memories autonomes** : intégrer le choix d'événement marquant par Jade, stockage sans TTL, provenance et signification pour Jade, doublons, contradictions, révisions, restitution pertinente. Écrire une fiche de décision brève, sans exposer de raisonnement interne ni retarder la voix.

**Lot 4 — Intégration au dialogue et ergonomie** : restitution limitée par tokens dans l'inférence ; visibilité et commandes de consultation/modification ; tests de continuité relationnelle et de non-divulgation.

**Lot 5 — Validation produit** : mesurer latence, coût additionnel, qualité des Core Memories après de longues conversations, pertinence des rappels, suppression et restauration. Exécuter tests ciblés puis suite hors ligne et recette réelle **avec consentement**. L'obtention de tests verts ne valide pas la qualité affective perçue.

## 10. Scénarios d'acceptation (testables, sans développement dans ce chantier)

1. Après redémarrage, Discord reconnaît Alice par son ID stable malgré changement de pseudo ; elle voit ses projets récurrents.
2. Une même personne en Discord texte/vocal retrouve son profil **sans** reconnexion biométrique ; une session vocale expirée ne donne aucun droit d'écoute.
3. Deux comptes différents portant le même nom ne partagent jamais les souvenirs ; un compte Twitch non vérifié reste inconnu.
4. Les comptes Twitch et Discord ne fusionnent qu'après preuve de contrôle de chacun, et peuvent être dissociés sans mélange.
5. Jade choisit spontanément **une Core Memory significative** après un événement construit pour le test, puis ne crée aucune Core pour une série de salutations triviales ; le choix du modèle n'est pas garanti par une simple règle de mots-clés.
6. Une Core Memory reste disponible après redémarrage, expiration des sessions et nettoyage des souvenirs ordinaires. Il n'y a **aucun TTL automatique** pour Core.
7. Une Core relationnelle d'Alice n'est pas restituée à Bob ni postée automatiquement sur Twitch ; un événement de serveur public reste correctement scoped.
8. Un fait erroné est corrigé sans ressurgir comme vérité ; une Core nuancée demeure historiquement traçable tant qu'elle est autorisée à être conservée.
9. « Oublie-moi » supprime les souvenirs personnels et relationnels concernés, ainsi que leurs dérivés ; une restauration ne les fait pas réapparaître.
10. Un tour LLM refusé, annulé ou simplement entendu par la politique Discord ne produit pas abusivement un souvenir ; une réponse seulement `planned_not_confirmed` n'est pas qualifiée de réussite partagée.
11. Le TTS/streaming garde la même balise d'intention existante, sans balise mémoire divulguée ni blocage notable sur une écriture de stockage.
12. Après un grand nombre de Core, elles sont toujours présentes dans la base mais seule une sélection pertinente tient dans le contexte LLM.

## 11. Points de vigilance et questions de conception ultérieures

- **Autonomie versus données des tiers** : permettre la décision libre de Jade à l'intérieur d'une mémoire activée/appropriée, plutôt que demander une validation pour chaque Core ; ne pas assimiler « jamais purgée » à « impossible à supprimer ».
- **Sincérité** : les souvenirs sont des expériences interprétées par Jade, pas une preuve qu'elle possède un vécu humain ou des sentiments biologiques. Ils peuvent infléchir sa voix narrative et sa relation, pas servir de promesses émotionnelles absolues.
- **Croissance** : un stockage Core sans TTL augmente continuellement ; indexation et budgets de récupération sont indispensables, pas une purge déguisée.
- **Identification ambiguë** : l'identification à partir d'un seul micro local est inconnue sauf configuration explicite mono-utilisateur. Aucun système de reconnaissance vocale n'est proposé en V1.
- **Développement simultané** : préserver les changements locaux de Terra/Codex, les contrats `Incoming`, `Reply`, `Dialogue`, la voie de streaming et l'isolement des sessions.

**Décision finale à ce stade : plan documenté ; pas d'implémentation.** La date du document reflète la demande visible, pas un déploiement.
