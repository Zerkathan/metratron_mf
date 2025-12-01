import sys
import os
import io
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

# FORCE UTF-8 STDOUT
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure we can import src
sys.path.append(os.getcwd())

class TestSafeAudioFileClip(unittest.TestCase):
    def setUp(self):
        # Import SafeAudioFileClip from the patched module
        # We need to import src.video_editor to trigger the monkeypatch
        import src.video_editor
        from moviepy.editor import AudioFileClip
        self.AudioFileClip = AudioFileClip

    def test_safe_audio_clip_init_failure(self):
        print("\nTesting SafeAudioFileClip Init Failure...")
        # Mock AudioFileClip to fail during init
        with patch('moviepy.audio.io.AudioFileClip.AudioFileClip.__init__', side_effect=Exception("Simulated Load Error")):
            clip = self.AudioFileClip("fake_file.mp3")
            
            # Should not crash, should be SafeAudioFileClip
            self.assertEqual(clip.__class__.__name__, 'SafeAudioFileClip')
            
            # Should return silence
            frame = clip.get_frame(0)
            print(f"Frame shape: {frame.shape}, Sum: {np.sum(frame)}")
            self.assertTrue(np.all(frame == 0))
            self.assertEqual(clip.duration, 5.0)

    def test_safe_audio_clip_reader_none(self):
        print("\nTesting SafeAudioFileClip Reader None...")
        # Create a dummy clip
        # We mock the init to avoid actual file loading
        with patch('moviepy.audio.io.AudioFileClip.AudioFileClip.__init__', return_value=None):
            clip = self.AudioFileClip("fake_file.mp3")
            # Force reader to None
            clip.reader = None
            
            # Should return silence instead of crashing
            try:
                frame = clip.get_frame(0.5)
                print(f"Frame shape: {frame.shape}, Sum: {np.sum(frame)}")
                self.assertTrue(np.all(frame == 0))
                print("[SUCCESS] get_frame returned silence when reader is None")
            except Exception as e:
                self.fail(f"get_frame crashed with reader=None: {e}")

if __name__ == "__main__":
    unittest.main()
