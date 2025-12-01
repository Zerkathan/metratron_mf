import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock moviepy to avoid import errors if environment is mismatched
sys.modules["moviepy"] = MagicMock()
sys.modules["moviepy.editor"] = MagicMock()
sys.modules["moviepy.video"] = MagicMock()
sys.modules["moviepy.video.VideoClip"] = MagicMock()
sys.modules["moviepy.audio"] = MagicMock()
sys.modules["moviepy.audio.AudioClip"] = MagicMock()
sys.modules["moviepy.video.fx"] = MagicMock()
sys.modules["moviepy.video.fx.all"] = MagicMock()
sys.modules["moviepy.audio.fx"] = MagicMock()
sys.modules["moviepy.audio.fx.all"] = MagicMock()
sys.modules["moviepy.audio.io"] = MagicMock()
sys.modules["moviepy.audio.io.ffmpeg_audiowriter"] = MagicMock()
sys.modules["moviepy.video.compositing"] = MagicMock()
sys.modules["moviepy.video.compositing.CompositeVideoClip"] = MagicMock()
sys.modules["moviepy.video.compositing.concatenate"] = MagicMock()
sys.modules["moviepy.audio.io.AudioFileClip"] = MagicMock()
sys.modules["imageio_ffmpeg"] = MagicMock()
sys.modules["whisper"] = MagicMock()

# Add src to path
sys.path.append(os.path.abspath("src"))

from music_manager import MusicManager
# Now import VideoEditor (it will use mocks)
from video_editor import VideoEditor

def test_music_manager():
    print("--- Testing MusicManager ---")
    mm = MusicManager()
    
    test_cases = [
        ("💀 Horror / Creepypasta", "horror"),
        ("Music for study", "general"), # Should map to general via "music" keyword
        ("Relaxing Lofi", "lofi"),
        ("Tech News", "tech"),
        ("Unknown Style", "general"),
    ]
    
    for style, expected in test_cases:
        normalized = mm._normalize_style(style)
        # Remove emojis for safe printing
        style_safe = style.encode('ascii', 'ignore').decode('ascii')
        print(f"Style: '{style_safe}' -> Normalized: '{normalized}' (Expected: '{expected}')")
        if normalized != expected:
            print(f"FAILED: Expected '{expected}', got '{normalized}'")
        else:
            print("PASS")

    # Test absolute path
    print("\n--- Testing get_random_music Absolute Path ---")
    # Create a dummy file to find
    dummy_dir = Path("assets/music/general")
    dummy_dir.mkdir(parents=True, exist_ok=True)
    dummy_file = dummy_dir / "test_audio.mp3"
    dummy_file.touch()
    
    music_path = mm.get_random_music("general")
    if music_path:
        print(f"Music Path: {music_path}")
        if os.path.isabs(music_path):
            print("PASS: Path is absolute")
        else:
            print("FAILED: Path is NOT absolute")
    else:
        print("No music found (might be expected if no files)")

    # Clean up
    if dummy_file.exists():
        dummy_file.unlink()

def test_video_editor_syntax():
    print("\n--- Testing VideoEditor Syntax ---")
    try:
        ve = VideoEditor()
        print("VideoEditor initialized successfully (Syntax is correct)")
    except Exception as e:
        print(f"FAILED to initialize VideoEditor: {e}")

if __name__ == "__main__":
    test_music_manager()
    test_video_editor_syntax()
