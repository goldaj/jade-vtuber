# Jade : autorisation de développement d'une application mobile privée (15 novembre 2026)

**Demande utilisateur :** « Maintenant j'aimerais qu'on rajoute une appli dédiée, uniquement pour moi, qui me permettra de voir le modèle bouger, en effaçant le fonds vert et en créant un petit décor sympa derrière elle. Je lui parlerai et lui écrirai via l'appli. Ça comptera en micro local mobile et écrit local mobile, donc Goldaj uniquement, son créateur, passera par ce biais. L'appli mobile peut passer par mon vps si ça aide, avec le vpn que j'utilise déjà et toute la conf serveur qui est faite sur le bot de trading hyperliquid. Dis-moi ce qui est le mieux avant de te lancer à le faire. Fait moi les propositions les plus adaptées. »

**Recommandation de l'assistant (résumé) :** PWA Android privée et installable avec modèle Live2D transparent animé directement sur l'appareil, décor CSS, microphone et chat ; moteur OpenAI/LLM et mémoire sur le PC Windows Jade, accès HTTPS par Tailscale Serve directement sur le PC, **sans détour ni modification du VPS Hyperliquid**. Développement progressif : texte et appuyer-pour-parler d'abord, streaming duplex et packaging APK ensuite.

**Autorisation explicite utilisateur :** « Vas-y je t'autorise à développer tout ça, en utilisant les solutions que tu recommandes. »

**Travail distant sur la branche isolée** `feat/jade-private-mobile-pwa-20261115`, PR indépendante `#7` vers `develop`. Passerelle HTTP privée, frontend installable, modèle r20 sous réserve du SDK Web propriétaire installé sur le PC, entrée voix/texte mobile Goldaj, passage OpenAI STT/TTS. Le SDK Web Cubism Core n'est pas publié dans Git ; le VPS trading et `main` ne sont pas touchés. Les essais Android, affichage Live2D réel et Tailscale restent à effectuer physiquement.

Voir le [guide de reprise Codex](../gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md). Cette note est une synthèse des messages accessibles et non une transcription complète, aucune information privée d'accès n'y figure.
