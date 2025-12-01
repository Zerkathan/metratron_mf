import sys
import unittest
from unittest.mock import MagicMock

# --- 1. SETUP MOCKS BEFORE IMPORTING ---
# Mock EVERYTHING that src.video_editor imports
mock_mp_editor = MagicMock()
sys.modules['moviepy'] = MagicMock()
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

# Define the "Original" classes that src.video_editor will patch
class OriginalCompositeVideoClip:
    def __init__(self, clips, *args, **kwargs):
        self.clips = clips
        # Simulate crash if None is passed
        for c in clips:
            if c is None:
                raise ValueError("Original: Clip contains None components")

def original_concatenate(clips, *args, **kwargs):
    for c in clips:
        if c is None:
            raise ValueError("Original: Clip contains None components")
    return MagicMock(name="ConcatenatedClip")

# Assign these to the mock module so src.video_editor sees them
mock_mp_editor.CompositeVideoClip = OriginalCompositeVideoClip
mock_mp_editor.concatenate_videoclips = original_concatenate

# --- 2. IMPORT TO TRIGGER MONKEYPATCH ---
print("Importing src.video_editor to trigger monkeypatch...")
try:
    import src.video_editor
    print("Import successful.")
except ImportError as e:
    print(f"Import failed: {e}")
    # Don't exit, we want to see if tests fail (they will if import failed)

# --- 3. VERIFY PATCH APPLICATION ---
# Check if the classes on the mock module have been replaced
CurrentComposite = mock_mp_editor.CompositeVideoClip
CurrentConcatenate = mock_mp_editor.concatenate_videoclips

print(f"Current CompositeVideoClip: {CurrentComposite}")
print(f"Current concatenate_videoclips: {CurrentConcatenate}")

if CurrentComposite == OriginalCompositeVideoClip:
    print("[FAIL] CompositeVideoClip was NOT patched!")
else:
    print("[OK] CompositeVideoClip was patched.")

if CurrentConcatenate == original_concatenate:
    print("[FAIL] concatenate_videoclips was NOT patched!")
else:
    print("[OK] concatenate_videoclips was patched.")

# --- 4. RUN TESTS ---
def run_verification():
    print("\nVERIFYING MONKEYPATCH LOGIC")
    print("===========================")
    
    clip1 = MagicMock(name="Clip1")
    clip1.get_frame = MagicMock()
    
    # Test 1: CompositeVideoClip with None
    print("\n[TEST 1] CompositeVideoClip([Clip1, None])")
    try:
        # This should call the SafeCompositeVideoClip (the patch)
        comp = CurrentComposite([clip1, None])
        print(f"   [OK] Success! Created object.")
        # Verify it filtered the None
        if len(comp.clips) == 1 and comp.clips[0] == clip1:
             print("   [OK] Correctly filtered to 1 clip")
        else:
             print(f"   [WARN] Unexpected clip count: {len(comp.clips)}")
    except Exception as e:
        print(f"   [FAIL] Crashed: {e}")

    # Test 2: concatenate_videoclips with None
    print("\n[TEST 2] concatenate_videoclips([Clip1, None])")
    try:
        res = CurrentConcatenate([clip1, None])
        print(f"   [OK] Success! Result: {res}")
    except Exception as e:
        print(f"   [FAIL] Crashed: {e}")

if __name__ == "__main__":
    run_verification()
