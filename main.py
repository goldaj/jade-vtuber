"""Jade's new opt-in runtime. Offline demo is the safe default."""
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
from src.jade_runtime.output import AudioOutput, SpeechOutput
from src.jade_runtime.twitch_token import validate_twitch_token
from src.jade_runtime.voice_pipeline import VoiceInput

LOG = logging.getLogger("jade.main")


class DemoChat:
    async def complete(self, messages):
        return "Mode démo : " + messages[-1]["content"].split(": ", 1)[-1][:120]


async def console(*, live=False, voice=False, mic=False, twitch=False,
                  discord=False, vts=False, discord_voice=False, http=False, avatar=False):
    config = Settings.load()
    config.validate()
    if (voice or mic or twitch or discord or vts or discord_voice or http) and not live:
        raise ValueError("external services require --live; demo never bills OpenAI")
    if live:
        config.require_openai()
    if voice and config.audio_output == "none" and not discord_voice:
        raise ValueError("set JADE_AUDIO_OUTPUT=ffplay before enabling billed TTS")
    if twitch and not config.twitch_enabled:
        raise ValueError("set JADE_TWITCH_ENABLED=1 to allow Twitch connection")
    if discord and (not config.discord_token or config.discord_token == "example"):
        raise ValueError("Discord token required")
    if discord_voice and not (discord and voice and config.discord_voice_channel > 0):
        raise ValueError("voice receive requires --discord --voice and an initial voice channel")
    if http and not config.http_enabled:
        raise ValueError("set JADE_HTTP_ENABLED=1 and private JADE_HTTP_TOKEN")
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
    shutdown_deadline = None

    async with AsyncExitStack() as scopes:
        chat = OpenAIServices(config) if live else DemoChat()
        if live:
            close_chat = getattr(chat, "aclose", None)
            scopes.push_async_callback(close_chat if callable(close_chat) else chat.client.close)
        dialogue = Dialogue(chat, prompt, bot_name=config.bot_name,
                            max_messages=config.max_history_messages,
                            random_reply_rate=config.reply_probability)
        avatar_client = None
        if avatar:
            from src.jade_runtime.avatar import Avatar
            avatar_client = await Avatar().start()
            scopes.push_async_callback(avatar_client.close)
        player = AudioOutput(config.audio_output)
        if avatar_client is not None:
            player.playback_observer = avatar_client.observer("local")
        speech = (SpeechOutput(chat, player,
                               config.subtitle_path, audio_gate=audio_gate) if voice else None)
        if vts:
            from src.jade_runtime.vtube_studio import VTubeStudio
            vts_client = await scopes.enter_async_context(VTubeStudio(
                config.vts_token, url=config.vts_url))

        async def on_reply(reply):
            if local_api is not None:
                local_api.deliver(reply)
            print("Jade:", reply.text)

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
                await optional("discord", lambda: discord_client.send_chat(reply.source.channel, reply.text))
            if (vts_client is not None and config.vts_speak_hotkey
                    and not runtime.current_streamed()):
                await optional("vts", lambda: vts_client.trigger_hotkey(config.vts_speak_hotkey))
            if speech is not None and not runtime.current_streamed():
                # TTS and the ensuing playback share this deadline. The old
                # 20-second total could cut off an otherwise valid answer.
                await optional("voice", lambda: speech.speak(reply),
                               timeout=min(180, config.timeout_seconds + 120))

        last_vts_turn = 0

        async def on_sentence(reply):
            nonlocal last_vts_turn
            if speech is None or not runtime.current_valid():
                return False
            hotkey_task = None
            if (vts_client is not None and config.vts_speak_hotkey
                    and runtime.active.turn != last_vts_turn):
                last_vts_turn = runtime.active.turn

                async def trigger_vts():
                    try:
                        await asyncio.wait_for(vts_client.trigger_hotkey(config.vts_speak_hotkey), timeout=20)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        LOG.warning("Jade optional output failed: vts")

                # Do not make the first audible frame wait for VTS.
                hotkey_task = asyncio.create_task(trigger_vts())
            try:
                return await asyncio.wait_for(
                    speech.speak(reply), timeout=min(180, config.timeout_seconds + 120))
            except asyncio.CancelledError:
                raise
            except Exception:
                # The response may already have begun playing: never replay it.
                LOG.warning("Jade optional output failed: voice")
                return False
            finally:
                if hotkey_task is not None:
                    if not hotkey_task.done():
                        hotkey_task.cancel()
                    await asyncio.gather(hotkey_task, return_exceptions=True)

        runtime = Runtime(dialogue, on_reply, config.max_queue,
                          on_sentence=on_sentence if speech is not None else None)
        await runtime.start()
        async def stop_runtime():
            remaining = 5 if shutdown_deadline is None else max(
                0.001, shutdown_deadline - asyncio.get_running_loop().time())
            await runtime.stop(graceful=False, timeout=remaining)
        scopes.push_async_callback(stop_runtime)
        if http:
            from src.jade_runtime.local_http import LocalHTTP
            local_api = LocalHTTP(runtime, token=config.http_token,
                                  port=config.http_port)
        if discord_voice:
            from src.jade_runtime.discord_voice import OpenVoiceBridge
            discord_voice_bridge = OpenVoiceBridge(chat, runtime, config.discord_voice_channel)
            speech.secondary_player = discord_voice_bridge
            if avatar_client is not None:
                discord_voice_bridge.playback_observer = avatar_client.observer("discord")

        async def accept(message):
            await runtime.submit(message)

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
                    voice_bridge=discord_voice_bridge)

            if twitch or discord or mic or http:
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
    parser.add_argument("--preflight", action="store_true",
                        help="Check settings and local dependencies with zero provider/network calls")
    args = vars(parser.parse_args())
    if args.pop("preflight"):
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


if __name__ == "__main__":
    main()
