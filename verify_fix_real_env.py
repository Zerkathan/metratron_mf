import sys
import os
import io

# FORCE UTF-8 STDOUT
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure we can import src
sys.path.append(os.getcwd())

print("Importing src.video_editor...")
try:
    import src.video_editor
    print("Import successful.")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

def run_test():
    print("\nTESTING SafeCompositeVideoClip IN REAL ENVIRONMENT")
    print("================================================")
    
    # Check if patched
    if hasattr(src.video_editor.CompositeVideoClip, '__name__'):
        print(f"Class Name: {src.video_editor.CompositeVideoClip.__name__}")
    
    # Create a dummy clip (ColorClip)
    from moviepy.editor import ColorClip
    clip1 = ColorClip(size=(100, 100), color=(255, 0, 0), duration=1.0)
    
    # Test: List with None
    clips = [clip1, None]
    print(f"\nAttempting to create CompositeVideoClip with {len(clips)} items (one is None)...")
    
    try:
        # This should use the patched class
        comp = src.video_editor.CompositeVideoClip(clips)
        print(f"[SUCCESS] Created CompositeVideoClip without crashing.")
        print(f"   Result duration: {comp.duration}")
        print(f"   Number of clips: {len(comp.clips)}")
        
        if len(comp.clips) == 1:
            print("[CORRECT] None clip was filtered out.")
        else:
            print(f"[WARNING] Expected 1 clip, got {len(comp.clips)}")
            
    except Exception as e:
        print(f"[FAILED] Crashed with error: {e}")
        import traceback
        traceback.print_exc()

    print("\nTESTING SafeCompositeAudioClip IN REAL ENVIRONMENT")
    print("================================================")
    
    # Check if patched
    if hasattr(src.video_editor.CompositeAudioClip, '__name__'):
        print(f"Class Name: {src.video_editor.CompositeAudioClip.__name__}")
    
    # Create a dummy audio clip (Silence)
    from moviepy.audio.AudioClip import AudioClip
    make_frame_silence = lambda t: [0] * 2
    audio_clip1 = AudioClip(make_frame_silence, duration=1.0)
    
    # Test: List with None
    audio_clips = [audio_clip1, None]
    print(f"\nAttempting to create CompositeAudioClip with {len(audio_clips)} items (one is None)...")
    
    try:
        # This should use the patched class
        comp_audio = src.video_editor.CompositeAudioClip(audio_clips)
        print(f"[SUCCESS] Created CompositeAudioClip without crashing.")
        print(f"   Result duration: {comp_audio.duration}")
        
        # Verify filtering (CompositeAudioClip stores clips in .clips?)
        # Actually CompositeAudioClip might not expose .clips easily or it might be different
        # But if it didn't crash, it's a success.
            
    except Exception as e:
        print(f"[FAILED] Crashed with error: {e}")
        import traceback
        traceback.print_exc()

    print("\nTESTING DEEP MONKEYPATCH (SOURCE MODULES)")
    print("=========================================")
    
    import moviepy.video.compositing.CompositeVideoClip as mp_cvc
    import moviepy.audio.AudioClip as mp_audio
    
    print(f"Source CompositeVideoClip: {mp_cvc.CompositeVideoClip.__name__}")
    if mp_cvc.CompositeVideoClip.__name__ == 'SafeCompositeVideoClip':
        print("[SUCCESS] Source CompositeVideoClip is patched!")
    else:
        print("[FAILURE] Source CompositeVideoClip is NOT patched!")

    print(f"Source CompositeAudioClip: {mp_audio.CompositeAudioClip.__name__}")
    if mp_audio.CompositeAudioClip.__name__ == 'SafeCompositeAudioClip':
        print("[SUCCESS] Source CompositeAudioClip is patched!")
    else:
        print("[FAILURE] Source CompositeAudioClip is NOT patched!")

if __name__ == "__main__":
    run_test()
