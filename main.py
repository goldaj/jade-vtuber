"""Jade runtime: live persistent memory on by default, offline demo isolated."""
import argparse
import asyncio
import logging
from contextlib import AsyncExitStack
from pathlib import Path

from src.jade_runtime.assets import load_prompt
from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.turn_logging import enable_console_logs, planned_destinations
from src.jade_runtime.session_logging import start_session_logging, event, summary
from src.jade_runtime.output import AudioOutput, SpeechOutput
from src.jade_runtime.twitch_token import validate_twitch_token
from src.jade_runtime.voice_pipeline import VoiceInput

LOG = logging.getLogger("jade.main")


class DemoChat:
    async def complete(self, messages):
        return "Mode démo : " + messages[-1]["content"].split(": ", 1)[-1][:120]


async def console(*, live=False, voice=False, mic=False, twitch=False,
                  discord=False, vts=False, discord_voice=False, http=False,
                  avatar=False, mobile=False, all_channels=False):
    config = Settings.load()
    config.validate()
    enable_console_logs(enable_latency=config.latency_logging)
    summary("runtime_configuration", live=live, discord=discord, discord_voice=discord_voice,
            mobile=mobile, microphone=mic, twitch=twitch, memory=config.memory_enabled,
            early_voice=config.early_voice, llm_model=config.model,
            max_completion_tokens=config.max_completion_tokens)
    event("runtime_configuration", live=live, discord=discord, discord_voice=discord_voice,
          mobile=mobile, microphone=mic, twitch=twitch, memory=config.memory_enabled,
          memory_curator=config.memory_curator_enabled,
          early_voice=config.early_voice, llm_model=config.model,
          reasoning_effort=config.reasoning_effort, tts_model=config.tts_model,
           max_completion_tokens=config.max_completion_tokens)
    if (voice or mic or twitch or discord or vts or discord_voice or http or mobile) and not live:
        raise ValueError("external services require --live; demo never bills OpenAI")
    if live:
        config.require_openai()
    if voice and config.audio_output == "none" and not discord_voice:
        raise ValueError("set JADE_AUDIO_OUTPUT=ffplay before enabling billed TTS")
    if all_channels and not config.twitch_send:
        raise ValueError("JADE_TWITCH_SEND=1 is required so Twitch can reply in all-channel mode")
    if all_channels and config.audio_output != "ffplay":
        raise ValueError("JADE_AUDIO_OUTPUT=ffplay is required for private local microphone replies")
    if twitch and not config.twitch_enabled:
        raise ValueError("set JADE_TWITCH_ENABLED=1 to allow Twitch connection")
    if discord and (not config.discord_token or config.discord_token == "example"):
        raise ValueError("Discord token required")
    if discord_voice and not (discord and voice and config.discord_voice_channel > 0):
        raise ValueError("voice receive requires --discord --voice and an initial voice channel")
    if http and not config.http_enabled:
        raise ValueError("set JADE_HTTP_ENABLED=1 and private JADE_HTTP_TOKEN")
    if mobile and not config.mobile_enabled:
        raise ValueError("set JADE_MOBILE_ENABLED=1 and private JADE_MOBILE_TOKEN")
    if vts and not config.vts_enabled:
        raise ValueError("set JADE_VTS_ENABLED=1 and provide the local token")
    prompt = load_prompt(Path(__file__).parent)
    if voice or mic:
        from src.jade_runtime.microphone import AudioCoordinator
        audio_gate = AudioCoordinator()
    else:
        audio_gate = None
    twitch_client = None
    twitch_manager = None
    discord_client = None
    vts_client = None
    discord_voice_bridge = None
    local_api = None
    mobile_gateway = None
    shutdown_deadline = None

    async with AsyncExitStack() as scopes:
        chat = OpenAIServices(config) if live else DemoChat()
        if live:
            scopes.push_async_callback(chat.close if callable(getattr(chat, 'close', None))
                                       else chat.client.close)
        dialogue = Dialogue(chat, prompt, bot_name=config.bot_name,
                            max_messages=config.max_history_messages,
                            random_reply_rate=config.reply_probability,
                            selective_context=bool(live and config.selective_context_enabled))
        memory = None
        if config.memory_enabled and live:
            from src.jade_runtime.memory_store import MemoryStore
            from src.jade_runtime.memory_service import MemoryService
            store = MemoryStore(Path(config.memory_db_path))
            if mic or mobile:
                # Private microphone and authenticated mobile gateway are Goldaj.
                await asyncio.to_thread(store.enable, ("microphone", "goldaj"))
            memory = MemoryService(store, chat,
                                   curator_enabled=bool(config.memory_curator_enabled and live),
                                   curation_mode=("batch" if config.memory_batch_enabled else "single"))
            scopes.push_async_callback(memory.close)
            if mic or mobile:
                # No LLM request: authorized owner L1/L2 warm before first turn.
                await memory.prefetch_owner()

            # Retention is enforced even for a long-running, otherwise idle Jade.
            # MemoryStore already prunes once during initialization.
            async def memory_retention_loop():
                while True:
                    await asyncio.sleep(3600)
                    try:
                        await asyncio.to_thread(store.prune_expired)
                    except Exception:
                        LOG.warning("Periodic SQLite memory purge unavailable; no content logged")

            retention_task = asyncio.create_task(
                memory_retention_loop(), name="jade-memory-retention")

            async def stop_memory_retention():
                retention_task.cancel()
                try:
                    await retention_task
                except asyncio.CancelledError:
                    pass

            scopes.push_async_callback(stop_memory_retention)
        # Persistent, verified owner continuity. No background LLM or actions.
        cross_channel = None
        if memory is not None:
            try:
                from src.jade_runtime.cross_channel import CrossChannelContinuity
                cross_channel = CrossChannelContinuity(
                    memory.store, allowed_discord_channels=config.cross_channel_discord_targets,
                    send_discord=lambda target, text: (
                        discord_client.send_chat(target, text)
                        if discord_client is not None else asyncio.sleep(0, result=False)))
            except Exception:
                # Optional task continuity cannot prevent the existing dialogue,
                # memory and transport connectors from starting.
                LOG.warning("Optional cross-channel continuity unavailable")
        avatar_client = None
        if avatar:
            from src.jade_runtime.avatar import Avatar
            avatar_client = await Avatar(intent_enabled=config.avatar_intent_enabled).start()
            scopes.push_async_callback(avatar_client.close)
        player = AudioOutput(config.audio_output)
        if avatar_client is not None:
            player.playback_observer = avatar_client.observer("local")
        speech = (SpeechOutput(chat, player,
                               config.subtitle_path, audio_gate=audio_gate,
                               early_timeout_seconds=min(180, config.timeout_seconds + 120)) if voice else None)
        if vts:
            from src.jade_runtime.vtube_studio import VTubeStudio
            vts_client = await scopes.enter_async_context(VTubeStudio(
                config.vts_token, url=config.vts_url))

        vts_tasks = set()

        async def stop_vts_tasks():
            # Do not let a slow visual hotkey hold up a voice reply or shutdown.
            for task in tuple(vts_tasks):
                task.cancel()
            if vts_tasks:
                await asyncio.gather(*vts_tasks, return_exceptions=True)

        async def on_reply(reply):
            if local_api is not None:
                local_api.deliver(reply)
            if mobile_gateway is not None:
                mobile_gateway.deliver(reply)
            # Mobile replies contain owner-only conversations. Do not echo
            # their full text to stdout; responses are delivered to the app.
            if reply.source.platform not in ("mobile",) and not (
                    reply.source.platform == "discord" and reply.source.private_channel):
                print("Jade:", reply.text)
            # Expressions use trusted, normalized Reply.intent (never raw LLM text).
            # Text-only replies also animate; mobile has its own Live2D instance.
            if avatar_client is not None and runtime.current_valid():
                avatar_client.set_intent(reply.intent)

            async def optional(label, action, *, timeout=20):
                if not runtime.current_valid():
                    return
                try:
                    await asyncio.wait_for(action(), timeout=timeout)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOG.warning("Jade optional output failed: %s", label)

            if reply.source.platform == "twitch" and twitch_client is not None:
                await optional("twitch", lambda: twitch_client.send_chat(reply.text))
            if reply.source.platform == "discord" and discord_client is not None:
                # Delivery is REQUIRED for a Discord reply, not an optional
                # decoration: an undelivered DM must not be stored as "sent"
                # or trigger autonomous curation. Never log private contents.
                sent = await asyncio.wait_for(discord_client.send_chat(
                    reply.source.channel, reply.text,
                    source_message_id=reply.source.message_id), timeout=20)
                if not sent:
                    raise RuntimeError("Discord message delivery not confirmed")
            if (vts_client is not None and speech is not None and config.vts_speak_hotkey
                    and not reply.spoken
                    and reply.source.platform in ("microphone", "discord_voice", "console")):
                # Optional animation runs independently; voice starts immediately
                # and the turn is not blocked by a 20-second VTube Studio timeout.
                vts_task = asyncio.create_task(
                    optional("vts", lambda: vts_client.trigger_hotkey(config.vts_speak_hotkey)))
                vts_tasks.add(vts_task)
                vts_task.add_done_callback(vts_tasks.discard)
            if (speech is not None and not reply.spoken
                    and reply.source.platform in ("microphone", "discord_voice", "console")):
                # TTS and the ensuing playback share this deadline. The old
                # 20-second total could cut off an otherwise valid answer.
                await optional("voice", lambda: speech.speak(reply),
                               timeout=min(180, config.timeout_seconds + 120))

        def start_early_voice(source):
            turn = speech.start_early(source)
            if turn is not None and vts_client is not None and config.vts_speak_hotkey:
                async def trigger_vts():
                    try:
                        await asyncio.wait_for(vts_client.trigger_hotkey(config.vts_speak_hotkey), timeout=20)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        LOG.warning("Jade optional output failed: vts")

                # The turn invokes this once, concurrently with its first audio.
                turn.on_first_sentence = trigger_vts
            return turn

        def describe_delivery(reply):
            return planned_destinations(
                reply, has_speech=speech is not None,
                audio_output=config.audio_output,
                discord_voice=discord_voice_bridge is not None,
                twitch_text=twitch_client is not None and config.twitch_send,
                discord_text=discord_client is not None,
                local_http=local_api is not None,
                mobile=mobile_gateway is not None)

        runtime = Runtime(dialogue, on_reply, config.max_queue,
                          on_stream_start=(start_early_voice if speech and config.early_voice else None),
                          delivery_plan=describe_delivery,
                          memory_service=memory,
                          cross_channel=cross_channel)
        await runtime.start()
        async def stop_runtime():
            remaining = 5 if shutdown_deadline is None else max(
                0.001, shutdown_deadline - asyncio.get_running_loop().time())
            await runtime.stop(graceful=False, timeout=remaining)
        scopes.push_async_callback(stop_runtime)
        scopes.push_async_callback(stop_vts_tasks)
        if http:
            from src.jade_runtime.local_http import LocalHTTP
            local_api = LocalHTTP(runtime, token=config.http_token,
                                  port=config.http_port)
        if mobile:
            from src.jade_runtime.mobile_gateway import MobileGateway
            mobile_gateway = MobileGateway(
                runtime, chat, token=config.mobile_token, port=config.mobile_port,
                billing_admin_key=config.billing_admin_key,
                deploy_supervisor_token=config.deploy_supervisor_token,
                deploy_supervisor_port=config.deploy_supervisor_port,
                owner_login=config.mobile_owner_login,
                public_origin=config.mobile_public_origin,
                vendor_dir=Path(config.mobile_vendor_dir) if config.mobile_vendor_dir else None,
                model_dir=Path(config.mobile_model_dir) if config.mobile_model_dir else None,
                avatar_intent_enabled=config.avatar_intent_enabled)
        social_policy = None
        initiatives = None
        if discord and live and config.memory_enabled:
            from src.jade_runtime.cost_guard import CostGuard
            from src.jade_runtime.social_intelligence import HybridSocialPolicy
            from src.jade_runtime.initiatives import InitiativeScheduler
            guard = CostGuard(Path(config.memory_db_path))
            if config.social_hybrid_enabled:
                social_policy = HybridSocialPolicy(
                    chat, guard, daily_usd=config.social_budget_daily_usd,
                    monthly_usd=config.social_budget_monthly_usd)
            if config.initiatives_enabled:
                initiatives = InitiativeScheduler(
                    guard, daily_usd=config.initiative_budget_daily_usd,
                    monthly_usd=config.initiative_budget_monthly_usd)
        if discord_voice:
            from src.jade_runtime.discord_voice import OpenVoiceBridge
            discord_voice_bridge = OpenVoiceBridge(
                chat, runtime, config.discord_voice_channel,
                group_reply_rate=config.discord_voice_auto_rate)
            discord_voice_bridge.initiatives = initiatives
            speech.secondary_player = discord_voice_bridge
            if avatar_client is not None:
                discord_voice_bridge.playback_observer = avatar_client.observer("discord")

        async def accept(message):
            # Twitch needs the Work.finished signal to ignore stale chat while replying.
            return await runtime.submit(message)

        try:
            if twitch:
                from src.jade_runtime.twitch_irc import TwitchIRC
                if config.twitch_auto_refresh:
                    from src.jade_runtime.private_backup import sync_private_backup
                    from src.jade_runtime.twitch_rotation import TwitchTokenManager
                    from src.utility.private_config import secrets_file
                    twitch_manager = TwitchTokenManager(
                        secrets_file(), sync_backup=sync_private_backup,
                        login=config.twitch_login, send_enabled=config.twitch_send)
                    identity = await asyncio.to_thread(twitch_manager.check)
                    if identity.backup_pending:
                        LOG.error("Sauvegarde privée Twitch non synchronisée ; intervention nécessaire")
                    token = identity.access_token
                    twitch_manager.login = identity.login
                else:
                    identity = await asyncio.to_thread(
                        validate_twitch_token, config.twitch_oauth,
                        login=config.twitch_login, send_enabled=config.twitch_send)
                    token = config.twitch_oauth
                twitch_client = TwitchIRC(
                    login=identity.login, token=token,
                    channel=config.channel, on_message=accept,
                    send_enabled=config.twitch_send)
            if discord:
                from src.jade_runtime.discord_text import DiscordText
                discord_client = DiscordText(
                    config.discord_token, accept, send_enabled=True,
                    voice_bridge=discord_voice_bridge, bot_name=config.bot_name,
                    auto_rate=config.discord_text_auto_rate,
                    cooldown_seconds=config.discord_text_cooldown_seconds,
                    social_policy=social_policy, initiatives=initiatives)

            if twitch or discord or mic or http or mobile:
                print("Jade connecteurs activés. Quitter avec Ctrl+C.")
                tasks = []
                try:
                    if twitch_client is not None:
                        if twitch_manager is not None:
                            from src.jade_runtime.twitch_managed import run_managed_twitch
                            tasks.append(asyncio.create_task(run_managed_twitch(twitch_client, twitch_manager)))
                        else:
                            tasks.append(asyncio.create_task(twitch_client.connect_forever()))
                    if discord_client is not None:
                        tasks.append(asyncio.create_task(discord_client.connect_forever()))
                    if mic:
                        print("Microphone activé : audio transmis à OpenAI STT.")
                        tasks.append(asyncio.create_task(VoiceInput(chat, runtime, audio_gate=audio_gate).loop()))
                    if local_api is not None:
                        tasks.append(asyncio.create_task(local_api.serve_forever()))
                    if mobile_gateway is not None:
                        tasks.append(asyncio.create_task(mobile_gateway.serve_forever()))
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                    for task in done:
                        task.result()
                finally:
                    shutdown_deadline = asyncio.get_running_loop().time() + 5
                    runtime.begin_shutdown()
                    for task in tasks:
                        task.cancel()
                    if audio_gate is not None:
                        try:
                            await asyncio.wait_for(audio_gate.close(), timeout=min(
                                2, max(0.001, shutdown_deadline - asyncio.get_running_loop().time())))
                        except TimeoutError:
                            LOG.error("Audio capture did not stop within the shutdown deadline")
                    if tasks:
                        finished, pending = await asyncio.wait(tasks, timeout=max(
                            0, shutdown_deadline - asyncio.get_running_loop().time()))
                        for task in finished:
                            if not task.cancelled() and task.exception() is not None:
                                LOG.warning("Connector stopped with an error during shutdown")
                        if pending:
                            LOG.error("Some connector tasks did not stop within the deadline")
            else:
                print("Jade :", "API OpenAI" if live else "démo hors ligne",
                      "(quitter avec /exit)")
                while True:
                    line = await asyncio.to_thread(input, "Vous: ")
                    if line.strip() in ("/exit", "/quit"):
                        break
                    if line.strip():
                        await runtime.submit(Incoming(
                            platform="console", author="local", text=line,
                            force_reply=True))
                        await runtime.idle()
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            await stop_runtime()


def main():
    start_session_logging()
    parser = argparse.ArgumentParser(description="Jade modular runtime")
    parser.add_argument("--live", action="store_true", help="Enable billed OpenAI requests")
    parser.add_argument("--voice", action="store_true", help="Billed OpenAI TTS via local ffplay")
    parser.add_argument("--mic", action="store_true", help="Capture microphone for OpenAI STT")
    parser.add_argument("--twitch", action="store_true", help="Read Twitch IRC chat")
    parser.add_argument("--discord", action="store_true", help="Read Discord guild text")
    parser.add_argument("--vts", action="store_true", help="Control localhost VTube Studio")
    parser.add_argument("--http", action="store_true",
                        help="Authenticated loopback-only text API")
    parser.add_argument("--discord-voice", action="store_true",
                        help="Explicitly receive Discord voice and send audio to OpenAI STT")
    parser.add_argument("--avatar", action="store_true",
                        help="Display the animated Live2D r20 avatar")
    parser.add_argument("--mobile", action="store_true",
                        help="Start the owner-only mobile PWA on localhost")
    parser.add_argument("--all-channels", action="store_true",
                        help="Start all inputs and avatar simultaneously; no channel mode selection")
    parser.add_argument("--preflight", action="store_true",
                        help="Check settings and local dependencies with zero provider/network calls")
    args = vars(parser.parse_args())
    all_channels = args.pop("all_channels")
    preflight = args.pop("preflight")
    if all_channels:
        # A single instance for all transports; no channel takes precedence.
        # VTS is an optional alternate renderer, used only when configured;
        # the autonomous r20 avatar is started in every case.
        settings = Settings.load()
        args.update(live=True, voice=True, mic=True, twitch=True,
                    discord=True, discord_voice=True, http=True,
                    avatar=True, mobile=True, vts=settings.vts_enabled,
                    all_channels=True)
    if preflight:
        from src.jade_runtime.diagnostics import inspect_environment
        try:
            config = Settings.load()
            checks = inspect_environment(config, **args)
        except ValueError as exc:
            print("Configuration invalide:", exc)
            raise SystemExit(2) from exc
        for check in checks:
            status = "OK" if check.ok else ("ERREUR" if check.required else "INFO")
            print(f"[{status}] {check.name}: {check.detail}")
        if any(check.required and not check.ok for check in checks):
            raise SystemExit(2)
        print("Préflight terminé. Aucun appel OpenAI, aucune connexion, aucun microphone.")
        return
    try:
        asyncio.run(console(**args))
    except KeyboardInterrupt:
        pass
    except Exception:
        LOG.exception("Jade startup/runtime failed")
        raise


if __name__ == "__main__":
    main()
