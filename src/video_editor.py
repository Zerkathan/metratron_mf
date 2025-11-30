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
from moviepy.video.fx import all as vfx

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
        Mantiene el aspecto sin distorsión usando crop/zoom inteligente (Center Crop).
        
        Args:
            clip: Clip de video a redimensionar
            target_width: Ancho objetivo
            target_height: Alto objetivo
        
        Returns:
            Clip redimensionado al formato especificado
        """
        try:
            original_width, original_height = clip.size
            original_aspect = original_width / original_height
            target_aspect = target_width / target_height
            
            logger.debug(f"Redimensionando video: {original_width}x{original_height} -> {target_width}x{target_height}")
            
            # Si el video ya está en el formato correcto
            if abs(original_width - target_width) < 10 and abs(original_height - target_height) < 10:
                logger.debug("Video ya está en formato correcto, omitiendo redimensionamiento")
                return clip
            
            # Si el video es más horizontal que el target, hacer crop centrado horizontal
            if original_aspect > target_aspect:
                # Video es más ancho: recortar los lados (Center Crop)
                new_width = int(original_height * target_aspect)
                x_center = original_width / 2
                x1 = max(0, int(x_center - new_width / 2))
                x2 = min(original_width, int(x_center + new_width / 2))
                
                clip = clip.crop(x1=x1, x2=x2)
                logger.debug(f"Crop horizontal (Center): x1={x1}, x2={x2}, nuevo tamaño: {clip.size}")
            
            # Si el video es más vertical que el target, hacer crop centrado vertical
            elif original_aspect < target_aspect:
                # Video es más alto: recortar arriba/abajo (Center Crop)
                new_height = int(original_width / target_aspect)
                y_center = original_height / 2
                y1 = max(0, int(y_center - new_height / 2))
                y2 = min(original_height, int(y_center + new_height / 2))
                
                clip = clip.crop(y1=y1, y2=y2)
                logger.debug(f"Crop vertical (Center): y1={y1}, y2={y2}, nuevo tamaño: {clip.size}")
            
            # Redimensionar al tamaño objetivo exacto
            clip = clip.resize((target_width, target_height))
            logger.debug(f"Video redimensionado a {target_width}x{target_height}")
            
            return clip
            
        except Exception as e:
            logger.warning(f"Error redimensionando video, usando tamaño original: {e}")
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
                            subtitle = TextClip(
                                current_text,
                                fontsize=70,  # Tamaño aumentado para mejor legibilidad
                                color='white',  # Color base: blanco
                                font=self.font,  # Usar fuente personalizada si está disponible
                                stroke_color='black',  # Borde negro para contraste
                                stroke_width=3,  # Borde grueso para máximo contraste (estilo viral profesional)
                                method='caption',
                                size=(None, None),
                                align='center'
                            ).set_position(('center', 'bottom')).set_start(current_start).set_duration(end - current_start)
                            
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
                    subtitle = TextClip(
                        current_text,
                        fontsize=60,
                        color='white',
                        font=self.font,
                        stroke_color='black',
                        stroke_width=2,
                        method='caption',
                        size=(None, None),
                        align='center'
                    ).set_position(('center', 'bottom')).set_start(current_start).set_duration(last_end - current_start)
                    
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
            base_fontsize = 70  # Aumentado para mejor legibilidad
            highlight_fontsize = int(base_fontsize * 1.3)  # 30% más grande para palabras activas
            base_color = 'white'  # Color base: blanco
            stroke_color = 'black'  # Borde negro para contraste
            stroke_width = 3  # Borde grueso para máximo contraste (estilo viral profesional)
            
            # Color vibrante para palabra activa: 'yellow' o '#00ff00' (Verde Neón)
            if highlight_color and highlight_color.lower() in ['yellow', '#00ff00', '#ffd700', '#ffff00']:
                highlight_color_final = highlight_color if highlight_color.startswith('#') else 'yellow'
            else:
                highlight_color_final = '#00ff00'  # Verde Neón por defecto (más impactante)
            
            # Posición: centro-abajo (aproximadamente 85% desde arriba)
            y_position = int(height * 0.85)
            
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
                        
                        # Estilo según si está activa (Estilo Viral: colores vibrantes)
                        if is_active:
                            fontsize = highlight_fontsize
                            color = highlight_color_final  # Yellow o Verde Neón para palabra activa
                            current_stroke_width = stroke_width  # Mantener stroke_width=3 para palabra activa
                        else:
                            fontsize = base_fontsize
                            color = base_color  # Blanco para palabras no activas
                            current_stroke_width = stroke_width  # Stroke_width=3 para todas las palabras
                        
                        # Calcular posición X (aproximada basada en ancho de caracteres)
                        word_width_approx = len(w) * char_width_approx
                        x_position = current_x + (word_width_approx / 2)
                        
                        try:
                            # Crear clip de texto para esta palabra (Estilo Hormozi: máximo impacto visual)
                            word_clip = TextClip(
                                w,
                                fontsize=fontsize,
                                color=color,
                                font=self.font,  # Usar fuente personalizada si está disponible
                                stroke_color=stroke_color,
                                stroke_width=current_stroke_width,  # Borde grueso para contraste
                                method='caption',
                                size=(None, None),
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
            # ESTILO VIRAL: Fuentes grandes, bordes gruesos, máximo contraste
            # ============================================================
            fontsize = 70  # Aumentado para mejor legibilidad
            color = 'white'  # Color base: blanco
            stroke_color = 'black'  # Borde negro para contraste
            stroke_width = 3  # Borde grueso para máximo contraste (estilo viral profesional)
            
            # Posición Y según el parámetro
            if position == "bottom":
                y_position = int(height * 0.85)  # 85% desde arriba
            elif position == "center":
                y_position = int(height * 0.5)  # Centro
            else:
                y_position = int(height * 0.15)  # 15% desde arriba
            
            # Limitar texto a un ancho razonable (aproximadamente 80% del ancho)
            max_width = int(width * 0.8)
            
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
        
        # Construir rutas absolutas y sanitizadas
        audio_file = os.path.abspath(str(BASE_DIR / "assets" / "temp" / f"audio_{idx}.mp3"))
        video_file = os.path.abspath(str(BASE_DIR / "assets" / "temp" / f"scene_{idx:02d}_video.mp4"))
        
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
            # Buscar si hay una imagen con el mismo nombre base
            for ext in image_extensions:
                image_file = video_path.with_suffix(ext)
                if image_file.exists():
                    video_file = str(image_file)
                    is_image = True
                    logger.info(f"📸 Imagen encontrada en lugar de video: {image_file.name}")
                    break
            
            if not is_image:
                logger.error(f"Archivo de video/imagen no encontrado: {video_file}")
                logger.warning(f"⚠️ Saltando escena {idx + 1} por falta de recurso visual")
                return None
        
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
            
            # Añadir música de fondo si está disponible (con loop si es necesario)
            final_audio = original_audio_clip
            if background_music and Path(background_music).exists():
                try:
                    music_clip = AudioFileClip(background_music)
                    music_duration = music_clip.duration
                    
                    # Si la música es más corta que el video, hacer loop
                    if music_duration < video_duration:
                        loops_needed = int(video_duration / music_duration) + 1
                        music_clips = [music_clip] * loops_needed
                        music_clip = concatenate_audioclips(music_clips).subclip(0, video_duration)
                        logger.debug(f"Música looped: {music_duration:.2f}s -> {video_duration:.2f}s")
                    else:
                        # Si es más larga, cortar al tamaño del video
                        music_clip = music_clip.subclip(0, video_duration)
                    
                    music_clip = music_clip.volumex(music_volume)
                    final_audio = CompositeAudioClip([original_audio_clip, music_clip])
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
        Renderiza el video final combinando todas las escenas.
        
        Args:
            scenes: Lista de diccionarios de escenas
            output_path: Ruta de salida del video
            background_music: Ruta opcional a música de fondo
            music_volume: Volumen de la música de fondo
            target_width: Ancho objetivo del video (opcional, usa TARGET_WIDTH por defecto)
            target_height: Alto objetivo del video (opcional, usa TARGET_HEIGHT por defecto)
            bitrate: Bitrate para el video (opcional, se calcula automáticamente según resolución)
            use_subtitles: Si True, incrusta subtítulos. Si False, renderiza Clean Feed (sin texto)
            watermark_text: Texto de marca de agua (opcional, ej: "@MiCanal")
            watermark_position: Posición del watermark ("bottom-right", "top-center", "bottom-left", "top-right")
            add_branding: Si True, agrega intro/outro y overlay de CTA si existen en assets/branding
            style_code: Código/nombre interno del estilo (ej: "HORROR")
            style_label: Etiqueta amigable del estilo (ej: "💀 Horror / Creepypasta")
            use_crossfade_transitions: Si True, aplica fundidos suaves entre clips
            use_crossfade: Si True, aplica fundidos suaves entre clips (alias de use_crossfade_transitions)
            target_resolution: Tupla (width, height) con la resolución objetivo del video (ej: (1080, 1920))
                               Si se proporciona, sobrescribe target_width y target_height
        
        Returns:
            Ruta del video renderizado
        """
        logger.info(f"Iniciando renderizado de {len(scenes)} escenas...")
        
        # Calcular style_slug desde style_code y style_label (necesario para branding)
        style_slug = self._normalize_style_slug(style_code or style_label or "general")
        
        # Obtener ruta absoluta para música de fondo
        if background_music:
            BASE_DIR = Path(__file__).parent.parent.resolve()
            music_path = (BASE_DIR / background_music).resolve()
            if music_path.exists():
                background_music = str(music_path)
            else:
                logger.warning(f"Archivo de música no encontrado: {music_path}")
                logger.info("Continuando sin música de fondo...")
                background_music = None
        
        clips = []
        try:
            # Si target_resolution está proporcionado, extraer width y height de ahí
            if target_resolution and isinstance(target_resolution, (tuple, list)) and len(target_resolution) >= 2:
                target_width = target_resolution[0]
                target_height = target_resolution[1]
                logger.info(f"📐 Resolución objetivo desde target_resolution: {target_width}x{target_height}")
            
            # Usar dimensiones dinámicas si se proporcionan, sino usar las por defecto
            final_width = target_width or TARGET_WIDTH
            final_height = target_height or TARGET_HEIGHT
            
            # Logging sobre subtítulos
            if use_subtitles:
                logger.info("📝 Subtítulos (Burn-in) activados - Generando subtítulos para todas las escenas")
            else:
                logger.info("📝 Renderizando Clean Feed (Sin subtítulos) - Saltando generación de subtítulos")
            
            # Procesar cada escena
            for idx, scene in enumerate(scenes):
                try:
                    clip = self.process_scene(scene, idx, background_music, music_volume, use_karaoke=use_subtitles, target_width=final_width, target_height=final_height, use_subtitles=use_subtitles, enable_color_grading=enable_color_grading, style_code=style_code, style_label=style_label)
                    clips.append(clip)  # Puede ser None si falló
                except Exception as e:
                    logger.error(f"Error procesando escena {idx + 1}: {e}")
                    logger.warning(f"⚠️ Agregando None para escena {idx + 1}")
                    clips.append(None)
            
            # FILTRADO AGRESIVO: Filtrar clips None e inválidos antes de concatenar
            final_clips = []
            for idx, clip in enumerate(clips):
                if clip is None:
                    logger.warning(f"⚠️ Clip {idx} es None, filtrando...")
                    continue
                
                # Validar que el clip tenga los atributos básicos necesarios
                try:
                    if not hasattr(clip, 'duration') or not hasattr(clip, 'get_frame'):
                        logger.warning(f"⚠️ Clip {idx} no tiene atributos necesarios (duration/get_frame), filtrando...")
                        continue
                    
                    # Validar que la duración sea válida
                    if clip.duration <= 0:
                        logger.warning(f"⚠️ Clip {idx} tiene duración inválida ({clip.duration}), filtrando...")
                        continue
                    
                    final_clips.append(clip)
                    logger.debug(f"✅ Clip {idx} validado (duración: {clip.duration:.2f}s)")
                    
                except Exception as e:
                    logger.error(f"❌ Error validando clip {idx}: {e}")
                    logger.warning(f"⚠️ Filtrando clip {idx} debido a error de validación")
                    continue
            
            # Verificar que hay al menos un clip válido
            if len(final_clips) == 0:
                raise ValueError("❌ ¡No hay clips válidos para renderizar! Todas las escenas fallaron o son inválidas.")
            
            # Informar sobre clips filtrados
            filtered_count = len(clips) - len(final_clips)
            if filtered_count > 0:
                logger.warning(f"⚠️ {filtered_count} escena(s) fallaron y fueron filtradas. Renderizando con {len(final_clips)} escena(s) válida(s).")
            
            # ============================================================
            # FIX CRÍTICO: CARGA DE AUDIO COMPLETO ANTES DE CONCATENAR
            # ============================================================
            logger.info("🔊 Cargando pista de audio completa...")
            BASE_DIR = Path(__file__).parent.parent.resolve()
            temp_dir = BASE_DIR / "assets" / "temp"
            
            # Cargar TODOS los audios y concatenarlos en una pista completa
            full_audio_clips = []
            total_audio_duration = 0.0
            
            for idx in range(len(scenes)):
                audio_file = temp_dir / f"audio_{idx}.mp3"
                if audio_file.exists():
                    try:
                        audio_clip = AudioFileClip(str(audio_file))
                        full_audio_clips.append(audio_clip)
                        total_audio_duration += audio_clip.duration
                        logger.debug(f"Audio {idx} cargado: {audio_clip.duration:.2f}s")
                    except Exception as e:
                        logger.warning(f"Error cargando audio_{idx}.mp3: {e}")
            
            # Concatenar todos los audios en una pista completa
            if full_audio_clips:
                # VALIDACIÓN: Filtrar cualquier None antes de concatenar
                valid_audio_clips = []
                for i, audio_clip in enumerate(full_audio_clips):
                    if audio_clip is None:
                        logger.warning(f"⚠️ Audio clip {i} es None, filtrando...")
                        continue
                    # Verificar que tiene duración válida
                    try:
                        if not hasattr(audio_clip, 'duration') or audio_clip.duration <= 0:
                            logger.warning(f"⚠️ Audio clip {i} tiene duración inválida, filtrando...")
                            continue
                        valid_audio_clips.append(audio_clip)
                    except Exception as e:
                        logger.warning(f"⚠️ Error validando audio clip {i}: {e}, filtrando...")
                        continue
                
                if not valid_audio_clips:
                    logger.warning("⚠️ No hay clips de audio válidos después del filtrado. El video quedará sin audio.")
                    full_audio_track = None
                    total_audio_duration = 0.0
                else:
                    logger.info(f"🔊 Concatenando {len(valid_audio_clips)} pistas de audio válidas en pista completa...")
                    try:
                        full_audio_track = concatenate_audioclips(valid_audio_clips)
                        if full_audio_track is None:
                            logger.error("❌ concatenate_audioclips retornó None")
                            full_audio_track = None
                            total_audio_duration = 0.0
                        else:
                            total_audio_duration = full_audio_track.duration
                            logger.success(f"✅ Pista de audio completa: {total_audio_duration:.2f}s")
                    except Exception as e:
                        logger.error(f"❌ Error concatenando audios: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
                        full_audio_track = None
                        total_audio_duration = 0.0
            else:
                logger.warning("⚠️ No se encontraron archivos de audio. El video quedará sin audio.")
                full_audio_track = None
                total_audio_duration = 0.0
            
            # ============================================================
            # CONCATENAR CLIPS VISUALES (SIN AUDIO)
            # ============================================================
            logger.info(f"🎬 Concatenando {len(final_clips)} escenas válidas (solo video)...")
            
            # FILTRADO AGRESIVO: Remover audio y validar clips antes de concatenar
            video_only_clips = []
            for idx, clip in enumerate(final_clips):
                if clip is None:
                    logger.warning(f"⚠️ Clip {idx} es None, saltando...")
                    continue
                
                try:
                    # Validar que el clip tenga los métodos necesarios
                    if not hasattr(clip, 'get_frame') or not hasattr(clip, 'without_audio'):
                        logger.warning(f"⚠️ Clip {idx} no tiene métodos necesarios, saltando...")
                        continue
                    
                    # Remover audio del clip individual
                    video_clip_clean = clip.without_audio()
                    
                    # Validar que el clip limpio también sea válido
                    if video_clip_clean is None:
                        logger.warning(f"⚠️ Clip {idx} se volvió None después de remover audio, saltando...")
                        continue
                    
                    # VALIDACIÓN ADICIONAL: Verificar que el audio removido no dejó componentes None
                    # Si el clip original tenía audio problemático, asegurarse de que se removió correctamente
                    if hasattr(video_clip_clean, 'audio') and video_clip_clean.audio is not None:
                        # Si todavía tiene audio después de without_audio(), puede ser problemático
                        audio_obj = video_clip_clean.audio
                        if hasattr(audio_obj, 'clips') and audio_obj.clips:
                            for audio_sub in audio_obj.clips:
                                if audio_sub is None or not hasattr(audio_sub, 'get_frame'):
                                    logger.warning(f"⚠️ Clip {idx} tiene audio inválido después de without_audio(), removiendo nuevamente...")
                                    try:
                                        video_clip_clean = video_clip_clean.without_audio()
                                    except:
                                        logger.warning(f"⚠️ No se pudo remover audio inválido del clip {idx}")
                    
                    # Validar que el clip limpio tenga duración válida
                    if not hasattr(video_clip_clean, 'duration') or video_clip_clean.duration <= 0:
                        logger.warning(f"⚠️ Clip {idx} tiene duración inválida, saltando...")
                        continue
                    
                    # Validar que tiene get_frame
                    if not hasattr(video_clip_clean, 'get_frame'):
                        logger.warning(f"⚠️ Clip {idx} no tiene get_frame después de limpiar, saltando...")
                        continue
                    
                    video_only_clips.append(video_clip_clean)
                    logger.debug(f"✅ Clip {idx} validado y agregado (duración: {video_clip_clean.duration:.2f}s)")
                    
                except Exception as e:
                    logger.error(f"❌ Error validando clip {idx}: {e}")
                    logger.warning(f"⚠️ Saltando clip {idx} debido a error de validación")
                    continue
            
            # Verificar que hay al menos un clip válido después del filtrado agresivo
            if not video_only_clips:
                raise ValueError("❌ ¡No hay clips válidos para renderizar! Todas las escenas fallaron o son inválidas.")
            
            logger.info(f"✅ {len(video_only_clips)} clip(s) válido(s) listos para concatenar (de {len(final_clips)} originales)")
            
            # Concatenar solo los clips visuales válidos
            # Usar use_crossfade si está disponible, sino usar use_crossfade_transitions
            crossfade_enabled = (use_crossfade or use_crossfade_transitions) and len(video_only_clips) > 1
            effective_crossfade = crossfade_duration
            if crossfade_enabled:
                min_duration = min(clip.duration for clip in video_only_clips)
                if min_duration <= 0.2:
                    logger.warning("⚠️ Clips demasiado cortos para aplicar crossfade. Usando cortes secos.")
                    crossfade_enabled = False
                else:
                    if effective_crossfade >= min_duration:
                        effective_crossfade = max(0.1, min_duration * 0.4)
                    logger.info(f"🎞️ Transiciones suaves activadas (crossfade {effective_crossfade:.2f}s).")
                    prepared_clips = [video_only_clips[0]]
                    for clip in video_only_clips[1:]:
                        try:
                            prepared_clips.append(clip.crossfadein(effective_crossfade))
                        except Exception as e:
                            logger.warning(f"⚠️ No se pudo aplicar crossfade a un clip: {e}. Usando versión sin transición.")
                            prepared_clips.append(clip)
                    video_only_clips = prepared_clips

            # VALIDACIÓN FINAL CRÍTICA: Verificar que TODOS los clips son válidos antes de concatenar
            # MoviePy puede llamar internamente a get_frame() durante concatenate_videoclips
            final_valid_clips = []
            for i, clip in enumerate(video_only_clips):
                if clip is None:
                    logger.warning(f"⚠️ Clip {i} es None antes de concatenar, filtrando...")
                    continue
                # Verificar que tiene los atributos necesarios
                if not hasattr(clip, 'duration') or not hasattr(clip, 'get_frame'):
                    logger.warning(f"⚠️ Clip {i} no tiene atributos necesarios antes de concatenar, filtrando...")
                    continue
                # Verificar duración válida
                try:
                    if clip.duration <= 0:
                        logger.warning(f"⚠️ Clip {i} tiene duración inválida ({clip.duration}), filtrando...")
                        continue
                    final_valid_clips.append(clip)
                    logger.debug(f"✅ Clip {i} validado para concatenación (duración: {clip.duration:.2f}s)")
                except Exception as e:
                    logger.warning(f"⚠️ Error validando clip {i} para concatenación: {e}, filtrando...")
                    continue
            
            if len(final_valid_clips) == 0:
                raise ValueError("❌ ¡No hay clips válidos para concatenar! Todos los clips fueron filtrados.")
            
            if len(final_valid_clips) < len(video_only_clips):
                logger.warning(f"⚠️ Se filtraron {len(video_only_clips) - len(final_valid_clips)} clips inválidos antes de concatenar")
            
            video_only_clips = final_valid_clips
            
            try:
                if crossfade_enabled:
                    final_video_clip = concatenate_videoclips(
                        video_only_clips,
                        method="compose",
                        padding=-effective_crossfade
                    )
                else:
                    final_video_clip = concatenate_videoclips(video_only_clips, method="compose")
            except Exception as e:
                logger.error(f"❌ Error al concatenar clips: {e}")
                logger.error(f"📊 Intentando concatenar {len(video_only_clips)} clips válidos")
                # Cerrar clips antes de fallar
                for clip in video_only_clips:
                    try:
                        clip.close()
                    except:
                        pass
                raise ValueError(f"Error al concatenar clips de video: {e}")
            total_video_duration = final_video_clip.duration
            
            logger.info(f"📊 Duración video concatenado: {total_video_duration:.2f}s | Duración audio completo: {total_audio_duration:.2f}s")
            
            # ============================================================
            # LOOPEAR CLIPS VISUALES SI SON MÁS CORTOS QUE EL AUDIO
            # ============================================================
            looped_video_temp = None  # Para limpiar después
            if full_audio_track and total_video_duration < total_audio_duration:
                logger.info(f"🔄 Video más corto que audio. Loopeando secuencia visual para cubrir {total_audio_duration:.2f}s...")
                loops_needed = int(total_audio_duration / total_video_duration) + 1
                
                # Crear lista de clips repetidos
                looped_video_clips = []
                for i in range(loops_needed):
                    # Hacer una copia del clip concatenado para cada loop
                    looped_video_clips.append(final_video_clip)
                
                # Concatenar los loops
                looped_video_temp = concatenate_videoclips(looped_video_clips, method="compose")
                
                # Cortar al tamaño exacto del audio
                old_video_clip = final_video_clip
                final_video_clip = looped_video_temp.subclip(0, total_audio_duration)
                total_video_duration = final_video_clip.duration
                
                # Cerrar el clip viejo
                try:
                    old_video_clip.close()
                except:
                    pass
                
                logger.success(f"✅ Video looped: {total_video_duration:.2f}s (cubriendo audio completo)")
            elif full_audio_track and total_video_duration > total_audio_duration:
                # Si el video es más largo, cortarlo al tamaño del audio
                logger.info(f"✂️ Video más largo que audio. Cortando video a {total_audio_duration:.2f}s...")
                old_video_clip = final_video_clip
                final_video_clip = final_video_clip.subclip(0, total_audio_duration)
                total_video_duration = total_audio_duration
                # Cerrar el clip viejo
                try:
                    old_video_clip.close()
                except:
                    pass
            elif not full_audio_track:
                # Sin audio: usar duración del video o duración basada en escenas
                logger.info(f"⚠️ Sin audio disponible. Usando duración del video: {total_video_duration:.2f}s")
            
            # ============================================================
            # CALCULAR PUNTOS DE CORTE PARA SFX DE TRANSICIÓN
            # ============================================================
            transition_cut_points = []
            if full_audio_clips and len(full_audio_clips) > 1:
                # Calcular los tiempos donde terminan los clips (puntos de corte)
                cumulative_time = 0.0
                for idx, audio_clip in enumerate(full_audio_clips):
                    # El punto de corte es donde TERMINA cada clip (excepto el último)
                    if idx < len(full_audio_clips) - 1:  # No agregar corte después del último clip
                        cumulative_time += audio_clip.duration
                        transition_cut_points.append(cumulative_time)
                logger.info(f"🎬 Puntos de corte detectados: {len(transition_cut_points)} transiciones")
            
            # ============================================================
            # AGREGAR MÚSICA DE FONDO Y MEZCLAR CON AUDIO COMPLETO
            # Sistema de Ducking: Música se atenúa cuando hay voz
            # ============================================================
            final_audio_composite = full_audio_track
            
            if background_music and Path(background_music).exists():
                try:
                    music_clip = AudioFileClip(background_music)
                    target_duration = total_audio_duration if full_audio_track else total_video_duration
                    
                    # VALIDACIÓN: Verificar que music_clip no es None
                    if music_clip is None:
                        logger.error("❌ music_clip es None después de cargar")
                        raise ValueError("No se pudo cargar la música de fondo")
                    
                    # Asegurar que la música cubra toda la duración necesaria
                    if music_clip.duration < target_duration:
                        loops_needed = int(target_duration / music_clip.duration) + 1
                        music_clips_looped = [music_clip] * loops_needed
                        try:
                            looped_music = concatenate_audioclips(music_clips_looped)
                            if looped_music is None:
                                logger.error("❌ concatenate_audioclips retornó None para música looped")
                                raise ValueError("Error concatenando música looped")
                            music_clip = looped_music.subclip(0, target_duration)
                            if music_clip is None:
                                logger.error("❌ subclip retornó None para música looped")
                                raise ValueError("Error en subclip de música looped")
                        except Exception as e:
                            logger.error(f"❌ Error creando música looped: {e}")
                            raise
                    
                    # LÓGICA DE DUCKING (Jerarquía de Audio)
                    if full_audio_track:
                        # VALIDACIÓN: Verificar que ambos clips son válidos antes de crear composite
                        if full_audio_track is None:
                            logger.error("❌ full_audio_track es None, no se puede mezclar con música")
                            final_audio_composite = music_clip
                        elif music_clip is None:
                            logger.error("❌ music_clip es None, usando solo full_audio_track")
                            final_audio_composite = full_audio_track
                        else:
                            # Hay voz: Bajar música al 10% para que no compita con la narración
                            effective_music_volume = 0.1  # 10% - Ducking automático
                            logger.info("🎵 Mezclando música de fondo con pista de audio completa (Ducking activado: música al 10%)...")
                            music_clip = music_clip.volumex(effective_music_volume)
                            try:
                                final_audio_composite = CompositeAudioClip([full_audio_track, music_clip])
                                if final_audio_composite is None:
                                    logger.error("❌ CompositeAudioClip retornó None")
                                    final_audio_composite = full_audio_track  # Fallback a solo voz
                                else:
                                    logger.success("✅ Música de fondo mezclada con voz (música atenuada al 10% para claridad)")
                            except Exception as e:
                                logger.error(f"❌ Error creando CompositeAudioClip de voz + música: {e}")
                                logger.warning("⚠️ Usando solo audio de voz como fallback")
                                final_audio_composite = full_audio_track
                    else:
                        # No hay voz (modo musical o sin narración): Música al volumen configurado o 100%
                        if music_clip is None:
                            logger.error("❌ music_clip es None y no hay voz. El video quedará sin audio.")
                            final_audio_composite = None
                        else:
                            effective_music_volume = music_volume if music_volume > 0 else 1.0
                            logger.info(f"🎵 Usando música de fondo sin narración (volumen: {effective_music_volume*100:.0f}%)...")
                            music_clip = music_clip.volumex(effective_music_volume)
                            final_audio_composite = music_clip
                            logger.success(f"✅ Música de fondo aplicada (sin voz, volumen: {effective_music_volume*100:.0f}%)")
                    
                    music_clip.close()
                except Exception as e:
                    logger.warning(f"⚠️ Error mezclando música de fondo: {e}. Usando solo audio de narración.")
                    if not full_audio_track:
                        logger.warning("⚠️ Sin audio de voz ni música. El video quedará sin audio.")
                        final_audio_composite = None
            
            # ============================================================
            # INYECTAR EFECTOS DE SONIDO (SFX) EN TRANSICIONES
            # ============================================================
            if final_audio_composite and transition_cut_points and len(transition_cut_points) > 0:
                try:
                    # Buscar archivo de SFX de transición
                    BASE_DIR = Path(__file__).parent.parent.resolve()
                    sfx_path = BASE_DIR / "assets" / "sfx" / "transition.mp3"
                    
                    if sfx_path.exists():
                        logger.info(f"🎵 Cargando SFX de transición desde: {sfx_path.name}")
                        transition_sfx = AudioFileClip(str(sfx_path))
                        sfx_duration = transition_sfx.duration
                        sfx_volume = 0.4  # Volumen al 40% para que no tape la voz
                        transition_sfx = transition_sfx.volumex(sfx_volume)
                        
                        # Crear clips de SFX en cada punto de corte
                        sfx_clips = []
                        target_duration = total_audio_duration if full_audio_track else total_video_duration
                        
                        for cut_point in transition_cut_points:
                            # Verificar que el SFX no exceda la duración del video
                            if cut_point + sfx_duration <= target_duration:
                                # Crear clip de SFX en el punto de corte
                                sfx_at_cut = transition_sfx.set_start(cut_point)
                                sfx_clips.append(sfx_at_cut)
                                logger.debug(f"✅ SFX agregado en transición {cut_point:.2f}s")
                            else:
                                logger.debug(f"⚠️ Saltando SFX en {cut_point:.2f}s (excedería duración del video)")
                        
                        if sfx_clips:
                            # VALIDACIÓN: Filtrar SFX None antes de mezclar
                            valid_sfx_clips = []
                            for i, sfx_clip in enumerate(sfx_clips):
                                if sfx_clip is None:
                                    logger.warning(f"⚠️ SFX clip {i} es None, filtrando...")
                                    continue
                                if not hasattr(sfx_clip, 'duration'):
                                    logger.warning(f"⚠️ SFX clip {i} no tiene duración, filtrando...")
                                    continue
                                valid_sfx_clips.append(sfx_clip)
                            
                            if valid_sfx_clips:
                                # VALIDACIÓN: Verificar que final_audio_composite no es None
                                if final_audio_composite is None:
                                    logger.warning("⚠️ final_audio_composite es None, no se pueden agregar SFX")
                                else:
                                    # Mezclar SFX con el audio compuesto existente
                                    logger.info(f"🔊 Mezclando {len(valid_sfx_clips)} efecto(s) de sonido de transición...")
                                    audio_layers = [final_audio_composite]
                                    audio_layers.extend(valid_sfx_clips)
                                    try:
                                        final_audio_composite = CompositeAudioClip(audio_layers)
                                        if final_audio_composite is None:
                                            logger.error("❌ CompositeAudioClip con SFX retornó None")
                                            # Mantener audio anterior sin SFX
                                        else:
                                            logger.success(f"✅ {len(valid_sfx_clips)} SFX de transición mezclado(s) exitosamente")
                                    except Exception as e:
                                        logger.error(f"❌ Error creando CompositeAudioClip con SFX: {e}")
                                        logger.warning("⚠️ Continuando sin SFX, usando audio anterior")
                            else:
                                logger.warning("⚠️ No hay clips de SFX válidos para mezclar")
                        else:
                            logger.warning("⚠️ No se pudieron crear clips de SFX válidos")
                        
                        # Cerrar el SFX original (ya se copió en los clips)
                        transition_sfx.close()
                    else:
                        logger.info(f"💡 SFX de transición no encontrado en: {sfx_path}. Continuando sin efectos de sonido.")
                        logger.info(f"💡 Para agregar SFX, coloca 'transition.mp3' en: assets/sfx/")
                except Exception as e:
                    logger.warning(f"⚠️ Error agregando SFX de transición: {e}. Continuando sin efectos de sonido.")
                    import traceback
                    logger.debug(traceback.format_exc())
            elif transition_cut_points and len(transition_cut_points) > 0:
                logger.debug(f"💡 SFX de transición disponible pero no hay audio compuesto para mezclar")
            
            # ============================================================
            # AGREGAR AUDIO COMPLETO AL VIDEO FINAL
            # ============================================================
            if final_audio_composite:
                # VALIDACIÓN CRÍTICA: Verificar que final_audio_composite es válido antes de agregarlo
                if final_audio_composite is None:
                    logger.error("❌ final_audio_composite es None, no se puede agregar audio")
                    logger.warning("⚠️ El video quedará sin audio")
                    final_audio_composite = None
                elif not hasattr(final_audio_composite, 'duration'):
                    logger.error("❌ final_audio_composite no tiene atributo duration")
                    logger.warning("⚠️ El video quedará sin audio")
                    try:
                        final_audio_composite.close()
                    except:
                        pass
                    final_audio_composite = None
                else:
                    try:
                        logger.info("🔊 Agregando pista de audio completa al video...")
                        
                        # VALIDACIÓN: Verificar que final_video_clip no es None
                        if final_video_clip is None:
                            logger.error("❌ final_video_clip es None, no se puede agregar audio")
                            raise ValueError("final_video_clip es None")
                        
                        # Validar duración del audio antes de agregarlo
                        audio_duration_check = final_audio_composite.duration
                        if audio_duration_check <= 0:
                            logger.error(f"❌ Duración de audio inválida: {audio_duration_check}")
                            raise ValueError(f"Duración de audio inválida: {audio_duration_check}")
                        
                        final_video_clip = final_video_clip.set_audio(final_audio_composite)
                        
                        # VALIDACIÓN POST-SET_AUDIO: Verificar que el clip resultante no es None
                        if final_video_clip is None:
                            logger.error("❌ set_audio retornó None")
                            raise ValueError("set_audio retornó None")
                        
                        # Asegurar que la duración coincida exactamente
                        final_video_clip = final_video_clip.set_duration(total_audio_duration)
                        
                        # VALIDACIÓN FINAL: Verificar que el clip final es válido
                        if final_video_clip is None:
                            logger.error("❌ set_duration retornó None después de agregar audio")
                            raise ValueError("set_duration retornó None")
                        
                        if not hasattr(final_video_clip, 'get_frame'):
                            logger.error("❌ final_video_clip no tiene get_frame después de agregar audio")
                            raise ValueError("final_video_clip no tiene get_frame")
                        
                        logger.success("✅ Audio completo agregado al video")
                        
                        # Cerrar el audio compuesto después de agregarlo (se copió)
                        try:
                            final_audio_composite.close()
                        except:
                            pass
                        
                        # Cerrar clips de audio individuales
                        for audio_clip in full_audio_clips:
                            try:
                                audio_clip.close()
                            except:
                                pass
                                
                    except Exception as e:
                        logger.error(f"❌ Error agregando audio al video: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
                        # Intentar continuar sin audio
                        logger.warning("⚠️ Continuando sin audio debido al error")
                        try:
                            if final_audio_composite:
                                final_audio_composite.close()
                        except:
                            pass
            else:
                logger.warning("⚠️ No hay audio disponible. El video quedará sin audio.")
                # Si no hay audio, usar la duración del video
                if total_video_duration <= 0:
                    total_video_duration = max(5.0, sum(
                        scene.get("duration") or scene.get("duration_estimate") or 4.0
                        for scene in scenes
                    ))
                final_video_clip = final_video_clip.set_duration(total_video_duration)
            
            final_clip = final_video_clip
            branding_clips_to_close = []
            
            # Asegurar que el video final esté en la resolución objetivo
            # Usar final_width y final_height que pueden venir de target_resolution
            if final_clip.size[0] != final_width or final_clip.size[1] != final_height:
                logger.info(f"Redimensionando a resolución objetivo: {final_width}x{final_height}...")
                # Redimensionar y recortar al centro para llenar el canvas sin bordes negros
                final_clip = self._resize_to_format(final_clip, final_width, final_height)
            
            if add_branding:
                target_fps = getattr(final_clip, "fps", 60) or 60
                
                subscribe_path = self._resolve_branding_asset(style_slug, "subscribe.png")
                if subscribe_path and subscribe_path.exists():
                    try:
                        overlay_start = max(0.0, total_video_duration * (2.0 / 3.0))
                        overlay_duration = min(3.0, total_video_duration - overlay_start)
                        if overlay_duration > 0.2:
                            subscribe_clip = (
                                ImageClip(str(subscribe_path))
                                .set_duration(overlay_duration)
                                .resize(width=int(final_clip.w * 0.6))
                                .set_position(("center", int(final_clip.h * 0.7)))
                                .set_start(overlay_start)
                                .fadein(0.5)
                                .fadeout(0.5)
                            )
                            # VALIDACIÓN: Verificar que ambos clips son válidos antes de crear composite
                            if final_clip is None or subscribe_clip is None:
                                logger.warning(f"⚠️ No se puede crear composite de subscribe: uno de los clips es None")
                            elif not hasattr(final_clip, 'get_frame') or not hasattr(subscribe_clip, 'get_frame'):
                                logger.warning(f"⚠️ No se puede crear composite de subscribe: uno de los clips no tiene get_frame")
                            else:
                                final_clip = CompositeVideoClip([final_clip, subscribe_clip]).set_duration(total_video_duration)
                            subscribe_clip.close()
                            logger.info("📢 Overlay 'subscribe' aplicado en el último tercio del video.")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo aplicar el overlay 'subscribe.png': {e}")
                
                intro_path = self._resolve_branding_asset(style_slug, "intro.mp4")
                outro_path = self._resolve_branding_asset(style_slug, "outro.mp4")
                concat_sequence = []
                
                def _prepare_brand_clip(path: Path):
                    """
                    Prepara un clip de branding (intro/outro) normalizándolo para que coincida
                    exactamente con la resolución y FPS del video principal.
                    
                    CRÍTICO: Si no se normaliza correctamente, FFmpeg fallará al concatenar.
                    """
                    clip = VideoFileClip(str(path))
                    
                    # 1. Silenciar audio del clip de branding (el audio se maneja por separado)
                    clip = clip.without_audio()
                    
                    # 2. Normalizar resolución: Redimensionar y recortar al formato exacto
                    clip = self._resize_to_format(clip, final_width, final_height)
                    
                    # 3. Normalizar FPS para que coincida exactamente con el video principal
                    clip = clip.set_fps(target_fps)
                    
                    # 4. Verificar que la resolución coincida exactamente
                    current_w, current_h = clip.size
                    if current_w != final_width or current_h != final_height:
                        logger.warning(f"⚠️ El clip de branding no se normalizó correctamente. Esperado: {final_width}x{final_height}, Obtenido: {current_w}x{current_h}")
                        # Forzar redimensionamiento final
                        clip = clip.resize((final_width, final_height))
                    
                    logger.debug(f"✅ Clip de branding normalizado: {final_width}x{final_height} @ {target_fps} FPS")
                    return clip
                
                if intro_path and intro_path.exists():
                    try:
                        intro_clip = _prepare_brand_clip(intro_path)
                        branding_clips_to_close.append(intro_clip)
                        concat_sequence.append(intro_clip)
                        logger.info("🎬 Intro branding detectado y agregado.")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo cargar intro.mp4: {e}")
                
                concat_sequence.append(final_clip)
                
                if outro_path and outro_path.exists():
                    try:
                        outro_clip = _prepare_brand_clip(outro_path)
                        branding_clips_to_close.append(outro_clip)
                        concat_sequence.append(outro_clip)
                        logger.info("🎬 Outro branding detectado y agregado.")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo cargar outro.mp4: {e}")
                
                if len(concat_sequence) > 1:
                    # VALIDACIÓN: Filtrar clips None antes de concatenar
                    valid_concat_sequence = []
                    for i, clip in enumerate(concat_sequence):
                        if clip is None:
                            logger.warning(f"⚠️ Clip {i} en concat_sequence es None, filtrando...")
                            continue
                        if not hasattr(clip, 'duration') or not hasattr(clip, 'get_frame'):
                            logger.warning(f"⚠️ Clip {i} en concat_sequence no tiene atributos necesarios, filtrando...")
                            continue
                        try:
                            if clip.duration <= 0:
                                logger.warning(f"⚠️ Clip {i} en concat_sequence tiene duración inválida, filtrando...")
                                continue
                            valid_concat_sequence.append(clip)
                        except Exception as e:
                            logger.warning(f"⚠️ Error validando clip {i} en concat_sequence: {e}, filtrando...")
                            continue
                    
                    if len(valid_concat_sequence) == 0:
                        logger.error("❌ Todos los clips en concat_sequence son inválidos")
                    elif len(valid_concat_sequence) == 1:
                        final_clip = valid_concat_sequence[0]
                        total_video_duration = final_clip.duration
                        logger.success("✅ Solo un clip válido en concat_sequence")
                    else:
                        final_clip = concatenate_videoclips(valid_concat_sequence, method="compose")
                        total_video_duration = final_clip.duration
                        logger.success("✅ Secuencia final con intro/outro ensamblada correctamente.")
            
            branding_watermark_text = self._load_branding_text(style_slug, "watermark.txt")
            effective_watermark_text = branding_watermark_text or watermark_text
            watermark_image_path = self._resolve_branding_asset(style_slug, "logo.png") or self._resolve_branding_asset(style_slug, "watermark.png")
            
            # Agregar marca de agua si se especifica
            if watermark_image_path or effective_watermark_text:
                try:
                    margin_x = 50
                    margin_y = 100
                    logger.info("Agregando watermark dinámico.")
                    
                    def _compute_position(element_w: int, element_h: int):
                        if watermark_position == "bottom-right":
                            pos_x = final_width - element_w - margin_x
                            pos_y = final_height - element_h - margin_y
                        elif watermark_position == "top-center":
                            pos_x = (final_width - element_w) / 2
                            pos_y = margin_y
                        elif watermark_position == "bottom-left":
                            pos_x = margin_x
                            pos_y = final_height - element_h - margin_y
                        elif watermark_position == "top-right":
                            pos_x = final_width - element_w - margin_x
                            pos_y = margin_y
                        else:
                            pos_x = final_width - element_w - margin_x
                            pos_y = final_height - element_h - margin_y
                        return pos_x, pos_y
                    
                    if watermark_image_path and watermark_image_path.exists():
                        watermark_img = ImageClip(str(watermark_image_path)).set_duration(final_clip.duration).set_fps(final_clip.fps)
                        target_width_img = min(int(final_width * 0.35), watermark_img.w)
                        watermark_img = watermark_img.resize(width=target_width_img)
                        img_w, img_h = watermark_img.size
                        pos_x, pos_y = _compute_position(img_w, img_h)
                        watermark_img = watermark_img.set_position((pos_x, pos_y), relative=False)
                        # VALIDACIÓN: Verificar que ambos clips son válidos
                        if final_clip is None or watermark_img is None:
                            logger.warning(f"⚠️ No se puede aplicar watermark de imagen: uno de los clips es None")
                        elif not hasattr(final_clip, 'get_frame') or not hasattr(watermark_img, 'get_frame'):
                            logger.warning(f"⚠️ No se puede aplicar watermark de imagen: uno de los clips no tiene get_frame")
                        else:
                            final_clip = CompositeVideoClip([final_clip, watermark_img])
                            logger.success("✅ Marca de agua por imagen aplicada.")
                    else:
                        fallback_text = effective_watermark_text
                        if not fallback_text:
                            style_handle_slug = self._normalize_style_slug(style_label or style_code or "MetratronTV")
                            if style_handle_slug and style_handle_slug != "general":
                                fallback_text = f"@{style_handle_slug.capitalize()}"
                            else:
                                fallback_text = "@MetratronTV"
                        if not fallback_text.startswith("@"):
                            fallback_text = f"@{fallback_text}"
                        font_candidates = ["Impact", "Arial-Bold", "Arial"]
                        font_size = max(34, int(final_height * 0.035))
                        shadow_offset = 3
                        shadow_kwargs = dict(
                            fontsize=font_size,
                            color='black',
                            stroke_color='black',
                            stroke_width=0,
                            method='label',
                            size=(None, None)
                        )
                        main_kwargs = dict(
                            fontsize=font_size,
                            color='white',
                            stroke_color='black',
                            stroke_width=1,
                            method='label',
                            size=(None, None)
                        )
                        def _create_text_clip(text: str, kwargs: dict):
                            last_error = None
                            for font_name in font_candidates:
                                try:
                                    return TextClip(text, font=font_name, **kwargs)
                                except Exception as exc:
                                    last_error = exc
                                    continue
                            raise last_error or RuntimeError("No fonts available for watermark text")
                        watermark_shadow = _create_text_clip(fallback_text, shadow_kwargs).set_duration(final_clip.duration).set_fps(final_clip.fps)
                        watermark_main = _create_text_clip(fallback_text, main_kwargs).set_duration(final_clip.duration).set_fps(final_clip.fps)
                        
                        text_w, text_h = watermark_main.size
                        pos_x_main, pos_y_main = _compute_position(text_w, text_h)
                        pos_x_shadow = pos_x_main + shadow_offset
                        pos_y_shadow = pos_y_main + shadow_offset
                        
                        watermark_shadow = watermark_shadow.set_position((pos_x_shadow, pos_y_shadow), relative=False)
                        watermark_shadow = watermark_shadow.set_opacity(0.35)
                        watermark_main = watermark_main.set_position((pos_x_main, pos_y_main), relative=False)
                        try:
                            watermark_main = watermark_main.set_opacity(0.6)
                        except (AttributeError, TypeError):
                            logger.debug("set_opacity no disponible para watermark textual.")
                        
                        # VALIDACIÓN: Verificar que todos los clips son válidos
                        watermark_clips = [c for c in [watermark_shadow, watermark_main] if c is not None]
                        if final_clip is None:
                            logger.warning(f"⚠️ No se puede aplicar watermark de texto: final_clip es None")
                        elif len(watermark_clips) == 0:
                            logger.warning(f"⚠️ No se puede aplicar watermark de texto: todos los clips de texto son None")
                        else:
                            # Verificar que todos tienen get_frame
                            all_valid = all(hasattr(c, 'get_frame') for c in watermark_clips) and hasattr(final_clip, 'get_frame')
                            if not all_valid:
                                logger.warning(f"⚠️ No se puede aplicar watermark de texto: algunos clips no tienen get_frame")
                            else:
                                final_clip = CompositeVideoClip([final_clip] + watermark_clips)
                                logger.success(f"✅ Marca de agua de texto aplicada ({watermark_position}).")
                except Exception as e:
                    logger.warning(f"⚠️ Error al agregar marca de agua: {e}. Continuando sin watermark...")
                    import traceback
                    logger.debug(traceback.format_exc())
            
            # Configuración Super 1080p para máxima calidad en redes sociales
            # Siempre usar bitrate alto (15 Mbps) para evitar pixelación en movimiento
            video_bitrate = bitrate or "15000k"  # 15 Mbps - Calidad de estudio
            audio_bitrate = "320k"  # Calidad de estudio para audio
            
            # ============================================================
            # FUNCIÓN DE VALIDACIÓN RECURSIVA DE CLIPS
            # ============================================================
            def validar_clip_recursivo(clip, nivel=0, path="root"):
                """Valida un clip y todos sus sub-clips recursivamente"""
                indent = "  " * nivel
                
                if clip is None:
                    logger.error(f"{indent}❌ {path}: es None")
                    return False
                
                if not hasattr(clip, 'get_frame'):
                    logger.error(f"{indent}❌ {path}: no tiene get_frame, tipo={type(clip)}")
                    return False
                
                # Obtener información básica
                try:
                    clip_type = type(clip).__name__
                    clip_duration = getattr(clip, 'duration', 'N/A')
                    logger.debug(f"{indent}✅ {path}: tipo={clip_type}, duración={clip_duration}")
                except Exception as e:
                    logger.warning(f"{indent}⚠️ {path}: error obteniendo info: {e}")
                
                # Si es CompositeVideoClip, revisar sus clips internos
                if hasattr(clip, 'clips') and clip.clips:
                    logger.debug(f"{indent}📁 {path}: CompositeVideoClip con {len(clip.clips)} clips internos")
                    for i, sub_clip in enumerate(clip.clips):
                        sub_path = f"{path}.clips[{i}]"
                        if not validar_clip_recursivo(sub_clip, nivel + 1, sub_path):
                            return False
                
                # Si tiene audio, validarlo también
                if hasattr(clip, 'audio') and clip.audio is not None:
                    audio_obj = clip.audio
                    logger.debug(f"{indent}🔊 {path}.audio: tipo={type(audio_obj).__name__}")
                    
                    # Revisar sub-clips de audio si es CompositeAudioClip
                    if hasattr(audio_obj, 'clips') and audio_obj.clips:
                        logger.debug(f"{indent}  📁 Audio tiene {len(audio_obj.clips)} clips internos")
                        for i, audio_clip in enumerate(audio_obj.clips):
                            if audio_clip is None:
                                logger.error(f"{indent}  ❌ {path}.audio.clips[{i}]: es None")
                                return False
                            if not hasattr(audio_clip, 'get_frame'):
                                logger.error(f"{indent}  ❌ {path}.audio.clips[{i}]: no tiene get_frame, tipo={type(audio_clip)}")
                                return False
                            logger.debug(f"{indent}  ✅ {path}.audio.clips[{i}]: tipo={type(audio_clip).__name__}")
                
                return True
            
            def limpiar_audio_invalido(clip):
                """Remueve audio inválido de un clip recursivamente"""
                if clip is None:
                    return None
                
                # Si es CompositeVideoClip, limpiar sus sub-clips primero
                if hasattr(clip, 'clips') and clip.clips:
                    clips_limpios = []
                    for sub_clip in clip.clips:
                        sub_clip_limpio = limpiar_audio_invalido(sub_clip)
                        if sub_clip_limpio is not None:
                            clips_limpios.append(sub_clip_limpio)
                    
                    if len(clips_limpios) != len(clip.clips):
                        logger.warning(f"⚠️ Se filtraron {len(clip.clips) - len(clips_limpios)} sub-clips inválidos")
                    
                    if clips_limpios:
                        try:
                            return CompositeVideoClip(clips_limpios)
                        except Exception as e:
                            logger.error(f"❌ Error recreando CompositeVideoClip: {e}")
                            return None
                    else:
                        return None
                
                # Limpiar audio inválido del clip
                if hasattr(clip, 'audio') and clip.audio is not None:
                    audio_obj = clip.audio
                    
                    # Verificar si el audio es válido
                    audio_invalido = False
                    
                    # Si es CompositeAudioClip, verificar sus clips internos
                    if hasattr(audio_obj, 'clips') and audio_obj.clips:
                        for audio_sub in audio_obj.clips:
                            if audio_sub is None or not hasattr(audio_sub, 'get_frame'):
                                audio_invalido = True
                                logger.warning(f"⚠️ Audio contiene clip None o inválido, removiendo audio")
                                break
                    elif not hasattr(audio_obj, 'get_frame'):
                        audio_invalido = True
                        logger.warning(f"⚠️ Audio no tiene get_frame, removiendo audio")
                    
                    if audio_invalido:
                        try:
                            return clip.without_audio()
                        except Exception as e:
                            logger.warning(f"⚠️ Error removiendo audio: {e}")
                            return clip
                
                return clip
            
            # VALIDACIÓN FINAL CRÍTICA: Verificar que final_clip es válido antes de renderizar
            if final_clip is None:
                raise ValueError("❌ final_clip es None. No se puede renderizar el video.")
            
            # Verificar que tiene los atributos necesarios
            if not hasattr(final_clip, 'duration'):
                raise ValueError("❌ final_clip no tiene atributo 'duration'")
            
            if not hasattr(final_clip, 'get_frame'):
                raise ValueError("❌ final_clip no tiene atributo 'get_frame'. No es un VideoClip válido.")
            
            # Verificar duración válida
            try:
                clip_duration = final_clip.duration
                if clip_duration is None or clip_duration <= 0:
                    raise ValueError(f"❌ final_clip tiene duración inválida: {clip_duration}")
                logger.info(f"✅ Clip final validado: duración {clip_duration:.2f}s, tipo: {type(final_clip)}")
            except Exception as e:
                logger.error(f"❌ Error verificando duración del clip: {e}")
                raise ValueError(f"No se puede verificar la duración del clip: {e}")
            
            # DIAGNÓSTICO RECURSIVO COMPLETO
            logger.info("🔍 Iniciando validación recursiva del clip final...")
            if not validar_clip_recursivo(final_clip, nivel=0, path="final_clip"):
                logger.error("❌ La validación recursiva encontró elementos None o inválidos")
                logger.warning("🔄 Intentando limpiar audio inválido...")
                final_clip = limpiar_audio_invalido(final_clip)
                
                if final_clip is None:
                    raise ValueError("❌ No se pudo limpiar el clip. Todos los sub-clips son inválidos.")
                
                # Re-validar después de la limpieza
                logger.info("🔍 Re-validando clip después de la limpieza...")
                if not validar_clip_recursivo(final_clip, nivel=0, path="final_clip_limpio"):
                    raise ValueError("❌ El clip aún contiene elementos inválidos después de la limpieza")
                else:
                    logger.success("✅ Clip validado correctamente después de la limpieza")
            else:
                logger.success("✅ Validación recursiva completada: todos los clips son válidos")
            
            # Renderizar video final con configuración optimizada
            logger.info(f"Renderizando video final en {final_width}x{final_height} @ 60 FPS")
            logger.info(f"Bitrate: {video_bitrate} (video) / {audio_bitrate} (audio)")
            
            try:
                final_clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    fps=60,  # 60 FPS para máxima fluidez en móviles
                    preset='slow',  # Mejor compresión y calidad (más lento pero mejor resultado)
                    bitrate=video_bitrate,
                    audio_bitrate=audio_bitrate,
                    threads=4,
                    logger=None
                )
            except AttributeError as e:
                error_msg = str(e)
                if "'NoneType' object has no attribute 'get_frame'" in error_msg:
                    logger.error("❌ ERROR CRÍTICO: Clip contiene elemento None con get_frame")
                    logger.error(f"   Detalles del clip:")
                    logger.error(f"   - Tipo: {type(final_clip)}")
                    logger.error(f"   - Tiene audio: {hasattr(final_clip, 'audio') and final_clip.audio is not None}")
                    
                    # DIAGNÓSTICO RECURSIVO COMPLETO - Mostrar TODOS los sub-clips
                    logger.error("🔍 Iniciando diagnóstico recursivo completo...")
                    def diagnosticar_clip_recursivo(clip, nivel=0, path="final_clip"):
                        """Diagnostica un clip y todos sus sub-clips recursivamente"""
                        indent = "   " + ("  " * nivel)
                        
                        if clip is None:
                            logger.error(f"{indent}❌ {path}: es None")
                            return
                        
                        clip_type = type(clip).__name__
                        es_none = clip is None
                        tiene_get_frame = hasattr(clip, 'get_frame')
                        duracion = getattr(clip, 'duration', 'N/A')
                        
                        logger.error(f"{indent}📹 {path}:")
                        logger.error(f"{indent}   - Tipo: {clip_type}")
                        logger.error(f"{indent}   - Es None: {es_none}")
                        logger.error(f"{indent}   - Tiene get_frame: {tiene_get_frame}")
                        logger.error(f"{indent}   - Duración: {duracion}")
                        
                        # Si es CompositeVideoClip, revisar TODOS sus clips internos RECURSIVAMENTE
                        if hasattr(clip, 'clips') and clip.clips:
                            logger.error(f"{indent}   - 📁 CompositeVideoClip con {len(clip.clips)} clips internos:")
                            for i, sub_clip in enumerate(clip.clips):
                                sub_path = f"{path}.clips[{i}]"
                                # Llamar recursivamente para revisar clips anidados dentro de este sub-clip
                                diagnosticar_clip_recursivo(sub_clip, nivel + 1, sub_path)
                        
                        # Revisar audio si existe
                        if hasattr(clip, 'audio') and clip.audio is not None:
                            audio_obj = clip.audio
                            audio_type = type(audio_obj).__name__
                            logger.error(f"{indent}   - 🔊 Audio: tipo={audio_type}")
                            
                            # Revisar sub-clips de audio si es CompositeAudioClip
                            if hasattr(audio_obj, 'clips') and audio_obj.clips:
                                logger.error(f"{indent}      - 📁 Audio tiene {len(audio_obj.clips)} clips internos:")
                                for i, audio_clip in enumerate(audio_obj.clips):
                                    audio_path = f"{path}.audio.clips[{i}]"
                                    if audio_clip is None:
                                        logger.error(f"{indent}      ❌ {audio_path}: es None")
                                    else:
                                        audio_clip_type = type(audio_clip).__name__
                                        audio_clip_has_get_frame = hasattr(audio_clip, 'get_frame')
                                        logger.error(f"{indent}      - {audio_path}: tipo={audio_clip_type}, tiene get_frame={audio_clip_has_get_frame}")
                                        if not audio_clip_has_get_frame:
                                            logger.error(f"{indent}      ❌ PROBLEMA ENCONTRADO: {audio_path} no tiene get_frame")
                    
                    diagnosticar_clip_recursivo(final_clip, nivel=0, path="final_clip")
                    
                    logger.error("❌ No se puede renderizar. El clip contiene componentes None inválidos.")
                    raise ValueError("Clip contiene componentes None inválidos que causan error en get_frame")
                else:
                    # Re-lanzar si es otro tipo de AttributeError
                    raise
            
            # Liberar recursos
            logger.info("Liberando recursos...")
            final_clip.close()
            
            # Cerrar clip looped si existe
            if 'looped_video_temp' in locals() and looped_video_temp:
                try:
                    looped_video_temp.close()
                except:
                    pass
            
            for clip in final_clips:  # Usar final_clips en lugar de clips
                try:
                    if clip is not None:
                        # Cerrar el clip compuesto
                        clip.close()
                        # Cerrar clips originales si existen
                        if hasattr(clip, '_original_video'):
                            try:
                                clip._original_video.close()
                            except:
                                pass
                        if hasattr(clip, '_original_audio'):
                            try:
                                clip._original_audio.close()
                            except:
                                pass
                except:
                    pass
            
            # Cerrar clips de branding (intro/outro)
            for clip in branding_clips_to_close:
                try:
                    clip.close()
                except:
                    pass
            
            # Cerrar clips de video limpios
            for clip in video_only_clips:
                try:
                    if clip is not None:
                        clip.close()
                except:
                    pass
            
            logger.success(f"Video renderizado exitosamente: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error renderizando video: {e}")
            # Cerrar todos los clips en caso de error
            for clip in clips:
                try:
                    if clip is not None:
                        clip.close()
                except:
                    pass
            raise

