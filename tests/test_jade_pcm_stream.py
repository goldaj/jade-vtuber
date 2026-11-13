"""Streaming Discord PCM behaves correctly across partial samples and underflow."""
import asyncio
import struct
import unittest

from src.jade_runtime.pcm_stream import FRAME_BYTES, Pcm48StereoBuffer, SILENCE


class PcmStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_underflow_is_silence_then_data_then_real_eof(self):
        buffer = Pcm48StereoBuffer(prebuffer_frames=1)
        self.assertEqual(buffer.read(), SILENCE)
        data = struct.pack("<h", 1000) * 480
        await buffer.feed(data[:1])
        await buffer.feed(data[1:])
        await buffer.finish()
        frame = buffer.read()
        self.assertEqual(len(frame), FRAME_BYTES)
        self.assertEqual(struct.unpack("<hhhh", frame[:8]), (1000, 1000, 1000, 1000))
        self.assertEqual(buffer.read(), b"")

    async def test_close_unblocks_backpressured_producer(self):
        buffer = Pcm48StereoBuffer(max_frames=1, prebuffer_frames=1)
        task = asyncio.create_task(buffer.feed(struct.pack("<h", 500) * 1200))
        await asyncio.wait_for(buffer.ready.wait(), 1)
        self.assertFalse(task.done())
        buffer.close()
        with self.assertRaises(asyncio.CancelledError):
            await task
