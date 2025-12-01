import sys
import os
import io

# FORCE UTF-8 STDOUT
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure we can import src
sys.path.append(os.getcwd())

try:
    from moviepy.editor import ColorClip, concatenate_videoclips, AudioClip
    import numpy as np
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

def make_silence(duration):
    return AudioClip(lambda t: [0, 0], duration=duration)

def run_test():
    print("\nTESTING AUDIO SANITIZATION LOGIC")
    print("================================")
    
    # 1. Create Clip WITH Audio
    print("Creating Clip 1 (With Audio)...")
    clip1 = ColorClip(size=(100, 100), color=(255, 0, 0), duration=2.0)
    # Add dummy audio
    make_frame_audio = lambda t: [np.sin(440 * 2 * np.pi * t), np.sin(440 * 2 * np.pi * t)]
    clip1.audio = AudioClip(make_frame_audio, duration=2.0)
    
    # 2. Create Clip WITHOUT Audio (Mute)
    print("Creating Clip 2 (Mute)...")
    clip2 = ColorClip(size=(100, 100), color=(0, 255, 0), duration=2.0)
    # clip2.audio is None by default
    
    # 3. Test Concatenation WITHOUT Sanitization (Might Crash or Warn)
    print("\nAttempting concatenation WITHOUT sanitization (Mixed Audio/Mute)...")
    try:
        # Note: MoviePy might handle this gracefully in some versions, but user reported crash
        final = concatenate_videoclips([clip1, clip2], method="compose")
        print("[WARNING] Concatenation succeeded without sanitization (Unexpected based on user report, but maybe MoviePy handled it?)")
        # Check if final clip has audio
        if final.audio:
            print("   Result has audio.")
        else:
            print("   Result has NO audio.")
    except Exception as e:
        print(f"[EXPECTED FAILURE] Concatenation crashed: {e}")

    # 4. Test Concatenation WITH Sanitization
    print("\nAttempting concatenation WITH sanitization (Adding Silence)...")
    try:
        # Sanitize clip2
        if clip2.audio is None:
            print(f"   Sanitizing Clip 2: Adding silence of {clip2.duration}s")
            clip2.audio = make_silence(clip2.duration)
        
        final_sanitized = concatenate_videoclips([clip1, clip2], method="compose")
        print("[SUCCESS] Concatenation succeeded with sanitization!")
        print(f"   Result duration: {final_sanitized.duration}")
        if final_sanitized.audio:
            print("   Result has audio.")
        
    except Exception as e:
        print(f"[FAILED] Concatenation crashed even with sanitization: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
