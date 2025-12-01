import sys
from unittest.mock import MagicMock

# Mock modules
sys.modules['moviepy'] = MagicMock()
sys.modules['moviepy.editor'] = MagicMock()
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

print("Importing src.video_editor...")
try:
    import src.video_editor
    print("Import successful.")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
