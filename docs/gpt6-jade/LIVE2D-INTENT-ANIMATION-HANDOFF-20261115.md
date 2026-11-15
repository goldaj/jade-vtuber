# Passation Codex : expressions, textes et futures animations 2D par intention
**Branche :** `feat/live2d-intent-expression-sync-20261115`, destinée à `develop`. **Date :** 15 novembre 2026.
**Décision explicite du propriétaire :** CHAQUE intention doit finalement avoir son animation Live2D propre, reconnaissable, avec **au moins deux réactions visuelles et deux présentations textuelles différentes**. Ce besoin est un critère produit, pas une suggestion décorative.

## Revue multi-personas et choix de sécurité produit
- **PO / UX :** varier les réactions sans générer des gestes incohérents ou surjoués. Réactions cohérentes avec la personnalité de Jade ; pas de deuxième LLM, pas de pollution de ses réponses avec des libellés de contrôle.
- **Architecture :** `Reply.intent` est la source après filtrage de `[INTENT:...]`. `src/jade_runtime/mobile_web/intent-visuals.json` est le **seul catalogue** des réactions courantes, lu et validé par `intent_visuals.py`, servi à Android et consommé par l'avatar Python. Modifier ce contrat, pas créer une seconde table JS.
- **Live2D / rigging :** le r20 n'offre actuellement que l'Idle et les expressions Neutral (reset), Smile, Sad, Angry, Surprised, Blink, WinkL, WinkR. Les deux variantes codées pour chaque intention sont des **expressions faciales de substitution**, pas 14 animations dédiées. Aucun motion3 supplémentaire fictif n'est lancé.
- **Audio / streaming :** la bouche continue de suivre les données audio ; la commande d'expression est séparée et ne peut pas être écrasée par 25 mises à jour de bouche/seconde. À l'arrêt de la voix ou après délai pour l'écrit, l'avatar revient au neutre. Le pitch, TTS, STT, Discord et mémoire ne changent pas.
- **Qualité / sécurité :** labels autorisés strictement, un comportement par défaut `neutral`, échec du renderer sans annulation du dialogue. Les messages privés ne sont pas recopiés dans d'autres canaux. Pas de SDK propriétaire dans Git.

## Matrice courante, **livrée comme substitut facial**
| Intention | Réaction A (visage) | Texte A | Réaction B (visage) | Texte B |
| --- | --- | --- | --- | --- |
| neutral | Neutral | Repos paisible | Blink | Un instant de calme |
| playful | WinkR | Petite malice | WinkL | Clin d’œil complice |
| excited | Smile | Joie pétillante | Surprised | Élan enthousiaste |
| curious | Surprised | Attention intriguée | Blink | Réflexion en cours |
| tender | WinkL | Douceur timide | Smile | Sourire affectueux |
| reassuring | Blink | Présence apaisante | Smile | Sourire rassurant |
| serious | Sad | Regard grave | Neutral | Concentration tranquille |

**État actuel :** rotation A/B par intention (compteur par instance), 14 textes distincts visibles dans la ligne d'humeur de la PWA mobile ; rendu PC des expressions, sans texte superposé dans la fenêtre OpenGL. Le texte de réaction est **décoratif**, non inclus dans `Reply.text`, ni prononcé, ni ajouté à la mémoire, ni publié sur Discord/Twitch/OBS. Chaque intention a une première expression différente, mais des expressions sont réutilisées dans les variantes B. Aucune variation d'animation corporelle propre à l'intention n'existe encore.

## Commande et extinction
- Le réglage global est `JADE_AVATAR_INTENT_ENABLED=1` par défaut, `0` désactive la réaction aux intentions sur l'avatar PC et dans la PWA mobile, **sans** désactiver extraction d'intentions, prosodie TTS, Idle ou synchronisation de la bouche.
- Changer la variable nécessite **redémarrage de Jade** et rechargement de la PWA ; ce n'est pas un interrupteur en temps réel sur l'écran.
- Le backend PWA sert `GET /assets/intent-visuals.json` en fonction de la configuration du PC. Ne pas renvoyer de token ou de métadonnées conversationnelles. L'échec de ce catalogue doit dégrader l'affichage, pas la réponse IA.
- PC : expression reçue à chaque `on_reply` valide ; le retour neutre est envoyé après fin de lecture audio, ou à 12 s si aucune lecture n'est active. Mobile : expression et texte à l'arrivée de la réponse, retour neutre à la fin de l'audio ou après 12 s si elle est écrite seule.

## Reste IMPÉRATIVEMENT à créer par Codex, avec designer / rigger Live2D
1. **14 animations distinctes en conditions réelles**, deux pour chacune des sept intentions. Distinguer gestuelle, regard, rythme, micro-expression et posture selon le cas, et ne pas simplement renommer deux fichiers de la même animation. Les 7 versions A doivent aussi être distinctes. Par exemple, pour `curious` : inclinaison de tête + regard, puis regard interrogatif + léger geste. Les exemples sont des pistes artistiques, pas des ressources présentes.
2. Préparer le rig sur le modèle 2D **intégral en pied** choisi par le propriétaire. Vérifier que la source r20 actuellement utilisée peut réellement être remplacée par le r21 en pied sans régresser animations, motion groups et affichage mobile. **Ne pas basculer r21 automatiquement**, son rig final n'est pas validé. Suivre les droits Live2D et Git LFS.
3. Exporter et versionner les ressources compatibles : motions `.motion3.json`, éventuels paramètres/expressions `.exp3.json`, déclaration des groupes de motion dans `Jade.model3.json`, ordre / loop / priorité / blend et contraintes du SDK. Prévoir une validation automatique de l'existence des 14 motion IDs et des paramètres modifiés, avec contrôle réel du rendu.
4. Étendre le schéma partagé par une **version 2** comprenant un identifiant de motion par variante, une politique de transition/blending, durée et retour à l'Idle. N'activer les appels `StartMotion` / `model.motion` pour un identifiant que si **tous** les assets et SDK des deux rendus ont été validés. En cas d'asset incomplet : rester en mode facial de repli **sans crash**.
5. Tester les 14 animations sur Windows, puis Android Wi-Fi/4G et après arrière-plan/reconnexion, les 7 intentions au moins deux fois, et la lisibilité de chacune sans audio. Vérifier superposition des expressions, lèvres, clignements, Idle, délais et interruptions.
6. **Texte à compléter :** les 14 libellés PWA sont implémentés. Décider avec le propriétaire d'une représentation textuelle dédiée pour le renderer PC, les sous-titres OBS ou les réponses Discord/Twitch ; n'ajouter ni emoji ni didascalie automatiquement aux messages publics, et ne jamais faire prononcer les métadonnées par le TTS.
7. Tester la remise à zéro sur la vraie version de `pixi-live2d-display`. `resetExpression()` est utilisé **uniquement si disponible** ; certains SDK ou bindings n'offrent pas cette méthode. S'assurer que `neutral` redevient réellement neutre, sans rester figé dans la dernière expression.
8. Après ajout de motions réelles : tests d'interruption / précédence de `Idle` / évitement du chevauchement de motions (PC et mobile), et usage CPU/GPU/latence sur de vraies machines. Ne pas promettre une animation « validée » sur la seule base de mocks.

## Preuves et limites de cette livraison
- Contrat partagé de 7 intentions, deux variantes faciales et deux textes par intention ; sélecteur robuste contre les labels inconnus.
- Route mobile globale et commande PC sans pertes de mouvements de bouche ; tests automatiques ajoutés dans `tests/test_jade_intent_visuals.py`.
- **Les tests automatisés ne sont pas une recette matérielle.** Le SDK Web Live2D, les GPU, la compatibilité Cubism, le changement r20→r21 et les 14 animations propres restent à valider ou à développer sur les appareils réels.
- Faire une passe de PO, animation, backend, QA, mobile, SRE après tout changement de modèle. Maintenir les neuf documents du manuel et cette passation synchronisés. Laisser `main` inchangée sans autorisation explicite.

## Statuts honnêtes à transmettre
| Élément | Statut |
| --- | --- |
| Intentions extraites et voix influencée | Déjà intégré sur develop avant ce chantier |
| Toggle global / 7×2 intentions→expressions / 14 textes / PC / PWA | Codé sur cette branche, tests et intégration à contrôler |
| Animation bouche et Idle r20 existants | Conservés, qualité sur machines réelles non confirmée |
| Deux **animations corporelles originales** par intention (14) | **ABSENTES : création des assets Live2D à réaliser** |
| Représentation textuelle sur mobile | Codée, recette visuelle Android requise |
| Représentation textuelle additionnelle sur PC/Discord/Twitch | Non branchée, décision produit à prendre pour éviter du bruit |
| Rendu mobile et reset neutre Cubism 4/5 | Non validés en environnement réel |
| Rig final r21 complet en pied | Travaux art/rig en cours, **non connecté** |

**Compatibilité de l'aperçu de publication isolé :** le catalogue JSON versionné doit rester sur la liste blanche explicite de `tools/jade_publication_export.py`, sinon le moteur ne peut pas lire ses deux variantes depuis l'aperçu cloné et les tests d'export échouent. Ne pas inclure pour autant les assets LFS ou SDK propriétaires dans l'aperçu.
