"""
VideoEditor: Maneja la edición y renderizado de videos con subtítulos usando Whisper.
Versión corregida con espera de archivos para OneDrive y rutas absolutas.
"""

import os
import time
import shutil
import tempfile
import subprocess
import unicodedata
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from PIL import Image
    # Compatibilidad con Pillow 10.0+
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    pass

# --- CONFIGURACIÓN FORZADA DE IMAGEMAGICK (ANTES DE IMPORTAR MOVIEPY) ---
# Esto asegura que ImageMagick esté disponible para TextClip desde el inicio
IMAGEMAGICK_BINARY = None

def _configure_imagemagick_global():
    """Configura ImageMagick globalmente antes de importar MoviePy."""
    global IMAGEMAGICK_BINARY
    
    # Intentar importar change_settings (puede no existir en versiones nuevas de MoviePy)
    try:
        from moviepy.config import change_settings
        has_change_settings = True
    except (ImportError, AttributeError):
        has_change_settings = False
    
    # Rutas estándar de ImageMagick en Windows
    imagemagick_paths = [
        r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe",
        r"C:\Program Files\ImageMagick-7.1.0-Q16-HDRI\magick.exe",
        r"C:\Program Files\ImageMagick-7.0.11-Q16-HDRI\magick.exe",
        r"C:\Program Files (x86)\ImageMagick-7.1.1-Q16-HDRI\magick.exe",
        r"C:\Program Files (x86)\ImageMagick-7.1.0-Q16-HDRI\magick.exe",
        r"C:\Program Files (x86)\ImageMagick-7.0.11-Q16-HDRI\magick.exe",
        # Intentar también con rutas comunes sin versión específica
        r"C:\Program Files\ImageMagick\magick.exe",
        r"C:\Program Files (x86)\ImageMagick\magick.exe",
    ]
    
    # Intentar configurar ImageMagick desde rutas estándar
    for path in imagemagick_paths:
        if os.path.exists(path):
            try:
                if has_change_settings:
                    change_settings({"IMAGEMAGICK_BINARY": path})
                else:
                    # Alternativa: configurar variable de entorno
                    os.environ["IMAGEMAGICK_BINARY"] = path
                IMAGEMAGICK_BINARY = path
                print(f"[ImageMagick] OK Configurado: {path}")
                return True
            except Exception as e:
                print(f"[ImageMagick] WARNING Error configurando {path}: {e}")
    
    # Si no se encontró, intentar buscar en PATH del sistema
    try:
        magick_path = shutil.which("magick")
        if magick_path:
            if has_change_settings:
                change_settings({"IMAGEMAGICK_BINARY": magick_path})
            else:
                os.environ["IMAGEMAGICK_BINARY"] = magick_path
            IMAGEMAGICK_BINARY = magick_path
            print(f"[ImageMagick] OK Encontrado en PATH: {magick_path}")
            return True
    except Exception as e:
        print(f"[ImageMagick] WARNING Error buscando en PATH: {e}")
    
    # Si no se encontró, intentar buscar en variables de entorno
    try:
        env_path = os.getenv("IMAGEMAGICK_BINARY") or os.getenv("MAGICK_HOME")
        if env_path:
            # Si es un directorio, agregar magick.exe
            if os.path.isdir(env_path):
                magick_exe = os.path.join(env_path, "magick.exe")
                if os.path.exists(magick_exe):
                    if has_change_settings:
                        change_settings({"IMAGEMAGICK_BINARY": magick_exe})
                    else:
                        os.environ["IMAGEMAGICK_BINARY"] = magick_exe
                    IMAGEMAGICK_BINARY = magick_exe
                    print(f"[ImageMagick] OK Encontrado en variable de entorno: {magick_exe}")
                    return True
            elif os.path.exists(env_path) and env_path.endswith(".exe"):
                if has_change_settings:
                    change_settings({"IMAGEMAGICK_BINARY": env_path})
                else:
                    os.environ["IMAGEMAGICK_BINARY"] = env_path
                IMAGEMAGICK_BINARY = env_path
                print(f"[ImageMagick] OK Encontrado en variable de entorno: {env_path}")
                return True
    except Exception as e:
        print(f"[ImageMagick] WARNING Error buscando en variables de entorno: {e}")
    
    print("[ImageMagick] WARNING ImageMagick no encontrado. Los subtitulos pueden fallar.")
    print("[ImageMagick] INFO Instala ImageMagick desde: https://imagemagick.org/script/download.php")
    print("[ImageMagick] INFO O configura la variable de entorno IMAGEMAGICK_BINARY con la ruta completa a magick.exe")
    return False

# Ejecutar configuración global ANTES de importar MoviePy
_configure_imagemagick_global()

# Ahora sí importamos MoviePy (con ImageMagick ya configurado)
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip,
    TextClip, ImageClip, concatenate_videoclips, concatenate_audioclips
)
from moviepy.video.VideoClip import ColorClip
from moviepy.video.VideoClip import ColorClip
from moviepy.audio.AudioClip import AudioClip
from moviepy.video.fx import all as vfx
from moviepy.audio.fx.all import audio_loop

# --- FIX DE EMERGENCIA PARA NUMPY (Compatibility Patch) ---
import moviepy.audio.io.ffmpeg_audiowriter
import numpy as np

# Sobrescribir la función problemática si es necesario
try:
    from moviepy.audio.AudioClip import AudioClip
    original_to_soundarray = AudioClip.to_soundarray
    
    def patched_to_soundarray(self, tt=None, fps=None, quantize=False, nbytes=2, buffersize=50000):
        if fps is None: 
            fps = self.fps
        try:
            return original_to_soundarray(self, tt, fps, quantize, nbytes, buffersize)
        except (TypeError, ValueError) as e:
            # Si falla por 0-d array o problemas de iteración, forzamos un array válido
            print(f"⚠️ [Numpy Fix] Error en to_soundarray, usando fallback: {e}")
            return np.zeros((1, 2), dtype=np.float32)
            
    AudioClip.to_soundarray = patched_to_soundarray
    print("[Numpy Fix] ✅ Parche de compatibilidad aplicado para AudioClip.to_soundarray")
except Exception as e:
    print(f"⚠️ [Numpy Fix] No se pudo aplicar el parche de Numpy: {e}")
# ---------------------------------------------------------

# --- MONKEYPATCH: BLINDAJE CONTRA CLIPS NONE (Deep Fix) ---
# Este parche intercepta TODAS las llamadas a CompositeVideoClip y concatenate_videoclips
# parcheando directamente los módulos fuente de MoviePy.

import moviepy.editor as mp_editor
import moviepy.video.compositing.CompositeVideoClip as mp_cvc
import moviepy.video.compositing.concatenate as mp_concat
import moviepy.audio.AudioClip as mp_audio

import moviepy.audio.io.AudioFileClip as mp_audio_file

# Guardar referencias originales si no existen ya
if not hasattr(mp_editor, 'OriginalCompositeVideoClip'):
    mp_editor.OriginalCompositeVideoClip = mp_cvc.CompositeVideoClip
if not hasattr(mp_editor, 'OriginalConcatenateVideoclips'):
    mp_editor.OriginalConcatenateVideoclips = mp_concat.concatenate_videoclips
if not hasattr(mp_editor, 'OriginalCompositeAudioClip'):
    mp_editor.OriginalCompositeAudioClip = mp_audio.CompositeAudioClip
if not hasattr(mp_editor, 'OriginalConcatenateAudioclips'):
    mp_editor.OriginalConcatenateAudioclips = mp_audio.concatenate_audioclips
if not hasattr(mp_editor, 'OriginalAudioFileClip'):
    mp_editor.OriginalAudioFileClip = mp_audio_file.AudioFileClip

class SafeCompositeVideoClip(mp_editor.OriginalCompositeVideoClip):
    def __init__(self, clips, *args, **kwargs):
        # Filtrar clips None y validar
        valid_clips = [c for c in clips if c is not None]
        
        # Validación extra: asegurar que tienen get_frame
        valid_clips = [c for c in valid_clips if hasattr(c, 'get_frame')]

        if len(valid_clips) < len(clips):
            print(f"⚠️ [SafeCompositeVideoClip] Se filtraron {len(clips) - len(valid_clips)} clips inválidos/None")
        
        if not valid_clips:
            # Fallback de emergencia: Crear un clip negro de 1 segundo
            print("⚠️ [SafeCompositeVideoClip] No hay clips válidos. Creando fallback negro.")
            from moviepy.video.VideoClip import ColorClip
            # Usar dimensiones estándar si no se pueden inferir
            fallback = ColorClip(size=(1080, 1920), color=(0,0,0), duration=1.0)
            valid_clips = [fallback]
             
        super().__init__(valid_clips, *args, **kwargs)

def safe_concatenate_videoclips(clips, *args, **kwargs):
    # Filtrar clips None
    valid_clips = [c for c in clips if c is not None]
    
    # Validación extra
    valid_clips = [c for c in valid_clips if hasattr(c, 'get_frame')]

    if len(valid_clips) < len(clips):
        print(f"⚠️ [safe_concatenate_videoclips] Se filtraron {len(clips) - len(valid_clips)} clips inválidos/None")
    
    if not valid_clips:
         raise ValueError("safe_concatenate_videoclips: No hay clips válidos para concatenar")
        
    return mp_editor.OriginalConcatenateVideoclips(valid_clips, *args, **kwargs)

class SafeCompositeAudioClip(mp_editor.OriginalCompositeAudioClip):
    def __init__(self, clips, *args, **kwargs):
        # Filtrar clips None
        valid_clips = [c for c in clips if c is not None]
        
        # Validación extra: asegurar que tienen duration (lo mínimo para un audio clip)
        valid_clips = [c for c in valid_clips if hasattr(c, 'duration')]

        if len(valid_clips) < len(clips):
            print(f"⚠️ [SafeCompositeAudioClip] Se filtraron {len(clips) - len(valid_clips)} clips inválidos/None")
        
        if not valid_clips:
            # Fallback de emergencia: Crear silencio de 1 segundo
            print("⚠️ [SafeCompositeAudioClip] No hay clips válidos. Creando silencio de emergencia.")
            from moviepy.audio.AudioClip import AudioClip
            make_frame_silence = lambda t: [0] * 2
            fallback = AudioClip(make_frame_silence, duration=1.0)
            valid_clips = [fallback]
             
        super().__init__(valid_clips, *args, **kwargs)

def safe_concatenate_audioclips(clips, *args, **kwargs):
    # Filtrar clips None
    valid_clips = [c for c in clips if c is not None]
    
    # Validación extra
    valid_clips = [c for c in valid_clips if hasattr(c, 'duration')]

    if len(valid_clips) < len(clips):
        print(f"⚠️ [safe_concatenate_audioclips] Se filtraron {len(clips) - len(valid_clips)} clips inválidos/None")
    
    if not valid_clips:
         raise ValueError("safe_concatenate_audioclips: No hay clips válidos para concatenar")
        
    return mp_editor.OriginalConcatenateAudioclips(valid_clips, *args, **kwargs)

class SafeAudioFileClip(mp_editor.OriginalAudioFileClip):
    """
    Una versión blindada de AudioFileClip que nunca crashea.
    Si el lector falla o el archivo no existe, devuelve silencio.
    """
    def __init__(self, filename, *args, **kwargs):
        self.filename = filename
        try:
            super().__init__(filename, *args, **kwargs)
        except Exception as e:
            print(f"⚠️ Error cargando audio {filename}: {e}. Generando silencio de reemplazo.")
            # Crear un clip mudo de emergencia (5 segundos default)
            # No podemos llamar super().__init__() de nuevo, así que inicializamos manualmente
            # los atributos mínimos necesarios para que funcione como AudioClip
            try:
                # Intentar inicializar AudioClip directamente como fallback
                from moviepy.audio.AudioClip import AudioClip
                # Crear un generador de silencio
                make_frame_silence = lambda t: np.zeros((1, 2), dtype=np.float32)
                # Inicializar con AudioClip (clase base de AudioFileClip)
                AudioClip.__init__(self, make_frame_silence, duration=5.0)
            except Exception:
                # Si incluso eso falla, establecer atributos mínimos manualmente
                self.duration = 5.0
                self.fps = 44100
                self.reader = None
                self.make_frame = lambda t: np.zeros((1, 2), dtype=np.float32)

    def get_frame(self, t):
        # El parche maestro: Si el lector murió, devuelve silencio (0,0)
        if not hasattr(self, 'reader') or self.reader is None:
            return np.zeros((1, 2), dtype=np.float32)
        
        try:
            return super().get_frame(t)
        except Exception:
            return np.zeros((1, 2), dtype=np.float32)

    def close(self):
        try:
            if hasattr(self, 'reader') and self.reader:
                super().close()
        except: 
            pass

# --- APLICAR PARCHES EN MÓDULOS FUENTE ---
# Esto es crucial: parcheamos donde se DEFINEN las clases, no solo donde se importan.

# 1. Patch CompositeVideoClip source
mp_cvc.CompositeVideoClip = SafeCompositeVideoClip
# 2. Patch concatenate_videoclips source
mp_concat.concatenate_videoclips = safe_concatenate_videoclips
# 3. Patch Audio classes source
mp_audio.CompositeAudioClip = SafeCompositeAudioClip
mp_audio.concatenate_audioclips = safe_concatenate_audioclips
# 4. Patch AudioFileClip source
mp_audio_file.AudioFileClip = SafeAudioFileClip

# 5. Patch moviepy.editor for consistency
mp_editor.CompositeVideoClip = SafeCompositeVideoClip
mp_editor.concatenate_videoclips = safe_concatenate_videoclips
mp_editor.CompositeAudioClip = SafeCompositeAudioClip
mp_editor.concatenate_audioclips = safe_concatenate_audioclips
mp_editor.AudioFileClip = SafeAudioFileClip

# CRITICAL: Actualizar también las referencias locales ya importadas
global CompositeVideoClip, concatenate_videoclips, CompositeAudioClip, concatenate_audioclips, AudioFileClip
CompositeVideoClip = SafeCompositeVideoClip
concatenate_videoclips = safe_concatenate_videoclips
CompositeAudioClip = SafeCompositeAudioClip
concatenate_audioclips = safe_concatenate_audioclips
AudioFileClip = SafeAudioFileClip

print("[Monkeypatch] ✅ Blindaje PROFUNDO contra clips None activado (Source Modules Patched + SafeAudioFileClip)")
# ---------------------------------------------------------------

# --- PARCHE DE METRATRON PARA FFMPEG ---
# Esto conecta el FFmpeg interno de Python con el sistema para que Whisper lo vea
FFMPEG_EXE_PATH = None  # Variable global para guardar la ruta de FFmpeg

try:
    import imageio_ffmpeg
    ffmpeg_path = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
    os.environ["PATH"] += os.pathsep + ffmpeg_path
    
    # Guardar la ruta completa del ejecutable para uso posterior
    FFMPEG_EXE_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ["FFMPEG_BINARY"] = FFMPEG_EXE_PATH
    
    # Logging (importar logger antes de usarlo)
    from loguru import logger
    logger.success(f"✅ FFmpeg puenteado exitosamente desde: {ffmpeg_path}")
except ImportError:
    # Importar logger para el warning
    from loguru import logger
    logger.warning("⚠️ No se pudo aplicar el puente de FFmpeg. imageio-ffmpeg no encontrado.")
except Exception as e:
    from loguru import logger
    logger.warning(f"⚠️ No se pudo aplicar el puente de FFmpeg: {e}")

# Ahora sí importamos Whisper seguro
import whisper
# ---------------------------------------


# --- CONFIGURACIÓN DE FORMATO (METRATRON) ---
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
ASPECT_RATIO = TARGET_WIDTH / TARGET_HEIGHT  # 9:16


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


def esperar_archivo(ruta_archivo: str, intentos: int = 30, espera: float = 0.5) -> bool:
    """
    Espera a que un archivo exista y tenga contenido.
    Especialmente importante para archivos en OneDrive que pueden estar sincronizándose.
    
    Args:
        ruta_archivo: Ruta absoluta del archivo a esperar
        intentos: Cuántas veces revisará (30 veces * 0.5s = 15 segundos máx)
        espera: Segundos de espera entre intentos
    
    Returns:
        True si el archivo existe y tiene contenido, False en caso contrario
    """
    logger.info(f"🔍 Buscando archivo: {ruta_archivo}")
    
    # Convertir a Path para normalización
    ruta_archivo_path = Path(ruta_archivo)
    
    for i in range(intentos):
        # 1. Verificar si existe
        if ruta_archivo_path.exists():
            try:
                # 2. Verificar si tiene tamaño (no está vacío)
                size = ruta_archivo_path.stat().st_size
                if size > 0:
                    logger.success(f"✅ Archivo encontrado y listo: {Path(ruta_archivo).name} ({size:,} bytes)")
                    time.sleep(0.3)  # Pausa de seguridad para liberar el 'lock' de OneDrive
                    return True
                else:
                    logger.warning(f"⏳ El archivo existe pero está vacío (Intento {i+1}/{intentos})...")
            except (OSError, PermissionError) as e:
                # OneDrive puede estar bloqueando el archivo temporalmente
                logger.debug(f"⏳ Archivo bloqueado por OneDrive? (Intento {i+1}/{intentos}): {e}")
        else:
            logger.debug(f"⏳ Esperando creación del archivo (Intento {i+1}/{intentos})...")
        
        time.sleep(espera)
    
    logger.error(f"❌ ERROR CRÍTICO: El archivo nunca apareció en: {ruta_archivo}")
    return False


class VideoEditor:
    """Editor de video que genera subtítulos automáticos con Whisper."""
    
    def __init__(self, whisper_model: str = "base", font: str = "Arial"):
        """
        Inicializa el editor de video.
        
        Args:
            whisper_model: Modelo de Whisper a usar (tiny, base, small, medium, large)
            font: Nombre de la fuente para los subtítulos
        """
        # ImageMagick ya está configurado globalmente al inicio del archivo
        # Solo verificamos que esté disponible y funcionando
        self.imagemagick_configured = IMAGEMAGICK_BINARY is not None
        if self.imagemagick_configured:
            logger.success(f"✅ ImageMagick disponible: {IMAGEMAGICK_BINARY}")
            # Verificar que realmente funciona
            try:
                test_clip = TextClip("Test", fontsize=20, color='white').set_duration(0.1)
                test_clip.close()
                logger.success("✅ ImageMagick verificado y funcionando correctamente")
            except Exception as e:
                logger.warning(f"⚠️ ImageMagick configurado pero falló la verificación: {e}")
        else:
            logger.warning("⚠️ ImageMagick no está configurado. Los subtítulos pueden fallar.")
            logger.info("💡 Instala ImageMagick desde: https://imagemagick.org/script/download.php")
        
        # Verificar FFmpeg antes de cargar Whisper
        self.ffmpeg_available = self._check_ffmpeg()
        
        if not self.ffmpeg_available:
            logger.warning("⚠️ FFmpeg no encontrado en PATH. Los subtítulos se generarán sin Whisper.")
            logger.warning("💡 Para habilitar subtítulos, instala FFmpeg: choco install ffmpeg o descarga de gyan.dev")
            self.whisper_model = None
        else:
            logger.info(f"Cargando modelo Whisper: {whisper_model}")
            try:
                self.whisper_model = whisper.load_model(whisper_model)
                logger.success("Modelo Whisper cargado")
            except Exception as e:
                logger.warning(f"No se pudo cargar Whisper: {e}. Continuando sin subtítulos.")
                self.whisper_model = None
        
        # ============================================================
        # CONFIGURACIÓN DE FUENTE PERSONALIZADA
        # ============================================================
        # Buscar fuente personalizada en assets/fonts/viral.ttf
        BASE_DIR = Path(__file__).parent.parent.resolve()
        custom_font_path = BASE_DIR / "assets" / "fonts" / "viral.ttf"
        
        if custom_font_path.exists():
            # Usar fuente personalizada con ruta absoluta
            self.font = str(custom_font_path.resolve())
            logger.success(f"✅ Fuente personalizada cargada: {self.font}")
        else:
            # Usar fuente de sistema por defecto (Arial-Bold para mejor visibilidad)
            self.font = font if font != "Arial" else "Arial-Bold"
            logger.info(f"📝 Usando fuente del sistema: {self.font}")
            logger.info(f"💡 Para usar fuente personalizada, coloca 'viral.ttf' en: assets/fonts/")
        
        # Guardar ruta de fuente personalizada para referencia
        self.custom_font_path = custom_font_path if custom_font_path.exists() else None
        logger.info(f"VideoEditor inicializado (font: {self.font})")
    
    @staticmethod
    def _normalize_style_slug(style_name: Optional[str]) -> str:
        if not style_name:
            return "general"
        normalized = unicodedata.normalize("NFKD", style_name)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
        ascii_text = ascii_text.replace("/", " ")
        tokens = [t for t in re.split(r"[^a-z0-9]+", ascii_text) if t]
        return tokens[0] if tokens else "general"
    
    @staticmethod
    def _resolve_branding_asset(style_slug: str, filename: str) -> Optional[Path]:
        """
        Resuelve la ruta de un asset de branding.
        Busca en este orden:
        1. assets/branding/filename (directamente en la raíz)
        2. assets/branding/{style_slug}/filename (subcarpeta del estilo)
        3. assets/branding/general/filename (carpeta general)
        """
        base_dir = Path("assets/branding")
        if not base_dir.exists():
            return None
        
        # 1. Buscar directamente en assets/branding/ (prioridad máxima)
        root_path = base_dir / filename
        if root_path.exists():
            return root_path
        
        # 2. Buscar en subcarpeta del estilo específico
        if style_slug and style_slug != "general":
            style_path = base_dir / style_slug / filename
            if style_path.exists():
                return style_path
        
        # 3. Buscar en carpeta general como fallback
        general_path = base_dir / "general" / filename
        if general_path.exists():
            return general_path
        
        return None
    
    def _load_branding_text(self, style_slug: str, filename: str) -> Optional[str]:
        asset_path = self._resolve_branding_asset(style_slug, filename)
        if asset_path:
            try:
                return asset_path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                logger.warning(f"⚠️ No se pudo leer {asset_path}: {exc}")
        return None
    
    def _verify_imagemagick(self):
        """Verifica que ImageMagick esté configurado correctamente."""
        global IMAGEMAGICK_BINARY
        
        if IMAGEMAGICK_BINARY and os.path.exists(IMAGEMAGICK_BINARY):
            try:
                # Intentar crear un TextClip de prueba para verificar que funciona
                test_clip = TextClip("Test", fontsize=20, color='white').set_duration(0.1)
                test_clip.close()
                logger.success("✅ ImageMagick verificado y funcionando correctamente")
                return True
            except Exception as e:
                logger.warning(f"⚠️ ImageMagick configurado pero falló la verificación: {e}")
                return False
        else:
            logger.warning("⚠️ ImageMagick no está disponible. Los subtítulos no funcionarán.")
            return False
    
    def _check_ffmpeg(self) -> bool:
        """
        Verifica si FFmpeg está disponible en el sistema.
        Usa el FFmpeg vinculado por Metratron si está disponible.
        
        Returns:
            True si FFmpeg está disponible, False en caso contrario
        """
        try:
            # Si tenemos la ruta del FFmpeg de imageio_ffmpeg, usarla directamente
            if FFMPEG_EXE_PATH and os.path.exists(FFMPEG_EXE_PATH):
                result = subprocess.run(
                    [FFMPEG_EXE_PATH, "-version"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                if result.returncode == 0:
                    logger.success(f"✅ FFmpeg verificado: {FFMPEG_EXE_PATH}")
                    return True
            
            # Intentar buscar en el PATH (por si acaso ya estaba instalado)
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                logger.success("✅ FFmpeg encontrado en PATH del sistema")
                return True
                
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
            logger.debug(f"FFmpeg no encontrado: {e}")
            return False
    
    def _resize_to_format(self, clip: VideoFileClip, target_width: int, target_height: int) -> VideoFileClip:
        """
        Redimensiona un clip de video al formato y resolución especificados.
        Usa Smart Crop para llenar la pantalla vertical sin deformar el contenido.
        
        Args:
            clip: Clip de video a redimensionar
            target_width: Ancho objetivo (ej: 1080)
            target_height: Alto objetivo (ej: 1920)
        
        Returns:
            Clip redimensionado al formato especificado
        """
        try:
            original_width, original_height = clip.size
            target_aspect = target_width / target_height  # 9/16 para vertical
            
            logger.debug(f"🎬 Smart Crop: {original_width}x{original_height} -> {target_width}x{target_height}")
            
            # Si el video ya está en el formato correcto
            if abs(original_width - target_width) < 10 and abs(original_height - target_height) < 10:
                logger.debug("✅ Video ya está en formato correcto, omitiendo redimensionamiento")
                return clip
            
            # LÓGICA DE SMART CROP: Llenado vertical inteligente
            clip_aspect = original_width / original_height
            
            if clip_aspect > target_aspect:
                # Es más ancho (horizontal): Ajustar por altura y recortar el centro exacto
                logger.debug(f"📐 Video más ancho que target ({clip_aspect:.2f} > {target_aspect:.2f}), ajustando por altura")
                clip = clip.resize(height=target_height)
                # Recortar el centro exacto horizontalmente
                clip = clip.crop(x_center=clip.w/2, width=target_width, height=target_height)
                logger.debug(f"✅ Crop horizontal aplicado: {clip.size}")
            else:
                # Es más alto o igual: Ajustar por ancho y recortar el centro vertical
                logger.debug(f"📐 Video más alto o igual ({clip_aspect:.2f} <= {target_aspect:.2f}), ajustando por ancho")
                clip = clip.resize(width=target_width)
                # Recortar el centro vertical (centro exacto, mostrando lo importante)
                clip = clip.crop(y_center=clip.h/2, width=target_width, height=target_height)
                logger.debug(f"✅ Crop vertical aplicado: {clip.size}")
            
            # Asegurar tamaño exacto (por si hubo algún redondeo)
            if abs(clip.w - target_width) > 5 or abs(clip.h - target_height) > 5:
                clip = clip.resize((target_width, target_height))
            
            logger.success(f"✅ Video redimensionado exitosamente: {clip.size}")
            return clip
            
        except Exception as e:
            logger.warning(f"⚠️ Error redimensionando video con Smart Crop, usando método fallback: {e}")
            # Fallback: método simple
            try:
                clip = clip.resize((target_width, target_height))
                return clip
            except Exception as e2:
                logger.error(f"❌ Error crítico en resize fallback: {e2}")
                return clip
    
    def _resize_to_vertical_format(self, clip: VideoFileClip) -> VideoFileClip:
        """
        Redimensiona un clip de video al formato vertical 9:16 (1080x1920).
        Mantiene compatibilidad con código existente.
        
        Args:
            clip: Clip de video a redimensionar
        
        Returns:
            Clip redimensionado al formato vertical
        """
        return self._resize_to_format(clip, TARGET_WIDTH, TARGET_HEIGHT)
    
    @staticmethod
    def _audio_loop(audio_clip: AudioFileClip, target_duration: float) -> AudioFileClip:
        """
        Hace loop de un clip de audio hasta alcanzar la duración objetivo.
        
        Args:
            audio_clip: Clip de audio a loopear
            target_duration: Duración objetivo en segundos
        
        Returns:
            Clip de audio looped hasta la duración objetivo
        """
        if audio_clip.duration >= target_duration:
            return audio_clip.subclip(0, target_duration)
        
        # Calcular cuántos loops se necesitan
        loops_needed = int(target_duration / audio_clip.duration) + 1
        music_clips = [audio_clip] * loops_needed
        looped = concatenate_audioclips(music_clips).subclip(0, target_duration)
        return looped
    
    def _apply_color_grading(self, clip: VideoFileClip, enable_grading: bool = True) -> VideoFileClip:
        """
        Aplica efectos de color grading profesional al clip.
        
        Args:
            clip: Clip de video a procesar
            enable_grading: Si True, aplica los efectos. Si False, retorna el clip sin modificar
        
        Returns:
            Clip con efectos aplicados
        """
        if not enable_grading:
            return clip
        
        try:
            logger.debug("Aplicando color grading...")
            
            # 1. Corrección de color: Aumentar saturación y contraste sutilmente
            # Intentar usar colorx si está disponible
            try:
                # colorx: factor > 1.0 aumenta saturación/brillo
                clip = clip.fx(vfx.colorx, 1.08)  # Aumento sutil del 8%
            except (AttributeError, TypeError):
                # Si colorx no está disponible, intentar con multiply_color
                try:
                    clip = clip.fx(vfx.multiply_color, 1.08)
                except (AttributeError, TypeError):
                    logger.debug("colorx/multiply_color no disponible, saltando corrección de saturación")
            
            # 2. Aumentar contraste
            try:
                # lum_contrast: (lum, contrast, contrast_thr)
                # lum: luminosidad (0 = sin cambio)
                # contrast: contraste (1.0 = sin cambio, >1.0 = más contraste)
                # contrast_thr: umbral de contraste
                clip = clip.fx(vfx.lum_contrast, 0, 0.08, 1.15)  # Aumento sutil de contraste
            except (AttributeError, TypeError):
                # Si lum_contrast no está disponible, intentar con multiply_contrast
                try:
                    clip = clip.fx(vfx.multiply_contrast, 1.15)
                except (AttributeError, TypeError):
                    logger.debug("lum_contrast/multiply_contrast no disponible, saltando corrección de contraste")
            
            logger.debug("Color grading aplicado exitosamente")
            
        except Exception as e:
            logger.warning(f"Error aplicando color grading: {e}. Continuando sin efectos.")
            # Si falla, retornar el clip original sin modificar
        
        return clip
    
    def create_dynamic_image_clip(
        self,
        image_path: str,
        duration: float,
        target_width: int = 1080,
        target_height: int = 1920,
        zoom_effect: str = "in"
    ) -> VideoFileClip:
        """
        Crea un clip de video animado desde una imagen estática usando efecto Ken Burns.
        
        Efectos aplicados:
        - Zoom In/Out: Recorta la imagen progresivamente (100% -> 110% o viceversa)
        - Pan: Si la imagen es horizontal, la mueve lentamente de izquierda a derecha
        
        Args:
            image_path: Ruta a la imagen (jpg, png)
            duration: Duración del clip en segundos
            target_width: Ancho objetivo del video
            target_height: Alto objetivo del video
            zoom_effect: "in" (zoom hacia adentro) o "out" (zoom hacia afuera)
        
        Returns:
            VideoClip animado que parece video real
        """
        logger.info(f"🎬 Creando clip animado desde imagen: {Path(image_path).name} (duración: {duration:.2f}s)")
        
        try:
            # Cargar la imagen
            base_clip = ImageClip(image_path, duration=duration)
            img_width, img_height = base_clip.size
            
            logger.debug(f"📐 Tamaño original de imagen: {img_width}x{img_height}")
            
            # Calcular relación de aspecto
            img_aspect = img_width / img_height
            target_aspect = target_width / target_height
            
            # Redimensionar imagen para que cubra el canvas completo (puede recortarse)
            # Usar el lado más largo para asegurar cobertura completa
            if img_aspect > target_aspect:
                # Imagen más ancha: ajustar por altura
                scale_factor = target_height / img_height
                new_width = int(img_width * scale_factor)
                new_height = target_height
            else:
                # Imagen más alta: ajustar por ancho
                scale_factor = target_width / img_width
                new_width = target_width
                new_height = int(img_height * scale_factor)
            
            # Redimensionar imagen base
            base_clip = base_clip.resize((new_width, new_height))
            
            # Calcular zoom (110% = 1.1x para zoom in, 0.9x para zoom out)
            zoom_start = 1.0
            zoom_end = 1.1 if zoom_effect == "in" else 0.9
            
            # Determinar si aplicar pan (solo si la imagen es significativamente horizontal)
            pan_enabled = img_aspect > 1.3
            
            # Importar funciones matemáticas
            from math import cos, pi
            
            # Función de zoom progresivo
            def zoom_func(t):
                """Calcula el factor de zoom en el tiempo t."""
                progress = t / duration
                # Interpolación suave (ease-in-out)
                smooth_progress = 0.5 * (1 - cos(pi * progress))
                return zoom_start + (zoom_end - zoom_start) * smooth_progress
            
            # Aplicar zoom usando resize con función de tiempo
            zoomed_clip = base_clip.resize(lambda t: zoom_func(t))
            
            # Aplicar pan si es necesario
            if pan_enabled:
                # Calcular rango de movimiento horizontal
                max_width = int(new_width * zoom_end)
                pan_range = max(0, max_width - target_width)
                
                def pan_func(t):
                    """Calcula la posición X para el pan."""
                    progress = t / duration
                    smooth_progress = 0.5 * (1 - cos(pi * progress))
                    x_pos = pan_range * smooth_progress
                    return x_pos
                
                # Aplicar pan moviendo el clip
                final_clip = zoomed_clip.set_position(lambda t: (pan_func(t), 'center'))
            else:
                # Sin pan, solo centrar
                final_clip = zoomed_clip.set_position('center')
            
            # Recortar al tamaño objetivo
            final_clip = final_clip.crop(
                x_center=final_clip.w / 2,
                y_center=final_clip.h / 2,
                width=target_width,
                height=target_height
            )
            
            # Asegurar tamaño exacto y FPS
            final_clip = final_clip.resize((target_width, target_height))
            final_clip = final_clip.set_duration(duration)
            final_clip = final_clip.set_fps(30)
            
            logger.success(f"✅ Clip animado creado: {duration:.2f}s con efecto Ken Burns (zoom: {zoom_effect}, pan: {'✅' if pan_enabled else '❌'})")
            
            return final_clip
            
        except Exception as e:
            logger.error(f"❌ Error creando clip animado desde imagen: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            # Fallback: crear clip simple sin animación
            try:
                simple_clip = ImageClip(image_path, duration=duration)
                simple_clip = self._resize_to_format(simple_clip, target_width, target_height)
                simple_clip = simple_clip.set_fps(30)
                logger.warning("⚠️ Usando clip simple sin animación como fallback")
                return simple_clip
            except Exception as e2:
                logger.error(f"❌ Error en fallback: {e2}")
                raise
    
    def create_emergency_image(
        self,
        text: str,
        target_width: int = 1080,
        target_height: int = 1920,
        background_color: str = "#1a1a1a",
        output_dir: str = "assets/temp"
    ) -> Optional[str]:
        """
        Crea una imagen de emergencia cuando todos los métodos de obtención de visuales fallan.
        Genera una imagen con fondo de color sólido y texto opcional.
        Esta imagen luego se puede usar con create_dynamic_image_clip para crear un video.
        
        Args:
            text: Texto a mostrar en la imagen (opcional, puede ser vacío)
            target_width: Ancho objetivo del video
            target_height: Alto objetivo del video
            background_color: Color de fondo en formato hexadecimal (ej: "#1a1a1a")
            output_dir: Directorio donde guardar la imagen
        
        Returns:
            Ruta del archivo de imagen creado, o None si falla
        """
        logger.warning(f"🚨 Creando imagen de emergencia...")
        
        try:
            # Crear imagen de fondo usando PIL
            from PIL import Image, ImageDraw, ImageFont
            
            # Crear imagen con color de fondo
            bg_image = Image.new('RGB', (target_width, target_height), background_color)
            
            # Si hay texto, agregarlo a la imagen
            if text and text.strip():
                try:
                    draw = ImageDraw.Draw(bg_image)
                    # Intentar usar fuente del sistema, fallback a default
                    try:
                        font_size = min(80, target_width // 15)
                        # Intentar diferentes fuentes comunes
                        font_paths = [
                            "C:/Windows/Fonts/arial.ttf",
                            "C:/Windows/Fonts/arialbd.ttf",
                            "C:/Windows/Fonts/Arial.ttf",
                            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                        ]
                        font = None
                        for font_path in font_paths:
                            try:
                                if Path(font_path).exists():
                                    font = ImageFont.truetype(font_path, font_size)
                                    break
                            except:
                                continue
                        if font is None:
                            font = ImageFont.load_default()
                    except:
                        font = ImageFont.load_default()
                    
                    # Preparar texto (limitar longitud y dividir en líneas si es necesario)
                    display_text = text.strip()[:150]
                    
                    # Calcular posición centrada
                    # Intentar obtener bbox
                    try:
                        bbox = draw.textbbox((0, 0), display_text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                    except:
                        # Fallback si textbbox no funciona
                        text_width = len(display_text) * (font_size // 2)
                        text_height = font_size
                    
                    x = (target_width - text_width) // 2
                    y = (target_height - text_height) // 2
                    
                    # Dibujar texto con sombra para mejor legibilidad
                    shadow_offset = 3
                    draw.text((x + shadow_offset, y + shadow_offset), display_text, 
                             font=font, fill="#000000", align="center")
                    draw.text((x, y), display_text, 
                             font=font, fill="#FFFFFF", align="center")
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo agregar texto a la imagen de emergencia: {e}")
            
            # Guardar imagen
            output_path_obj = Path(output_dir)
            output_path_obj.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            output_file = output_path_obj / f"emergency_{timestamp}_{hash(text) % 10000}.png"
            bg_image.save(output_file)
            
            logger.success(f"✅ Imagen de emergencia creada: {output_file.name}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"❌ Error creando imagen de emergencia: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # Fallback absoluto: crear imagen simple sin texto
            try:
                from PIL import Image
                bg_image = Image.new('RGB', (target_width, target_height), background_color)
                output_path_obj = Path(output_dir)
                output_path_obj.mkdir(parents=True, exist_ok=True)
                output_file = output_path_obj / f"emergency_fallback_{int(time.time())}.png"
                bg_image.save(output_file)
                logger.warning(f"⚠️ Usando imagen de emergencia simplificada (solo fondo): {output_file.name}")
                return str(output_file)
            except Exception as e2:
                logger.error(f"❌ Error crítico en fallback de emergencia: {e2}")
                return None
    
    def create_emergency_clip(
        self,
        text: str,
        duration: float,
        target_width: int = 1080,
        target_height: int = 1920,
        background_color: str = "#1a1a1a"
    ) -> Optional[VideoFileClip]:
        """
        Crea un clip de emergencia usando MoviePy directamente (ColorClip + TextClip).
        Esta función NO depende de archivos externos, por lo que es más robusta.
        
        Args:
            text: Texto a mostrar en el clip
            duration: Duración del clip en segundos
            target_width: Ancho del video
            target_height: Alto del video
            background_color: Color de fondo en formato hexadecimal (ej: "#1a1a1a")
        
        Returns:
            VideoFileClip con fondo de color y texto, o None si falla
        """
        logger.warning(f"🚨 Creando clip de emergencia con MoviePy (duración: {duration}s)...")
        
        try:
            # Convertir color hexadecimal a RGB
            bg_color_hex = background_color.lstrip('#')
            bg_color_rgb = tuple(int(bg_color_hex[i:i+2], 16) for i in (0, 2, 4))
            
            # Crear ColorClip como fondo
            color_clip = ColorClip(
                size=(target_width, target_height),
                color=bg_color_rgb,
                duration=duration
            )
            
            # Intentar agregar texto si está disponible y el texto no está vacío
            if text and text.strip() and self.imagemagick_configured:
                try:
                    # Preparar texto (limitar longitud)
                    display_text = text.strip()[:100]  # Limitar a 100 caracteres
                    
                    # Calcular tamaño de fuente apropiado
                    fontsize = min(80, target_width // 15)
                    
                    # Crear TextClip
                    text_clip = TextClip(
                        display_text,
                        fontsize=fontsize,
                        color='white',
                        font=self.font if hasattr(self, 'font') else 'Arial-Bold',
                        stroke_color='black',
                        stroke_width=2,
                        method='caption',
                        size=(target_width * 0.9, None),  # 90% del ancho para márgenes
                        align='center'
                    ).set_position('center').set_duration(duration)
                    
                    # Componer ColorClip + TextClip
                    final_clip = CompositeVideoClip([color_clip, text_clip])
                    logger.success(f"✅ Clip de emergencia creado con texto: '{display_text[:50]}...'")
                    return final_clip
                    
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo agregar texto al clip de emergencia: {e}")
                    logger.info("💡 Usando solo ColorClip sin texto...")
                    # Si falla el texto, retornar solo el ColorClip
                    return color_clip
            else:
                # Si no hay texto o ImageMagick no está configurado, retornar solo ColorClip
                if not text or not text.strip():
                    logger.info("💡 Texto vacío, usando solo ColorClip...")
                else:
                    logger.warning("⚠️ ImageMagick no configurado, usando solo ColorClip sin texto...")
                return color_clip
                
        except Exception as e:
            logger.error(f"❌ Error crítico creando clip de emergencia: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # Último recurso: intentar crear un ColorClip mínimo
            try:
                logger.warning("🔄 Intentando crear ColorClip mínimo como último recurso...")
                bg_color_hex = background_color.lstrip('#')
                bg_color_rgb = tuple(int(bg_color_hex[i:i+2], 16) for i in (0, 2, 4))
                minimal_clip = ColorClip(
                    size=(target_width, target_height),
                    color=bg_color_rgb,
                    duration=duration
                )
                logger.success("✅ Clip de emergencia mínimo creado (solo fondo)")
                return minimal_clip
            except Exception as e2:
                logger.error(f"❌ ERROR CRÍTICO: No se pudo crear clip de emergencia ni siquiera mínimo: {e2}")
                return None
    
    def _get_word_timestamps(self, audio_file: str) -> List[Dict[str, Any]]:
        """
        Obtiene los timestamps de palabras usando Whisper.
        Versión robusta que maneja errores de FFmpeg y rutas de OneDrive.
        
        Args:
            audio_file: Ruta del archivo de audio (relativa o absoluta)
        
        Returns:
            Lista de diccionarios con 'word', 'start', 'end' para cada palabra
        """
        # Verificar si Whisper está disponible
        if not self.whisper_model:
            logger.warning("⚠️ Whisper no disponible (FFmpeg no encontrado). Saltando subtítulos.")
            return []
        
        # Verificar FFmpeg antes de intentar transcribir
        if not self.ffmpeg_available:
            logger.warning("⚠️ FFmpeg no encontrado en PATH. Saltando subtítulos.")
            return []
        
        try:
            # Obtener la ruta base del proyecto automáticamente
            BASE_DIR = Path(__file__).parent.parent.resolve()
            
            # Construir la ruta absoluta de forma segura y sanitizada
            audio_path = Path(audio_file)
            
            # Si es relativo, construir la ruta completa
            if not audio_path.is_absolute():
                audio_path = BASE_DIR / "assets" / "temp" / audio_path.name
            else:
                # Ya es absoluta, normalizar y sanitizar
                audio_path = audio_path.resolve()
            
            ruta_audio_abs = os.path.abspath(str(audio_path))
            
            logger.debug(f"Ruta absoluta generada: {ruta_audio_abs}")
            logger.info(f"Transcribiendo audio con Whisper: {Path(ruta_audio_abs).name}")
            
            # ESPERAR A QUE EL ARCHIVO EXISTA Y TENGA CONTENIDO
            if not esperar_archivo(ruta_audio_abs, intentos=30, espera=0.5):
                logger.error(f"Archivo de audio no encontrado después de esperar: {ruta_audio_abs}")
                return []
            
            # Verificación final antes de procesar
            if not Path(ruta_audio_abs).exists():
                logger.error(f"Archivo desapareció después de esperar: {ruta_audio_abs}")
                return []
            
            # SOLUCIÓN 2: Usar tempfile para crear archivo fuera de OneDrive
            # Crear un directorio temporal seguro fuera de OneDrive
            temp_dir_safe = Path(tempfile.gettempdir()) / "autoviral_whisper"
            temp_dir_safe.mkdir(parents=True, exist_ok=True)
            
            # Crear una copia temporal del archivo para Whisper (fuera de OneDrive)
            temp_audio_path = temp_dir_safe / f"whisper_temp_{Path(ruta_audio_abs).name}"
            
            # Limpiar archivos temporales antiguos (más de 1 hora)
            try:
                for old_file in temp_dir_safe.glob("whisper_temp_*"):
                    if old_file.stat().st_mtime < (time.time() - 3600):
                        old_file.unlink()
            except Exception:
                pass
            
            try:
                logger.debug(f"Copiando archivo para Whisper (fuera de OneDrive): {temp_audio_path.name}")
                
                # Copiar el archivo a la ubicación temporal segura
                shutil.copy2(ruta_audio_abs, temp_audio_path)
                
                # Esperar un momento adicional para asegurar que la copia esté lista
                time.sleep(0.3)
                
                # Sanitizar ruta para Whisper (ruta absoluta)
                whisper_path = os.path.abspath(str(temp_audio_path))
                
                logger.info(f"Transcribiendo con Whisper desde copia temporal segura...")
                
                # Transcribir con Whisper usando la copia temporal
                result = self.whisper_model.transcribe(
                    whisper_path,
                    word_timestamps=True,
                    language="es"
                )
                
                logger.success(f"✅ Transcripción completada para: {Path(ruta_audio_abs).name}")
                
            except FileNotFoundError as e:
                # SOLUCIÓN 1: Capturar específicamente el error de FFmpeg
                logger.warning(f"⚠️ FFmpeg no encontrado en PATH, saltando subtítulos.")
                logger.warning(f"💡 Error: {e}")
                logger.warning(f"💡 Instala FFmpeg: choco install ffmpeg o desde gyan.dev")
                return []
            finally:
                # Limpiar el archivo temporal después de la transcripción
                try:
                    if temp_audio_path.exists():
                        time.sleep(0.5)  # Dar tiempo a Whisper para liberar el archivo
                        temp_audio_path.unlink()
                        logger.debug(f"Archivo temporal eliminado: {temp_audio_path.name}")
                except Exception as cleanup_error:
                    logger.warning(f"No se pudo eliminar archivo temporal: {cleanup_error}")
            
            # Procesar las palabras y sus timestamps
            words = []
            if result and "segments" in result:
                for segment in result["segments"]:
                    if "words" in segment:
                        for word_info in segment["words"]:
                            words.append({
                                "word": word_info["word"].strip(),
                                "start": word_info["start"],
                                "end": word_info["end"]
                            })
            
            logger.debug(f"Se extrajeron {len(words)} palabras con timestamps")
            return words
            
        except FileNotFoundError as e:
            # SOLUCIÓN 1: Capturar específicamente errores de archivos no encontrados
            logger.warning(f"⚠️ FFmpeg no encontrado o archivo no accesible. Saltando subtítulos.")
            logger.debug(f"Error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error en transcripción Whisper: {e}")
            logger.error(f"Ruta intentada: {ruta_audio_abs if 'ruta_audio_abs' in locals() else audio_file}")
            logger.warning("Continuando sin subtítulos...")
            return []
    
    def create_subtitles(self, audio_file: str, audio_duration: float) -> List[TextClip]:
        """
        Crea clips de subtítulos basados en la transcripción de Whisper.
        
        Args:
            audio_file: Ruta del archivo de audio
            audio_duration: Duración del audio en segundos
        
        Returns:
            Lista de clips de texto (subtítulos)
        """
        try:
            # Obtener timestamps de palabras
            words = self._get_word_timestamps(audio_file)
            
            if not words:
                logger.warning("No se pudieron generar subtítulos")
                return []
            
            subtitle_clips = []
            current_text = ""
            current_start = 0.0
            max_words_per_line = 4
            
            # Agrupar palabras en líneas de subtítulos
            for i, word_info in enumerate(words):
                word = word_info["word"]
                start = word_info["start"]
                end = word_info["end"]
                
                if i == 0:
                    current_start = start
                    current_text = word
                elif len(current_text.split()) < max_words_per_line:
                    current_text += " " + word
                else:
                    # Crear subtítulo con el texto acumulado (Estilo Viral mejorado)
                    if current_text:
                        try:
                            # Ancho máximo para subtítulos (dejando márgenes laterales)
                            max_width = int(TARGET_WIDTH * 0.9)  # 90% del ancho del video
                            
                            subtitle = TextClip(
                                current_text,
                                fontsize=80,  # Tamaño aumentado para mejor legibilidad y estilo viral
                                color='white',  # Color base: blanco brillante
                                font=self.font,  # Usar fuente personalizada si está disponible
                                stroke_color='black',  # Borde negro para contraste máximo
                                stroke_width=4,  # Borde más grueso para destacar (estilo viral profesional)
                                method='caption',
                                size=(max_width, None),  # Limitar ancho para evitar desbordes
                                align='center'
                            )
                            
                            # Posición mejorada: 75% desde arriba (más seguro para UI de TikTok/Reels)
                            video_height = TARGET_HEIGHT
                            subtitle_y = int(video_height * 0.75)
                            subtitle = subtitle.set_position(lambda t: ('center', subtitle_y), relative=False)
                            subtitle = subtitle.set_start(current_start).set_duration(end - current_start)
                            
                            # VERIFICAR que el clip no sea None antes de agregarlo
                            if subtitle is not None:
                                subtitle_clips.append(subtitle)
                            else:
                                logger.warning(f"TextClip retornó None para texto: {current_text[:50]}...")
                        except Exception as e:
                            logger.warning(f"Error creando subtítulo: {e}")
                            # Continuar sin agregar este subtítulo
            
                    # Iniciar nueva línea
                    current_text = word
                    current_start = start
            
            # Agregar el último subtítulo
            if current_text and words:
                try:
                    last_end = words[-1]["end"]
                    # Ancho máximo para subtítulos (dejando márgenes laterales)
                    max_width = int(TARGET_WIDTH * 0.9)  # 90% del ancho del video
                    
                    subtitle = TextClip(
                        current_text,
                        fontsize=80,  # Tamaño consistente con los demás
                        color='white',
                        font=self.font,
                        stroke_color='black',
                        stroke_width=4,  # Borde grueso consistente
                        method='caption',
                        size=(max_width, None),  # Limitar ancho para evitar desbordes
                        align='center'
                    )
                    
                    # Posición mejorada: 75% desde arriba
                    video_height = TARGET_HEIGHT
                    subtitle_y = int(video_height * 0.75)
                    subtitle = subtitle.set_position(lambda t: ('center', subtitle_y), relative=False)
                    subtitle = subtitle.set_start(current_start).set_duration(last_end - current_start)
                    
                    # VERIFICAR que el clip no sea None antes de agregarlo
                    if subtitle is not None:
                        subtitle_clips.append(subtitle)
                    else:
                        logger.warning(f"TextClip retornó None para último texto: {current_text[:50]}...")
                except Exception as e:
                    logger.warning(f"Error creando último subtítulo: {e}")
            
            # Filtrar cualquier None que pueda haber quedado (defensa adicional)
            subtitle_clips = [clip for clip in subtitle_clips if clip is not None]
            
            if subtitle_clips:
                logger.success(f"✅ Se crearon {len(subtitle_clips)} clips de subtítulos válidos")
            else:
                logger.warning("⚠️ No se crearon clips de subtítulos válidos")
            
            return subtitle_clips
            
        except Exception as e:
            logger.error(f"Error creando subtítulos: {e}")
            return []
    
    def generate_karaoke_subtitles(self, audio_file: str, video_size: tuple = (1080, 1920), highlight_color: str = '#00ff00') -> List[TextClip]:
        """
        Genera subtítulos estilo karaoke con word-level highlighting (Estilo Viral).
        Cada palabra se ilumina cuando se está diciendo con colores vibrantes y bordes gruesos.
        
        Args:
            audio_file: Ruta del archivo de audio
            video_size: Tamaño del video (width, height)
            highlight_color: Color de la palabra activa (default: #00ff00 - Verde Neón o 'yellow')
        
        Returns:
            Lista de clips de texto (una por palabra)
        """
        try:
            # Obtener timestamps de palabras
            logger.info(f"Obteniendo timestamps de palabras para subtítulos karaoke estilo viral...")
            words = self._get_word_timestamps(audio_file)
            
            if not words:
                logger.warning("⚠️ No se pudieron obtener timestamps de palabras. Whisper puede no estar disponible o el audio no es válido.")
                logger.info("💡 Intentando continuar sin subtítulos karaoke...")
                return []
            
            logger.info(f"✅ Se obtuvieron {len(words)} palabras con timestamps para subtítulos karaoke")
            
            width, height = video_size
            subtitle_clips = []
            
            # ============================================================
            # ESTILO VIRAL: Fuentes grandes, bordes gruesos, colores vibrantes
            # ============================================================
            base_fontsize = 85  # Aumentado para mejor legibilidad y estilo más impactante
            highlight_fontsize = int(base_fontsize * 1.35)  # 35% más grande para palabras activas (más dramático)
            base_color = 'white'  # Color base: blanco brillante
            stroke_color = 'black'  # Borde negro para contraste máximo
            stroke_width = 5  # Borde más grueso para destacar (estilo viral profesional mejorado)
            
            # Color vibrante para palabra activa: 'yellow' o '#00ff00' (Verde Neón)
            if highlight_color and highlight_color.lower() in ['yellow', '#00ff00', '#ffd700', '#ffff00']:
                highlight_color_final = highlight_color if highlight_color.startswith('#') else 'yellow'
            else:
                highlight_color_final = '#FFD700'  # Amarillo dorado por defecto (más atractivo que verde)
            
            # Posición mejorada: 75% desde arriba (más seguro para UI)
            y_position = int(height * 0.75)
            
            # Crear un clip de texto temporal para medir anchos (usando fuente personalizada)
            try:
                test_clip = TextClip("M", fontsize=base_fontsize, font=self.font)
                char_width_approx = test_clip.w / len("M") if hasattr(test_clip, 'w') and test_clip.w else base_fontsize * 0.6
                test_clip.close()
            except:
                char_width_approx = base_fontsize * 0.6
            
            # Agrupar palabras en líneas para mostrar contexto
            # Mostrar 3-5 palabras a la vez, destacando la actual
            words_per_line = 5
            current_line_words = []
            
            for i, word_info in enumerate(words):
                word = word_info["word"].strip()
                start = word_info["start"]
                end = word_info["end"]
                duration = end - start
                
                # Agregar palabra a la línea actual
                current_line_words.append({
                    "word": word,
                    "start": start,
                    "end": end,
                    "index": i
                })
                
                # Si tenemos suficientes palabras o es la última, crear la línea
                if len(current_line_words) >= words_per_line or i == len(words) - 1:
                    # Crear clips para cada palabra en la línea
                    # Calcular el ancho total de la línea
                    line_text = " ".join([w["word"] for w in current_line_words])
                    line_width_approx = sum(len(w["word"]) + 1 for w in current_line_words) * char_width_approx
                    
                    # Posición X inicial (centrado)
                    x_start = (width / 2) - (line_width_approx / 2)
                    current_x = x_start
                    
                    for j, w_info in enumerate(current_line_words):
                        w = w_info["word"]
                        w_start = w_info["start"]
                        w_end = w_info["end"]
                        w_duration = w_end - w_start
                        
                        # Determinar si esta palabra está activa (la última de la línea)
                        is_active = (j == len(current_line_words) - 1)
                        
                        # Estilo según si está activa (Estilo Viral: colores vibrantes mejorados)
                        if is_active:
                            fontsize = highlight_fontsize
                            color = highlight_color_final  # Amarillo dorado o verde neón para palabra activa
                            current_stroke_width = 6  # Borde aún más grueso para palabra activa (máximo impacto)
                        else:
                            fontsize = base_fontsize
                            color = base_color  # Blanco para palabras no activas
                            current_stroke_width = stroke_width  # Stroke_width=5 para todas las palabras
                        
                        # Calcular posición X (aproximada basada en ancho de caracteres)
                        word_width_approx = len(w) * char_width_approx
                        x_position = current_x + (word_width_approx / 2)
                        
                        try:
                            # Crear clip de texto para esta palabra (Estilo Viral Mejorado: máximo impacto visual)
                            # Ancho máximo por palabra para evitar desbordes
                            max_word_width = int(width * 0.25)  # Máximo 25% del ancho por palabra
                            
                            word_clip = TextClip(
                                w,
                                fontsize=fontsize,
                                color=color,
                                font=self.font,  # Usar fuente personalizada si está disponible
                                stroke_color=stroke_color,
                                stroke_width=current_stroke_width,  # Borde grueso para contraste máximo
                                method='caption',
                                size=(max_word_width, None),  # Limitar ancho para evitar desbordes
                                align='center'
                            ).set_position((x_position, y_position), relative=False).set_start(w_start).set_duration(w_duration)
                            
                            if word_clip is not None:
                                subtitle_clips.append(word_clip)
                        except Exception as e:
                            logger.warning(f"Error creando clip de palabra '{w}': {e}")
                            # Continuar sin esta palabra
                        
                        # Actualizar posición X para la siguiente palabra
                        current_x += word_width_approx + char_width_approx  # +1 espacio
                    
                    # Limpiar línea actual
                    current_line_words = []
            
            # Filtrar None
            subtitle_clips = [clip for clip in subtitle_clips if clip is not None]
            
            if subtitle_clips:
                logger.success(f"✅ Se crearon {len(subtitle_clips)} clips de subtítulos karaoke")
            else:
                logger.warning("⚠️ No se crearon clips de subtítulos karaoke válidos")
            
            return subtitle_clips
            
        except Exception as e:
            logger.error(f"Error creando subtítulos karaoke: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def create_static_subtitle(self, text: str, duration: float, video_size: tuple = (1080, 1920), position: str = "bottom") -> Optional[TextClip]:
        """
        Crea un subtítulo estático desde texto plano.
        Fallback cuando el karaoke no funciona o no hay audio para transcribir.
        
        Args:
            text: Texto a mostrar
            duration: Duración del subtítulo en segundos
            video_size: Tamaño del video (width, height)
            position: Posición del subtítulo ("bottom", "center", "top")
        
        Returns:
            TextClip o None si falla
        """
        try:
            width, height = video_size
            
            # ============================================================
            # ESTILO VIRAL MEJORADO: Fuentes grandes, bordes gruesos, máximo contraste
            # ============================================================
            fontsize = 80  # Aumentado para mejor legibilidad y estilo más impactante
            color = 'white'  # Color base: blanco brillante
            stroke_color = 'black'  # Borde negro para contraste máximo
            stroke_width = 4  # Borde más grueso para máximo contraste (estilo viral profesional mejorado)
            
            # Posición Y mejorada según el parámetro (evitando cortes en los bordes)
            if position == "bottom":
                y_position = int(height * 0.75)  # 75% desde arriba (más seguro)
            elif position == "center":
                y_position = int(height * 0.5)  # Centro
            else:
                y_position = int(height * 0.18)  # 18% desde arriba (más espacio desde el borde superior)
            
            # Limitar texto a un ancho razonable (90% del ancho para mejor aprovechamiento)
            max_width = int(width * 0.9)
            
            logger.info(f"Creando subtítulo estático estilo viral: '{text[:50]}...' (duración: {duration:.2f}s)")
            
            try:
                subtitle_clip = TextClip(
                    text,
                    fontsize=fontsize,
                    color=color,
                    font=self.font,  # Usar fuente personalizada si está disponible
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,  # Borde grueso para máximo contraste
                    method='caption',
                    size=(max_width, None),
                    align='center'
                ).set_position(('center', y_position), relative=False).set_start(0).set_duration(duration)
                
                if subtitle_clip is not None:
                    logger.success("✅ Subtítulo estático creado exitosamente")
                    return subtitle_clip
                else:
                    logger.warning("⚠️ TextClip retornó None para subtítulo estático")
                    return None
                    
            except Exception as e:
                logger.error(f"Error creando TextClip para subtítulo estático: {e}")
                logger.warning("💡 Asegúrate de que ImageMagick esté instalado y configurado")
                return None
                
        except Exception as e:
            logger.error(f"Error en create_static_subtitle: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def process_scene(self, scene: Dict, idx: int, background_music: Optional[str] = None, music_volume: float = 0.1, use_karaoke: bool = True, target_width: int = None, target_height: int = None, use_subtitles: bool = True, enable_color_grading: bool = False, style_code: Optional[str] = None, style_label: Optional[str] = None) -> Optional[VideoFileClip]:
        """
        Procesa una escena individual combinando video, audio y subtítulos.
        Retorna None si hay un error para evitar crashes.
        
        Args:
            scene: Diccionario con 'text', 'visual_query', 'duration_estimate'
            idx: Índice de la escena (0-based)
            background_music: Ruta opcional a música de fondo
            music_volume: Volumen de la música de fondo (0.0 a 1.0)
            use_karaoke: Si True, usa subtítulos karaoke. Si False, usa subtítulos estáticos
            target_width: Ancho objetivo del video
            target_height: Alto objetivo del video
            use_subtitles: Si True, incrusta subtítulos. Si False, renderiza Clean Feed (sin texto)
            enable_color_grading: Si True, aplica color grading al video
            style_code: Código/nombre interno del estilo (ej: "HORROR")
            style_label: Etiqueta amigable del estilo (ej: "💀 Horror / Creepypasta")
        
        Returns:
            Clip de video procesado o None si hay error
        """
        logger.info(f"Procesando escena {idx + 1}...")
    
        # Obtener la ruta base del proyecto
        BASE_DIR = Path(__file__).parent.parent.resolve()
        
        # --- FIX DE RUTAS: Priorizar rutas del diccionario de escena ---
        # main.py genera archivos con timestamps, así que debemos usar esas rutas si existen.
        
        # 1. Audio Path
        audio_file = scene.get('audio_path')
        if not audio_file:
            # Fallback a ruta construida (solo si no viene en el diccionario)
            audio_file = os.path.abspath(str(BASE_DIR / "assets" / "temp" / f"audio_{idx}.mp3"))
            logger.debug(f"⚠️ Usando ruta de audio fallback: {audio_file}")
        else:
            logger.debug(f"✅ Usando ruta de audio del guion: {audio_file}")

        # 2. Video Path
        video_file = scene.get('video_path')
        if not video_file:
            # Fallback a ruta construida
            video_file = os.path.abspath(str(BASE_DIR / "assets" / "temp" / f"scene_{idx:02d}_video.mp4"))
            logger.debug(f"⚠️ Usando ruta de video fallback: {video_file}")
        else:
            logger.debug(f"✅ Usando ruta de video del guion: {video_file}")
        
        # Verificar que los archivos existen
        if not Path(audio_file).exists():
            logger.error(f"Archivo de audio no encontrado: {audio_file}")
            logger.warning(f"⚠️ Saltando escena {idx + 1} por falta de audio")
            return None
        
        # Verificar si existe video o imagen
        video_path = Path(video_file)
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        is_image = False
        
        if not video_path.exists():
            # Buscar si hay una imagen con el mismo nombre base (solo para el fallback)
            # Si viene del diccionario, asumimos que es la ruta correcta
            for ext in image_extensions:
                image_file = video_path.with_suffix(ext)
                if image_file.exists():
                    video_file = str(image_file)
                    is_image = True
                    logger.info(f"📸 Imagen encontrada en lugar de video: {image_file.name}")
                    break
            
            if not is_image and not video_path.exists():
                logger.error(f"Archivo de video/imagen no encontrado: {video_file}")
                logger.warning(f"⚠️ Saltando escena {idx + 1} por falta de recurso visual")
                return None
        else:
            # Determinar si es imagen por extensión
            if video_path.suffix.lower() in image_extensions:
                is_image = True
            
        original_video_clip = None
        original_audio_clip = None
        
        try:
            # Crear subtítulos ANTES de cargar el audio con MoviePy
            temp_audio_clip = AudioFileClip(audio_file)
            audio_duration = temp_audio_clip.duration
            temp_audio_clip.close()
            
            # Generar subtítulos SOLO si use_subtitles está activado
            subtitle_clips_list = []
            
            if use_subtitles:
                # Generar subtítulos (puede retornar lista vacía o lista con clips válidos)
                # Usar dimensiones dinámicas si se proporcionan
                video_size = (target_width or TARGET_WIDTH, target_height or TARGET_HEIGHT)
                
                if use_karaoke:
                    logger.info(f"Generando subtítulos karaoke para escena {idx + 1}...")
                    subtitle_clips_list = self.generate_karaoke_subtitles(audio_file, video_size=video_size)
                    logger.info(f"Subtítulos karaoke generados: {len(subtitle_clips_list)} clips")
                else:
                    logger.info(f"Generando subtítulos estáticos para escena {idx + 1}...")
                    subtitle_clips_list = self.create_subtitles(audio_file, audio_duration)
                    logger.info(f"Subtítulos estáticos generados: {len(subtitle_clips_list)} clips")
                
                # FILTRAR cualquier None de la lista de subtítulos
                subtitle_clips_list = [clip for clip in subtitle_clips_list if clip is not None]
                
                # FALLBACK: Si no se generaron subtítulos karaoke, intentar con subtítulos estáticos desde el texto
                if not subtitle_clips_list and use_karaoke:
                    logger.warning(f"⚠️ No se generaron subtítulos karaoke para escena {idx + 1}, intentando fallback estático...")
                    scene_text = scene.get("text", "")
                    if scene_text and scene_text.strip():
                        try:
                            static_subtitle = self.create_static_subtitle(
                                text=scene_text.strip(),
                                duration=audio_duration,
                                video_size=video_size,
                                position="bottom"
                            )
                            if static_subtitle:
                                subtitle_clips_list = [static_subtitle]
                                logger.success(f"✅ Subtítulo estático creado como fallback para escena {idx + 1}")
                            else:
                                logger.warning(f"⚠️ Fallback estático también falló para escena {idx + 1}")
                        except Exception as e:
                            logger.warning(f"⚠️ Error en fallback estático para escena {idx + 1}: {e}")
                
                logger.info(f"Total de clips de subtítulos válidos para escena {idx + 1}: {len(subtitle_clips_list)}")
            else:
                logger.info(f"📝 Saltando generación de subtítulos para escena {idx + 1} (Clean Feed activado)")
            
            # Cargar video/audio (o crear clip animado desde imagen)
            if is_image:
                # Crear clip animado desde imagen con efecto Ken Burns
                logger.info(f"🎬 Animando imagen con efecto Ken Burns para escena {idx + 1}...")
                try:
                    original_video_clip = self.create_dynamic_image_clip(
                        image_path=video_file,
                        duration=audio_duration,
                        target_width=final_width,
                        target_height=final_height,
                        zoom_effect="in"  # Zoom in por defecto
                    )
                    if original_video_clip is None:
                        logger.error(f"❌ create_dynamic_image_clip retornó None para escena {idx + 1}")
                        return None
                except Exception as e:
                    logger.error(f"❌ Error creando clip animado para escena {idx + 1}: {e}")
                    return None
            else:
                # Cargar video normal
                try:
                    if not os.path.exists(video_file):
                        logger.error(f"❌ Archivo de video no existe: {video_file}")
                        return None
                    
                    original_video_clip = VideoFileClip(video_file)
                    
                    # VALIDACIÓN CRÍTICA: Verificar que el clip se cargó correctamente
                    if original_video_clip is None:
                        logger.error(f"❌ VideoFileClip retornó None para: {video_file}")
                        return None
                    
                    # Verificar que tiene los métodos necesarios
                    if not hasattr(original_video_clip, 'duration') or not hasattr(original_video_clip, 'get_frame'):
                        logger.error(f"❌ El clip cargado no tiene los atributos necesarios: {video_file}")
                        if original_video_clip:
                            try:
                                original_video_clip.close()
                            except:
                                pass
                        return None
                    
                    # CRÍTICO: Silenciar audio original del video de stock para evitar ruido
                    # El audio se manejará por separado (TTS + música)
                    original_video_clip = original_video_clip.without_audio()
                    logger.debug(f"🔇 Audio original del video de stock silenciado para escena {idx + 1}")
                except Exception as e:
                    logger.error(f"❌ Error cargando video para escena {idx + 1}: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    return None
            
            # VALIDACIÓN FINAL: Verificar que original_video_clip es válido antes de continuar
            if original_video_clip is None:
                logger.error(f"❌ original_video_clip es None después de cargar para escena {idx + 1}")
                return None
            
            # Cargar audio
            try:
                original_audio_clip = AudioFileClip(audio_file)
                if original_audio_clip is None:
                    logger.error(f"❌ AudioFileClip retornó None para: {audio_file}")
                    if original_video_clip:
                        try:
                            original_video_clip.close()
                        except:
                            pass
                    return None
            except Exception as e:
                logger.error(f"❌ Error cargando audio para escena {idx + 1}: {e}")
                if original_video_clip:
                    try:
                        original_video_clip.close()
                    except:
                        pass
                return None
            
            # Ajustar duración del video al audio
            video_duration = original_audio_clip.duration
            
            # VALIDACIÓN: Verificar duración válida antes de usar subclip
            if video_duration <= 0:
                logger.error(f"❌ Duración de audio inválida: {video_duration} para escena {idx + 1}")
                try:
                    original_video_clip.close()
                    original_audio_clip.close()
                except:
                    pass
                return None
            
            # Validar que el clip de video tiene duración válida
            try:
                video_clip_duration = original_video_clip.duration
                if video_clip_duration <= 0:
                    logger.error(f"❌ Duración de video inválida: {video_clip_duration} para escena {idx + 1}")
                    try:
                        original_video_clip.close()
                        original_audio_clip.close()
                    except:
                        pass
                    return None
                
                # Usar la duración mínima entre video y audio
                clip_duration = min(video_duration, video_clip_duration)
                background_clip = original_video_clip.subclip(0, clip_duration)
                
                # VALIDACIÓN POST-SUBCLIP: Verificar que subclip funcionó
                if background_clip is None:
                    logger.error(f"❌ subclip retornó None para escena {idx + 1}")
                    try:
                        original_video_clip.close()
                        original_audio_clip.close()
                    except:
                        pass
                    return None
                    
            except Exception as e:
                logger.error(f"❌ Error procesando duración/subclip para escena {idx + 1}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                try:
                    original_video_clip.close()
                    original_audio_clip.close()
                except:
                    pass
                return None
            
            # --- REDIMENSIONAR AL FORMATO OBJETIVO (dinámico) ---
            final_width = target_width or TARGET_WIDTH
            final_height = target_height or TARGET_HEIGHT
            style_slug = self._normalize_style_slug(style_code or style_label or "general")
            
            # VALIDACIÓN: Verificar que background_clip es válido antes de redimensionar
            if background_clip is None:
                logger.error(f"❌ background_clip es None antes de redimensionar para escena {idx + 1}")
                try:
                    original_video_clip.close()
                    original_audio_clip.close()
                except:
                    pass
                return None
            
            try:
                background_clip = self._resize_to_format(background_clip, final_width, final_height)
                if background_clip is None:
                    logger.error(f"❌ _resize_to_format retornó None para escena {idx + 1}")
                    try:
                        original_video_clip.close()
                        original_audio_clip.close()
                    except:
                        pass
                    return None
                logger.debug(f"Video redimensionado a {final_width}x{final_height} para escena {idx + 1}")
            except Exception as e:
                logger.error(f"❌ Error redimensionando video para escena {idx + 1}: {e}")
                try:
                    original_video_clip.close()
                    original_audio_clip.close()
                except:
                    pass
                return None
            
            # --- APLICAR COLOR GRADING (si está habilitado) ---
            try:
                background_clip = self._apply_color_grading(background_clip, enable_color_grading)
                if background_clip is None:
                    logger.error(f"❌ _apply_color_grading retornó None para escena {idx + 1}")
                    try:
                        original_video_clip.close()
                        original_audio_clip.close()
                    except:
                        pass
                    return None
            except Exception as e:
                logger.error(f"❌ Error aplicando color grading para escena {idx + 1}: {e}")
                # Continuar sin color grading en lugar de fallar completamente
                logger.warning(f"⚠️ Continuando sin color grading para escena {idx + 1}")
            
            # Cargar música de fondo si está disponible (con loop si es necesario)
            # NOTA: El audio se manejará a nivel global en render_final_video
            # Esta sección se mantiene para compatibilidad pero el audio final se procesa globalmente
            final_audio = original_audio_clip
            if background_music and os.path.exists(background_music):
                try:
                    music = AudioFileClip(background_music)
                    
                    # Loopear música si es corta
                    if music.duration < video_duration:
                        music = self._audio_loop(music, video_duration)
                        logger.debug(f"Música looped: {music.duration:.2f}s -> {video_duration:.2f}s")
                    else:
                        music = music.subclip(0, video_duration)
                    
                    # Bajar volumen (Ducking)
                    music = music.volumex(music_volume)
                    
                    # Mezclar con voz (si existe)
                    if original_audio_clip:
                        audio_clips_validos = [c for c in [original_audio_clip, music] if is_valid_audio_clip(c)]
                        
                        if len(audio_clips_validos) >= 2:
                            final_audio = CompositeAudioClip(audio_clips_validos)
                        elif len(audio_clips_validos) == 1:
                            logger.warning("⚠️ Solo un clip de audio válido, usando ese directamente")
                            final_audio = audio_clips_validos[0]
                        else:
                            logger.error("❌ No hay clips de audio válidos")
                            final_audio = None
                    else:
                        final_audio = music
                    
                    music.close()
                except Exception as e:
                    logger.warning(f"Error añadiendo música de fondo: {e}")
            
            # ============================================================
            # FIX: NO AGREGAR AUDIO AQUÍ - Se agregará al final como pista completa
            # ============================================================
            # El audio se manejará a nivel global en render_final_video
            # Solo procesamos el video visual aquí
            
            # LÓGICA DEFENSIVA: Construir layers de forma segura
            layers = [background_clip]  # Clip sin audio
            
            # VERIFICACIÓN: Solo agregar subtítulos si existen y no son None
            if subtitle_clips_list and len(subtitle_clips_list) > 0:
                # Filtrar una vez más por si acaso
                valid_subtitles = [clip for clip in subtitle_clips_list if clip is not None]
                if valid_subtitles:
                    layers.extend(valid_subtitles)
                    logger.debug(f"Agregando {len(valid_subtitles)} clips de subtítulos a la escena {idx + 1}")
                else:
                    logger.warning(f"⚠️ Renderizando escena {idx + 1} sin subtítulos (todos los clips eran None)")
            else:
                logger.warning(f"⚠️ Renderizando escena {idx + 1} sin subtítulos (no se generaron subtítulos)")
            
            # Crear CompositeVideoClip solo con layers válidos (nunca None)
            try:
                # VALIDACIÓN: Verificar que background_clip es válido antes de crear composite
                if background_clip is None:
                    logger.error(f"❌ background_clip es None antes de crear composite para escena {idx + 1}")
                    try:
                        original_video_clip.close()
                        original_audio_clip.close()
                    except:
                        pass
                    return None
                
                if len(layers) > 1:
                    # Hay subtítulos, crear composite
                    # VALIDACIÓN CRÍTICA: Filtrar cualquier None de los layers ANTES de crear composite
                    valid_layers = []
                    for i, layer in enumerate(layers):
                        if layer is None:
                            logger.warning(f"⚠️ Layer {i} es None en escena {idx + 1}, filtrando...")
                            continue
                        # Verificar que tiene los atributos necesarios
                        if not hasattr(layer, 'duration') or not hasattr(layer, 'get_frame'):
                            logger.warning(f"⚠️ Layer {i} no tiene atributos necesarios en escena {idx + 1}, filtrando...")
                            continue
                        valid_layers.append(layer)
                    
                    if len(valid_layers) == 0:
                        logger.error(f"❌ Todos los layers son inválidos para escena {idx + 1}")
                        try:
                            original_video_clip.close()
                            original_audio_clip.close()
                        except:
                            pass
                        return None
                    
                    if len(valid_layers) == 1:
                        # Solo hay un layer válido, usarlo directamente
                        video_clip = valid_layers[0]
                    else:
                        # Crear composite solo con layers válidos
                        video_clip = CompositeVideoClip(valid_layers)
                    
                    if video_clip is None:
                        logger.error(f"❌ CompositeVideoClip retornó None para escena {idx + 1}")
                        try:
                            original_video_clip.close()
                            original_audio_clip.close()
                        except:
                            pass
                        return None
                else:
                    # No hay subtítulos, usar solo el clip de fondo
                    video_clip = background_clip
                    if video_clip is None:
                        logger.error(f"❌ background_clip es None para escena {idx + 1}")
                        try:
                            original_video_clip.close()
                            original_audio_clip.close()
                        except:
                            pass
                        return None
                
                # Ajustar duración final del clip visual (sin audio)
                # La duración se ajustará al audio completo en render_final_video
                video_clip = video_clip.set_duration(video_duration)
                
                # VALIDACIÓN FINAL: Verificar que video_clip es válido y tiene los métodos necesarios
                if video_clip is None:
                    logger.error(f"❌ video_clip es None después de set_duration para escena {idx + 1}")
                    try:
                        original_video_clip.close()
                        original_audio_clip.close()
                    except:
                        pass
                    return None
                
                # Verificar que tiene los atributos necesarios
                if not hasattr(video_clip, 'duration') or not hasattr(video_clip, 'get_frame'):
                    logger.error(f"❌ video_clip no tiene atributos necesarios después de procesar para escena {idx + 1}")
                    try:
                        video_clip.close() if hasattr(video_clip, 'close') else None
                        original_video_clip.close()
                        original_audio_clip.close()
                    except:
                        pass
                    return None
                
                # Guardar referencia al audio original para referencia (pero no lo usamos aquí)
                # El audio se manejará globalmente
                
                # NO cerrar los clips aquí - se cerrarán después de concatenar
                # Guardar referencias para poder cerrarlos después
                video_clip._original_video = original_video_clip
                video_clip._original_audio = original_audio_clip
                
                logger.success(f"✅ Escena {idx + 1} procesada correctamente (duración: {video_clip.duration:.2f}s)")
                return video_clip
                
            except Exception as e:
                logger.error(f"❌ Error creando composite o ajustando duración para escena {idx + 1}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                try:
                    if 'video_clip' in locals() and video_clip:
                        video_clip.close()
                    original_video_clip.close()
                    original_audio_clip.close()
                except:
                    pass
                return None
            
        except Exception as e:
            logger.error(f"Error procesando escena {idx + 1}: {e}")
            logger.warning(f"⚠️ Retornando None para escena {idx + 1} para evitar crash")
            # Cerrar clips si hay error antes de retornar None
            if original_video_clip:
                try:
                    original_video_clip.close()
                except:
                    pass
            if original_audio_clip:
                try:
                    original_audio_clip.close()
                except:
                    pass
            return None
    
    def render_final_video(self, scenes: List[Dict], output_path: str, background_music: Optional[str] = None, music_volume: float = 0.1, target_width: int = None, target_height: int = None, bitrate: str = None, use_subtitles: bool = True, watermark_text: Optional[str] = None, watermark_position: str = "bottom-right", enable_color_grading: bool = False, use_crossfade_transitions: bool = False, crossfade_duration: float = 0.5, add_branding: bool = False, style_code: Optional[str] = None, style_label: Optional[str] = None, use_crossfade: bool = False, target_resolution: tuple = None) -> str:
        """
        Renderiza el video final concatenando las escenas procesadas.
        Versión ROBUSTA: Garantiza duración exacta y música audible.
        """
        logger.info(f"🎬 Iniciando renderizado final: {output_path}")
        
        # 1. Configuración de resolución
        if target_resolution:
            target_width, target_height = target_resolution
        else:
            target_width = target_width or TARGET_WIDTH
            target_height = target_height or TARGET_HEIGHT
            
        # 2. Procesar escenas
        final_clips = []
        full_audio_clips = []
        
        for idx, scene in enumerate(scenes):
            try:
                clip = self.process_scene(
                    scene=scene,
                    idx=idx,
                    background_music=None,  # La música se añade al final globalmente
                    music_volume=0,
                    use_karaoke=True,
                    target_width=target_width,
                    target_height=target_height,
                    use_subtitles=use_subtitles,
                    enable_color_grading=enable_color_grading,
                    style_code=style_code,
                    style_label=style_label
                )
                
                if clip is not None:
                    final_clips.append(clip)
                    if clip.audio:
                        full_audio_clips.append(clip.audio)
                else:
                    logger.warning(f"⚠️ Escena {idx + 1} falló y fue omitida.")
            except Exception as e:
                logger.error(f"❌ Error procesando escena {idx + 1}: {e}")
        
        if not final_clips:
            raise ValueError("❌ No se pudieron generar clips válidos para el video.")

        # 3. Concatenar Audio Principal (Voz)
        # Este es el "Master Clock" del video
        try:
            if full_audio_clips:
                voice_track = concatenate_audioclips(full_audio_clips)
                total_audio_duration = voice_track.duration
                logger.info(f"🎙️ Duración total de voz: {total_audio_duration:.2f}s")
            else:
                voice_track = None
                total_audio_duration = sum(c.duration for c in final_clips)
                logger.warning("⚠️ Sin audio de voz. Usando duración visual.")
        except Exception as e:
            logger.error(f"❌ Error concatenando audio: {e}")
            raise

        # 4. Preparar Clips Visuales (Smart Loop)
        # Objetivo: Que los visuales cubran EXACTAMENTE la duración del audio
        video_only_clips = [c.without_audio() for c in final_clips]
        current_visual_duration = sum(c.duration for c in video_only_clips)
        
        logger.info(f"📊 Duración visual inicial: {current_visual_duration:.2f}s vs Objetivo: {total_audio_duration:.2f}s")
        
        # Bucle de seguridad: Repetir clips si faltan
        final_visual_list = []
        accumulated_duration = 0.0
        
        # Estrategia: Llenar una lista hasta superar la duración objetivo
        if total_audio_duration > 0:
            while accumulated_duration < total_audio_duration:
                for clip in video_only_clips:
                    final_visual_list.append(clip)
                    accumulated_duration += clip.duration
                    if accumulated_duration >= total_audio_duration:
                        break
        else:
            final_visual_list = video_only_clips
        
        logger.info(f"🔄 Smart Loop: Se usaron {len(final_visual_list)} clips para cubrir la duración.")

        # 5. Concatenar y Cortar Video
        try:
            # Concatenar visuales
            if use_crossfade_transitions and len(final_visual_list) > 1:
                final_video = concatenate_videoclips(final_visual_list, method="compose", padding=-crossfade_duration)
            else:
                final_video = concatenate_videoclips(final_visual_list, method="compose")
            
            # Cortar al tiempo exacto del audio
            if total_audio_duration > 0:
                final_video = final_video.subclip(0, total_audio_duration)
            logger.success(f"✅ Video visual ensamblado: {final_video.duration:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Error ensamblando video: {e}")
            raise

        # 6. Mezcla de Audio (Voz + Música)
        final_audio = voice_track
        
        if background_music and os.path.exists(background_music):
            try:
                logger.info(f"🎵 Añadiendo música de fondo: {Path(background_music).name}")
                music_clip = AudioFileClip(background_music)
                
                target_dur = total_audio_duration if total_audio_duration > 0 else final_video.duration
                
                # Loopear música si es corta (Lógica estricta del usuario)
                if music_clip.duration < target_dur:
                    music_clip = audio_loop(music_clip, duration=target_dur)
                else:
                    music_clip = music_clip.subclip(0, target_dur)
                
                # Bajar volumen (Ducking)
                music_clip = music_clip.volumex(music_volume)
                
                # Mezclar con voz (si existe)
                if voice_track:
                    # Nota: El orden en CompositeAudioClip importa para el mix, pero aquí se mezclan igual
                    final_audio = CompositeAudioClip([music_clip, voice_track])
                else:
                    final_audio = music_clip
                    
                logger.success("✅ Mezcla de audio completada")
                
            except Exception as e:
                logger.warning(f"⚠️ Error mezclando música: {e}. Se usará solo voz.")
        
        # Asignar audio final al video
        if final_audio:
            final_video = final_video.set_audio(final_audio)

        # 7. Renderizado
        try:
            # Asegurar directorio de salida
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Parámetros de renderizado optimizados
            threads = os.cpu_count() or 4
            preset = "medium"  # Balance velocidad/calidad
            
            final_video.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                fps=24,
                preset=preset,
                threads=threads,
                bitrate=bitrate or "5000k",
                logger=None  # Reducir ruido en logs
            )
            
            logger.success(f"🚀 Renderizado completado: {output_path}")
            
            # Limpieza
            try:
                final_video.close()
                for c in final_clips: c.close()
            except:
                pass
                
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Error fatal en write_videofile: {e}")
            raise

