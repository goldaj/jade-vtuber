# Architecture des six évolutions économiques de Jade — 21/11/2026

**Branche d'implémentation :** `feat/jade-economie-social-memoire-voix-20261121` (PR #34 vers `develop`). **Ne jamais fusionner vers `main` sans accord.**

## Décision produit finale sur les initiatives

- **Déclenchement permis dès un événement** : un humain rejoint le vocal, Jade peut saluer sans que quiconque lui ait encore parlé. Aucune limite de nombre par jour.
- **Stop quand elle est ignorée** : après une initiative, Jade **n'enchaîne pas de relances autonomes** dans le même salon tant qu'une personne n'a pas réellement parlé ou réagi ; un salon vidé puis rejoint constitue une nouvelle session.
- **Veille inactive gratuite pour les initiatives** : ni boucle LLM ni vérification temporelle payante. Les seuls déclencheurs sont des événements locaux, et la sélection n'appelle l'API que pour une vraie intervention.
- **Budgets facultatifs, distincts** : les budgets d'initiatives `JADE_INITIATIVE_BUDGET_DAILY_USD` et `JADE_INITIATIVE_BUDGET_MONTHLY_USD` sont à zéro par défaut (= **aucun plafond monétaire**, pas « OFF »). Le propriétaire peut les fixer ; `CostGuard` conserve des **réservations estimées** et la déduplication dans SQLite, mais ces sommes ne sont pas des factures OpenAI définitives. La sécurité financière forte nécessite aussi un plafond côté fournisseur.
- Le coût de la première intervention sur un événement de connexion est réel, même si personne ne répond ensuite. Les phases de silence sans nouvel événement ne déclenchent aucun coût d'initiative.

## Composants et responsabilités

| Source | Module | Responsabilité |
|---|---|---|
| Historique SQLite par identité/salon | `context_selection.py` + `dialogue.py` | Choisir localement les tours récents et anciens pertinents avant l'appel de dialogue ; conserver les 24 h intégrales en base, L1 purgé à 7 jours. |
| Échanges consentis | `memory_batch.py` + `memory_service.py` | Filtrer les banalités, rassembler jusqu'à 3 candidats sur 18 secondes, un appel de curation par lot au maximum ; personne et portée épinglées à l'envoi, effacement vérifié à l'écriture. |
| Souvenirs personnels et autobiographie réservée | `personality_evolution.py` | Fournir quelques repères autorisés au dialogue sans nouveau LLM ; seule Jade décide de ses Core Memories. |
| Activité humaine Discord | `discord_text_policy.py` + `social_intelligence.py` | Décision locale prioritaire ; classifieur LLM facultatif sur certaines ambiguïtés, avec budget distinct et repli local. |
| Entrée dans un vocal Discord | `initiatives.py` + `discord_text.py` | Une initiative de bienvenue possible sur événement d'arrivée, aucun sondage payant en silence, attente d'une réaction humaine ; déduplication persistante. **Si le vocal et la session sont actifs, cette première intégration utilise le TTS vocal existant** ; sinon elle peut se replier sur le chat natif du même salon. La présence du membre est revérifiée juste avant de parler, et le tour synthétique ne crée aucune mémoire au nom du participant. |
| Plafonds facultatifs | `cost_guard.py` | Réservations USD à l'avance et idempotence SQLite. Le zéro d'initiative vaut budget illimité ; le zéro de classification sociale vaut classification payante désactivée. |
| PWA Android + Tailscale Serve | `mobile_duplex.py`, `mobile_gateway.py`, `mobile_web/duplex-client.js`, `mobile_web/app.js` | WebSocket privé avec jeton en charge utile TLS, trames PCM16/16 kHz bornées (20 s), STT existant à la fin d'une prise de parole, TTS en flux, annulation, fin de phrase locale et repli WAV HTTP si WebSocket indisponible avant la session. |

## Contrats de flux

### Dialogue et mémoire

1. La source identifie l'interlocuteur et le salon ; `MemoryStore` recharge la fenêtre locale de 24 h avec tous les tours disponibles.
2. `select_context` conserve les cinq paires récentes compatibles avec le budget caractères, puis quatre anciennes paires au plus par recouvrement lexical. La base SQLite et les délais de rétention ne sont **pas modifiés**.
3. Le dialogue reçoit aussi les résumés mémoriels consentis et quelques repères de personnalité tirés de la même sélection.
4. Après réponse, la mémoire brute est enregistrée ; la curation optionnelle prend les événements intéressants en lots. Aucune boucle de curation ne travaille indéfiniment sur une conversation inactive.
5. Si une personne efface ou désactive sa mémoire, le `person_id` initial épinglé et les vérifications transactionnelles empêchent la réintroduction de souvenirs après réinscription. Les comptes et salons ne sont jamais fusionnés par déduction de pseudonyme.

### Initiative événementielle

```text
Événement fiable (nouvelle connexion vocale)
    -> filtre local [humain, salon Jade, session ouverte ?]
    -> salon déjà en attente d'une réaction ? [oui = silence]
    -> cooldown / déduplication dans SQLite
    -> budget monétaire configuré ? [si oui, réserver une estimation]
    -> un seul tour Jade, vocal si la session est valable, sinon texte du salon
    -> ATTENTE : aucun polling IA, aucune auto-relance
    -> activité vocale humaine STT ou message Discord réel : réarmement
    -> salon entièrement vide : réarmement pour une nouvelle session
```

Un événement connecté ne prouve pas une réponse. Les messages synthétiques de Jade et les bots ne réarment jamais le comportement.

### Audio mobile

```text
PWA HTTPS/Tailscale -> WebSocket /api/duplex [owner Tailscale + token mémoire]
    -> début de capture / flux PCM16 16 kHz
    -> VAD local et/ou arrêt manuel
    -> fin d'énoncé -> un appel OpenAI STT (pas Realtime conversationnel)
    -> dialogue partagé -> réponse écrite, intention
    -> synthèse TTS existante en PCM progressif ou WAV
    -> PWA écoute/affiche ; cancel ferme le travail et la lecture
```

Le vieux `POST /api/voice` WAV reste présent. Une déconnexion après un appel facturable démarré ne permet **pas** de garantir un remboursement ou un coût nul.

## Options d'arrêt et limites actuelles

- `JADE_INITIATIVES_ENABLED=0` désactive les initiatives tout en conservant le dialogue ; **défaut = 1**.
- `JADE_SOCIAL_HYBRID_ENABLED=0` restaure la décision Discord locale sans classifier ; par défaut activé mais la classification payante nécessite des budgets USD positifs.
- `JADE_MEMORY_BATCH_ENABLED=0` restaure la curation antérieure par échange.
- `JADE_SELECTIVE_CONTEXT_ENABLED=0` restaure l'injection intégrale de l'historique chargé.
- Le duplex mobile reste accessible par la PWA HTTPS sous Tailscale, avec le mode WAV historique si le navigateur ne gère pas WebSocket. Tests Android physiques et vérification du proxy requis avant toute déclaration de recette complète.
- Pas de nouveau moteur Realtime voix, d'embeddings payants, de tâche de veille IA ou de modification de l'avatar 2D.
- Des évolutions supplémentaires sont à prévoir : recette physique du salut parlé, ajustement de la qualité VAD par appareil, pilotage des budgets depuis la PWA, mesure réelle du coût par fonctionnalité et relais vers d'autres types d'événements.

## Preuves de validation

La CI de PR comporte compilation Python, tests unitaires hors ligne, tests réseau local de WebSocket/annulation, syntaxe JS, client progressif et contrôle des secrets. Les essais physiques Discord/Android/Tailscale ne sont pas simulés en résultats réussis. Les détails de CI finale et les limites sont tenus dans la passation propre à la PR.
