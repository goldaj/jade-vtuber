"""Synthetic reproductions against a supplied Jade checkout; no network/hardware.

This records defects on the audited baseline. It is not the desired regression
suite: after fixes, the reported defect flags must become false.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import AsyncMock, Mock, patch

parser = argparse.ArgumentParser()
parser.add_argument('repo', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.repo.resolve()))
os.environ['JADE_SECRETS_FILE'] = r'D:\Codex\tmp\jade-audit-no-secrets.env'
tempfile.tempdir = r'D:\Codex\tmp'
# Stub only private config loading, so this reproduction neither reads the
# private dotenv nor requires installed python-decouple/OpenAI packages.
sys.modules['src.utility.private_config'] = types.SimpleNamespace(
    environ=lambda name, default=None: default)

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.messages import Incoming
from src.jade_runtime.voice_pipeline import VoiceInput
from src.jade_runtime.output import AudioOutput

class Echo:
    async def complete(self, messages):
        return 'synthetic'

async def check():
    results = {}
    speaking = asyncio.Event()
    release = asyncio.Event()
    captured = []
    async def output(reply):
        speaking.set()
        await release.wait()
    runner = Runtime(Dialogue(Echo(), 'Jade'), output)
    await runner.start()
    await runner.submit(Incoming('twitch', 'synthetic', 'Jade'))
    await asyncio.wait_for(speaking.wait(), 1)
    async def capture(duration):
        captured.append(speaking.is_set())
        return None
    voice = VoiceInput(AsyncMock(), runner, capture=capture)
    await voice.once()
    results['microphone_captures_during_other_reply'] = captured == [True]
    stopping = asyncio.create_task(runner.stop())
    await asyncio.sleep(.05)
    results['shutdown_waits_for_blocked_reply'] = not stopping.done()
    release.set()
    await asyncio.wait_for(stopping, 1)

    dialogue = Dialogue(Echo(), 'Jade', max_messages=2)
    for number in range(600):
        await dialogue.respond(Incoming('http', 'synthetic', 'synthetic',
            channel=str(number), force_reply=True))
    results['sessions_after_600_unique'] = {
        name: len(getattr(dialogue, name)) for name in ('history', 'seen', 'locks')}

    started = asyncio.Event()
    hold = asyncio.Event()
    class FakeProcess:
        def __init__(self):
            self.terminate = Mock()
            self.kill = Mock()
        async def wait(self):
            started.set()
            await hold.wait()
    process = FakeProcess()
    with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=process)):
        playback = asyncio.create_task(AudioOutput('ffplay').play(b'RIFFsynthetic'))
        await asyncio.wait_for(started.wait(), 1)
        playback.cancel()
        try:
            await playback
        except asyncio.CancelledError:
            pass
    results['cancelled_audio_terminate_calls'] = process.terminate.call_count
    results['cancelled_audio_kill_calls'] = process.kill.call_count
    print(json.dumps(results, ensure_ascii=False, indent=2))

asyncio.run(check())
