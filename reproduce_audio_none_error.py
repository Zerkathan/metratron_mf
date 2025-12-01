import sys
from unittest.mock import MagicMock

# --- 1. SETUP MOCKS BEFORE IMPORTING ---
# Mock modules
sys.modules['moviepy'] = MagicMock()
mock_mp_editor = MagicMock()
sys.modules['moviepy.editor'] = mock_mp_editor
sys.modules['moviepy.video'] = MagicMock()
sys.modules['moviepy.video.VideoClip'] = MagicMock()
sys.modules['moviepy.video.fx'] = MagicMock()
sys.modules['moviepy.video.fx.all'] = MagicMock()
sys.modules['loguru'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['moviepy.audio'] = MagicMock()
sys.modules['moviepy.audio.io'] = MagicMock()
sys.modules['moviepy.audio.io.ffmpeg_audiowriter'] = MagicMock()
sys.modules['moviepy.audio.AudioClip'] = MagicMock()
sys.modules['moviepy.config'] = MagicMock()
sys.modules['imageio_ffmpeg'] = MagicMock()
sys.modules['whisper'] = MagicMock()

# Set version
sys.modules['moviepy'].__version__ = "1.0.3"

# Define Original classes
class OriginalCompositeAudioClip:
    def __init__(self, clips, *args, **kwargs):
        self.clips = clips
        # Simulate crash if None is passed (MoviePy behavior)
        for c in clips:
            if c is None:
                raise ValueError("OriginalCompositeAudioClip: Clip contains None components")

def original_concatenate_audioclips(clips, *args, **kwargs):
    for c in clips:
        if c is None:
            raise ValueError("original_concatenate_audioclips: Clip contains None components")
    return MagicMock(name="ConcatenatedAudioClip")

# Assign to mock module
mock_mp_editor.CompositeAudioClip = OriginalCompositeAudioClip
mock_mp_editor.concatenate_audioclips = original_concatenate_audioclips

# Also mock Video classes to avoid import errors
mock_mp_editor.CompositeVideoClip = MagicMock()
mock_mp_editor.concatenate_videoclips = MagicMock()
mock_mp_editor.VideoFileClip = MagicMock()
mock_mp_editor.AudioFileClip = MagicMock()
mock_mp_editor.TextClip = MagicMock()
mock_mp_editor.ImageClip = MagicMock()

# --- 2. IMPORT TO TRIGGER MONKEYPATCH ---
print("Importing src.video_editor...")
try:
    import src.video_editor
    print("Import successful.")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# --- 3. VERIFY IF AUDIO CLASSES ARE PATCHED ---
CurrentCompositeAudio = mock_mp_editor.CompositeAudioClip
print(f"Current CompositeAudioClip Class: {CurrentCompositeAudio.__name__}")

# --- 4. TEST WITH NONE ---
def run_test():
    print("TESTING...")
    clip1 = MagicMock(name="AudioClip1")
    clip1.duration = 5.0
    
    try:
        comp = CurrentCompositeAudio([clip1, None])
        print("SUCCESS: Created SafeCompositeAudioClip")
    except ValueError as e:
        print(f"FAILURE: Crashed with ValueError: {e}")
    except Exception as e:
        print(f"FAILURE: Crashed with {type(e).__name__}: {e}")

if __name__ == "__main__":
    run_test()
