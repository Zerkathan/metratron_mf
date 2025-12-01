import sys
import unittest
from unittest.mock import MagicMock, patch

# --- MOCK DEPENDENCIES ---
sys.modules['moviepy'] = MagicMock()
sys.modules['moviepy.editor'] = MagicMock()
sys.modules['moviepy.video.VideoClip'] = MagicMock()
sys.modules['moviepy.video.fx'] = MagicMock()
sys.modules['moviepy.video.fx.all'] = MagicMock()
sys.modules['moviepy.audio.io.ffmpeg_audiowriter'] = MagicMock()
sys.modules['moviepy.audio.AudioClip'] = MagicMock()
sys.modules['imageio_ffmpeg'] = MagicMock()
sys.modules['whisper'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['loguru'] = MagicMock()

from moviepy.editor import CompositeAudioClip
from moviepy.audio.AudioClip import AudioClip

# Mock logger
logger = MagicMock()

# --- COPIED LOGIC FROM src/video_editor.py ---
def is_valid_audio_clip(clip) -> bool:
    """
    Valida estrictamente un clip de audio.
    Retorna False si es None, tiene duración 0/None, o le falta make_frame.
    """
    if clip is None:
        return False
    if not hasattr(clip, 'duration'):
        return False
    if clip.duration is None or clip.duration <= 0:
        return False
    if not hasattr(clip, 'make_frame'):
        return False
    return True

def test_composite_logic_strict(original_audio_clip, music_clip, case_name):
    print(f"\n[TEST CASE]: {case_name}")
    print(f"   Input: original={original_audio_clip}, music={music_clip}")
    
    # --- LOGIC COPIED FROM src/video_editor.py (Updated) ---
    # FIX BLINDADO: Validacion estricta + Fallback a silencio
    lista_audios_cruda = [original_audio_clip, music_clip]
    audio_clips_validos = [c for c in lista_audios_cruda if is_valid_audio_clip(c)]

    if not audio_clips_validos:
        print("   [WARN] No valid clips. Creating silence fallback.")
        try:
            # Crear silencio de emergencia
            make_frame_silence = lambda t: [0] * 2
            silence = AudioClip(make_frame_silence, duration=1.0)
            # Mocking silence clip properties for test
            silence.duration = 1.0
            silence.make_frame = make_frame_silence
            audio_clips_validos = [silence]
        except Exception as e_silence:
            print(f"   [ERR] Error creating silence: {e_silence}")
            audio_clips_validos = []

    final_audio = None
    if len(audio_clips_validos) >= 2:
        print("   [OK] Action: Creating CompositeAudioClip with valid clips")
        final_audio = CompositeAudioClip(audio_clips_validos)
    elif len(audio_clips_validos) == 1:
        print("   [WARN] Action: Using single valid clip (Composite avoided)")
        final_audio = audio_clips_validos[0]
    else:
        print("   [ERR] Action: Imposible crear audio")
        final_audio = None
    # ---------------------------------------------------------------
    
    return final_audio

def run_tests():
    print("STARTING DYNAMIC VERIFICATION OF STRICT Audio PROTECTION")
    print("========================================================")
    
    # Define mock objects
    class ValidClip:
        def __init__(self, name, duration=10): 
            self.name = name
            self.duration = duration
        def make_frame(self, t): return [0, 0]
        def __repr__(self): return f"<Clip:{self.name}>"

    class InvalidClipNoDuration:
        def __init__(self, name): self.name = name
        def make_frame(self, t): return [0, 0]
        def __repr__(self): return f"<InvalidNoDur:{self.name}>"

    class InvalidClipZeroDuration:
        def __init__(self, name): 
            self.name = name
            self.duration = 0
        def make_frame(self, t): return [0, 0]
        def __repr__(self): return f"<InvalidZeroDur:{self.name}>"

    class InvalidClipNoMakeFrame:
        def __init__(self, name): 
            self.name = name
            self.duration = 10
        def __repr__(self): return f"<InvalidNoMF:{self.name}>"

    clip1 = ValidClip("Voice")
    clip2 = ValidClip("Music")
    
    invalid_no_dur = InvalidClipNoDuration("NoDur")
    invalid_zero_dur = InvalidClipZeroDuration("ZeroDur")
    invalid_no_mf = InvalidClipNoMakeFrame("NoMF")
    none_obj = None

    # 1. Normal Case
    result = test_composite_logic_strict(clip1, clip2, "Normal Case (Both Valid)")
    if isinstance(result, MagicMock):
        print("   RESULT: SUCCESS (Composite created)")
    else:
        print(f"   RESULT: FAILED (Expected Composite, got {result})")

    # 2. Zombie Clip (Duration 0)
    result = test_composite_logic_strict(clip1, invalid_zero_dur, "Zombie Case (One has 0 duration)")
    if result == clip1:
        print("   RESULT: SUCCESS (Filtered out zombie, used valid clip)")
    else:
        print(f"   RESULT: FAILED (Expected clip1, got {result})")

    # 3. Corrupt Clip (No make_frame)
    result = test_composite_logic_strict(clip1, invalid_no_mf, "Corrupt Case (One has no make_frame)")
    if result == clip1:
        print("   RESULT: SUCCESS (Filtered out corrupt, used valid clip)")
    else:
        print(f"   RESULT: FAILED (Expected clip1, got {result})")

    # 4. Total Failure (All Invalid) -> Silence Fallback
    result = test_composite_logic_strict(invalid_zero_dur, none_obj, "Total Failure Case (All invalid)")
    # Should return a silence clip (AudioClip instance)
    if isinstance(result, MagicMock) or (hasattr(result, 'duration') and result.duration == 1.0):
         print("   RESULT: SUCCESS (Created silence fallback)")
    else:
         print(f"   RESULT: FAILED (Expected Silence Fallback, got {result})")

    print("\n========================================================")
    print("VERIFICATION COMPLETE")

if __name__ == "__main__":
    run_tests()
