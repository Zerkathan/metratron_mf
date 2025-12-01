import sys
import inspect
import moviepy.editor as mp
import moviepy.video.compositing.CompositeVideoClip as cvc
import moviepy.video.compositing.concatenate as concat
import moviepy.audio.AudioClip as ac

print("Checking MoviePy Structure...")
try:
    print(f"moviepy version: {mp.__version__}")
except:
    import moviepy
    print(f"moviepy version: {moviepy.__version__}")

print(f"CompositeVideoClip defined in: {inspect.getmodule(mp.CompositeVideoClip).__name__}")
print(f"concatenate_videoclips defined in: {inspect.getmodule(mp.concatenate_videoclips).__name__}")
print(f"CompositeAudioClip defined in: {inspect.getmodule(mp.CompositeAudioClip).__name__}")
print(f"concatenate_audioclips defined in: {inspect.getmodule(mp.concatenate_audioclips).__name__}")

# Check imports in concatenate module
print("\nChecking imports in moviepy.video.compositing.concatenate:")
try:
    import moviepy.video.compositing.concatenate as c_module
    print(f"CompositeVideoClip in concatenate: {c_module.CompositeVideoClip}")
except Exception as e:
    print(f"Could not check concatenate module: {e}")
