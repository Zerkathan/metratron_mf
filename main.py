import os
import time
import asyncio
from typing import Optional, Dict, Any
from loguru import logger
from dotenv import load_dotenv

# --- IMPORTACIONES DE MÓDULOS INTERNOS ---
try:
    from src.script_generator import ViralScriptGenerator
    HAS_SCRIPT_GEN = True
except ImportError as e:
    logger.error(f"Error importando ViralScriptGenerator: {e}")
    HAS_SCRIPT_GEN = False
    ViralScriptGenerator = None

try:
    from src.audio_engine import AudioEngine
    HAS_AUDIO_ENGINE = True
except ImportError as e:
    logger.error(f"Error importando AudioEngine: {e}")
    HAS_AUDIO_ENGINE = False
    AudioEngine = None

try:
    from src.stock_manager import StockEngine
    HAS_STOCK = True
except ImportError as e:
    logger.error(f"Error importando StockEngine: {e}")
    HAS_STOCK = False
    StockEngine = None

try:
    from src.asset_manager import AssetManager
    HAS_ASSET = True
except ImportError as e:
    logger.error(f"Error importando AssetManager: {e}")
    HAS_ASSET = False
    AssetManager = None

try:
    from src.video_editor import VideoEditor
    HAS_VIDEO_EDITOR = True
except ImportError as e:
    logger.error(f"Error importando VideoEditor: {e}")
    HAS_VIDEO_EDITOR = False
    VideoEditor = None

try:
    from src.metadata_generator import MetadataGenerator
    HAS_METADATA = True
except ImportError as e:
    logger.error(f"Error importando MetadataGenerator: {e}")
    HAS_METADATA = False
    MetadataGenerator = None

try:
    from src.music_manager import MusicManager
    HAS_MUSIC = True
except ImportError as e:
    logger.error(f"Error importando MusicManager: {e}")
    HAS_MUSIC = False
    MusicManager = None

try:
    from src.analytics import AnalyticsManager
    HAS_ANALYTICS = True
except ImportError as e:
    logger.error(f"Error importando AnalyticsManager: {e}")
    HAS_ANALYTICS = False
    AnalyticsManager = None

try:
    from src.cleaner import DiskCleaner
    HAS_CLEANER = True
except ImportError as e:
    logger.error(f"Error importando DiskCleaner: {e}")
    HAS_CLEANER = False
    DiskCleaner = None

try:
    from src.thumbnail_generator import ThumbnailMaker
    HAS_THUMBNAIL = True
except ImportError as e:
    logger.error(f"Error importando ThumbnailMaker: {e}")
    HAS_THUMBNAIL = False
    ThumbnailMaker = None

# Módulos Opcionales (para que no crashee si faltan)
try:
    from src.audio_processor import AudioEngineer
    HAS_AUDIO_PROC = True
except ImportError:
    HAS_AUDIO_PROC = False

try:
    from src.uploader import YouTubeUploader, TikTokUploader
    HAS_UPLOADER = True
except ImportError:
    HAS_UPLOADER = False

try:
    from src.console_ui import Console
    HAS_CONSOLE = True
except ImportError:
    HAS_CONSOLE = False

# Configuración
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "assets", "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class AutoViralBot:
    def __init__(self):
        """Inicializa todos los subsistemas del bot."""
        logger.info("🤖 Inicializando AutoViral-Bot (Arquitectura Segura v3.0)...")
        
        if not HAS_SCRIPT_GEN or not ViralScriptGenerator:
            raise ImportError("ViralScriptGenerator es obligatorio. Instala las dependencias necesarias.")
        self.script_generator = ViralScriptGenerator()
        
        if not HAS_AUDIO_ENGINE or not AudioEngine:
            raise ImportError("AudioEngine es obligatorio. Instala las dependencias necesarias.")
        self.audio_engine = AudioEngine()
        
        if not HAS_STOCK or not StockEngine:
            raise ImportError("StockEngine es obligatorio. Instala las dependencias necesarias.")
        self.stock_manager = StockEngine()
        
        if not HAS_ASSET or not AssetManager:
            raise ImportError("AssetManager es obligatorio. Instala las dependencias necesarias.")
        self.asset_manager = AssetManager()
        
        if not HAS_VIDEO_EDITOR or not VideoEditor:
            raise ImportError("VideoEditor es obligatorio. Instala moviepy: pip install moviepy")
        self.video_editor = VideoEditor()
        
        if not HAS_MUSIC or not MusicManager:
            raise ImportError("MusicManager es obligatorio. Instala las dependencias necesarias.")
        self.music_manager = MusicManager()
        
        if not HAS_METADATA or not MetadataGenerator:
            raise ImportError("MetadataGenerator es obligatorio. Instala las dependencias necesarias.")
        self.metadata_generator = MetadataGenerator()
        
        if not HAS_ANALYTICS or not AnalyticsManager:
            raise ImportError("AnalyticsManager es obligatorio. Instala las dependencias necesarias.")
        self.analytics = AnalyticsManager()
        
        if not HAS_CLEANER or not DiskCleaner:
            raise ImportError("DiskCleaner es obligatorio. Instala las dependencias necesarias.")
        self.cleaner = DiskCleaner()
        
        if not HAS_THUMBNAIL or not ThumbnailMaker:
            raise ImportError("ThumbnailMaker es obligatorio. Instala las dependencias necesarias.")
        self.thumbnail_maker = ThumbnailMaker()
        
        self.audio_processor = AudioEngineer() if HAS_AUDIO_PROC else None
        
        self.yt_uploader = None
        self.tt_uploader = None
        
        if HAS_UPLOADER:
            try:
                self.yt_uploader = YouTubeUploader()
            except Exception: pass
            try:
                self.tt_uploader = TikTokUploader()
            except Exception: pass

        logger.success("✅ Sistemas cargados correctamente.")

    async def generate_video(self, topic: str, **kwargs) -> Dict[str, Any]:
        """
        Genera un video completo usando un Diccionario de Configuración Seguro.
        Usa **kwargs para absorber cualquier variable y evitar errores de 'UnboundLocal'.
        """
        
        # --- 🛡️ CAJA FUERTE DE CONFIGURACIÓN 🛡️ ---
        # Aquí extraemos las variables de forma segura. Si no existen, usamos el valor por defecto.
        # NUNCA dará error de 'variable not defined'.
        config = {
            "duration": kwargs.get("duration_minutes", 1.0),
            "style": kwargs.get("style_prompt", "General"),
            "voice": kwargs.get("voice", "es-MX-JorgeNeural"),
            "music_vol": kwargs.get("music_volume", 0.1),
            "subtitles": kwargs.get("use_subtitles", True),
            
            # Variables "Peligrosas" ahora blindadas
            "news_mode": kwargs.get("use_news_mode", False),
            "runway": kwargs.get("use_runway", False),
            "dalle": kwargs.get("use_dalle", False),
            "branding": kwargs.get("use_branding", False),
            
            # Uploads
            "up_yt": kwargs.get("upload_youtube", False),
            "up_tt": kwargs.get("upload_tiktok", False),
            "up_ig": kwargs.get("upload_instagram", False),
            
            # Textos Manuales
            "title": kwargs.get("custom_title", None),
            "desc": kwargs.get("custom_desc", None),
            "tags": kwargs.get("custom_tags", None),
            
            # Callbacks
            "callback": kwargs.get("progress_callback", None)
        }
        # ----------------------------------------------

        def notify(pct, msg):
            # Convertir porcentaje (0-100) a valor decimal (0.0-1.0) para el callback
            # Si el valor es mayor que 1, asumimos que es un porcentaje (0-100)
            if pct > 1.0:
                progress_decimal = pct / 100.0
            else:
                progress_decimal = float(pct)  # Asegurar que sea float
            
            if config["callback"]:
                try:
                    config["callback"](progress_decimal, msg)
                except Exception as e:
                    logger.warning(f"Error en callback de progreso: {e}")
            if HAS_CONSOLE: Console.log_step(msg)
            else: logger.info(msg)

        try:
            notify(5, f"🚀 Iniciando Protocolo para: {topic}")
            logger.debug(f"Configuración activa: {config}")

            # 1. GUION
            notify(15, "🧠 Generando Guion Neuronal...")
            
            # Obtener datos de noticias de kwargs si existen
            news_data = kwargs.get("news_data", None)
            news_context = kwargs.get("news_context", None)
            
            # Obtener style_code y style_label de kwargs o config
            style_code = kwargs.get("style_code", None)
            style_label = kwargs.get("style_label", None)
            
            # Si no se proporciona style_code, intentar extraerlo de config["style"]
            if not style_code and config.get("style"):
                style_input = config["style"].upper().strip()
                # Normalización simple del estilo
                if "HORROR" in style_input or "CREEPY" in style_input:
                    style_code = "HORROR"
                elif "MOTIVACION" in style_input or "ESTOIC" in style_input:
                    style_code = "MOTIVACION"
                elif "MUSICAL" in style_input or "VISUALIZER" in style_input:
                    style_code = "MUSICAL"
                elif "LUJO" in style_input or "BUSINESS" in style_input:
                    style_code = "LUJO"
                elif "CRIMEN" in style_input or "MISTERIO" in style_input:
                    style_code = "CRIMEN"
                elif "HUMOR" in style_input or "RANDOM" in style_input:
                    style_code = "HUMOR"
                elif "FUTURISMO" in style_input or "FUTUR" in style_input:
                    style_code = "FUTURISMO"
                elif "TECH" in style_input or "IA" in style_input:
                    style_code = "TECH"
                elif "SALUD" in style_input or "BIENESTAR" in style_input:
                    style_code = "SALUD"
                elif "RELIGION" in style_input or "FE" in style_input:
                    style_code = "RELIGION"
                elif "CUSTOM" in style_input or "PERSONALIZ" in style_input:
                    style_code = "CUSTOM"
                else:
                    style_code = "CURIOSIDADES"  # Default
            
            # Generar script con parámetros de noticias si están disponibles
            script_data = self.script_generator.generate_script(
                topic,
                config["duration"],
                config["style"],
                style_code=style_code or "CURIOSIDADES",
                use_news_mode=config["news_mode"],
                news_data=news_data,
                news_context=news_context
            )
            if not script_data: raise ValueError("El guion llegó vacío.")

            # 2. AUDIO
            notify(30, "🎙️ Sintetizando Voz...")
            audio_paths = []
            for i, scene in enumerate(script_data):
                if config["voice"] == "NO_VOICE" or not config["voice"]:
                    scene['audio_path'] = None
                    continue
                
                out_audio = os.path.join(TEMP_DIR, f"tts_{i}_{int(time.time())}.mp3")
                text = scene.get('text', '')
                if text:
                    await self.audio_engine.generate_audio(text, config["voice"], out_audio)
                    # Procesar audio (Speed/Silence) si existe el procesador
                    if self.audio_processor:
                        # Aquí podrías añadir lógica de speed si la configuras en kwargs
                        pass
                    scene['audio_path'] = out_audio
                    audio_paths.append(out_audio)
                else:
                    scene['audio_path'] = None

            # 3. VISUALES
            notify(50, "👁️ Generando Universo Visual...")
            for idx, scene in enumerate(script_data):
                query = scene.get('visual_query', topic)
                visual_path = None
                scene_text = scene.get('text', query)
                scene_duration = scene.get('duration', 5.0)
                
                # Prioridad 1: Runway (Si está activo y configurado)
                if config["runway"]:
                    # Lógica de Runway aquí
                    pass 
                
                # Prioridad 2: Stock (Pexels/Pixabay)
                if not visual_path:
                    visual_path = self.stock_manager.get_visual(query, orientation="portrait")
                
                # Prioridad 3: DALL-E 3 (Fallback)
                if not visual_path or config["dalle"]:
                    if config["dalle"]: logger.info("🎨 Forzando DALL-E 3...")
                    else: logger.warning("⚠️ Stock falló. Usando DALL-E 3 como rescate.")
                    
                    try:
                        img_path = self.stock_manager.generate_dalle_image(query)
                        # Aplicar Ken Burns
                        visual_path = self.video_editor.create_dynamic_image_clip(img_path, duration=scene_duration)
                    except Exception as e:
                        logger.error(f"DALL-E Falló: {e}")
                
                # Prioridad 4: FALLBACK DE EMERGENCIA - Imagen estática (Si todo falla)
                if not visual_path:
                    logger.error(f"❌ Todos los métodos de obtención de visuales fallaron para: '{query}'")
                    logger.warning(f"🚨 Usando imagen de emergencia como penúltimo recurso...")
                    try:
                        # Crear imagen de emergencia con texto de la escena
                        emergency_img_path = self.video_editor.create_emergency_image(
                            text=scene_text,
                            target_width=1080,
                            target_height=1920,
                            background_color="#1a1a1a"  # Gris oscuro profesional
                        )
                        if emergency_img_path:
                            # Aplicar Ken Burns a la imagen de emergencia (igual que DALL-E)
                            visual_path = self.video_editor.create_dynamic_image_clip(
                                emergency_img_path, 
                                duration=scene_duration
                            )
                            logger.success(f"✅ Clip de emergencia (imagen) creado para escena {idx + 1}: '{query[:50]}...'")
                        else:
                            logger.error(f"❌ ERROR: No se pudo crear imagen de emergencia")
                            visual_path = None
                    except Exception as e:
                        logger.error(f"❌ ERROR: Fallo al crear clip de emergencia (imagen): {e}")
                        visual_path = None
                
                # Prioridad 5: FALLBACK ABSOLUTO - Clip MoviePy directo (Si TODO falla)
                if not visual_path:
                    logger.error(f"❌ ERROR CRÍTICO: Todos los métodos de emergencia fallaron para escena {idx + 1}")
                    logger.warning(f"🚨 Usando clip MoviePy directo como ÚLTIMO RECURSO ABSOLUTO...")
                    try:
                        # Crear clip de emergencia directamente con MoviePy (sin archivos externos)
                        emergency_clip = self.video_editor.create_emergency_clip(
                            text=scene_text,
                            duration=scene_duration,
                            target_width=1080,
                            target_height=1920,
                            background_color="#1a1a1a"
                        )
                        
                        if emergency_clip:
                            # Guardar el clip en un archivo temporal con el nombre esperado por process_scene
                            emergency_video_path = os.path.join(TEMP_DIR, f"scene_{idx:02d}_video.mp4")
                            
                            # Renderizar el clip de emergencia a archivo
                            logger.info(f"💾 Guardando clip de emergencia en: {emergency_video_path}")
                            emergency_clip.write_videofile(
                                emergency_video_path,
                                fps=24,
                                codec='libx264',
                                audio=False,
                                preset='ultrafast',
                                logger=None  # Silenciar logs de MoviePy
                            )
                            emergency_clip.close()
                            
                            # Verificar que el archivo se creó correctamente
                            if os.path.exists(emergency_video_path) and os.path.getsize(emergency_video_path) > 0:
                                visual_path = emergency_video_path
                                logger.success(f"✅ Clip de emergencia MoviePy guardado exitosamente para escena {idx + 1}")
                            else:
                                logger.error(f"❌ El archivo de emergencia no se creó correctamente")
                                visual_path = None
                        else:
                            logger.error(f"❌ create_emergency_clip retornó None")
                            visual_path = None
                            
                    except Exception as e:
                        logger.error(f"❌ ERROR CRÍTICO: Fallo al crear clip de emergencia MoviePy: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
                        visual_path = None
                
                # Asegurar que SIEMPRE hay un visual_path válido (nunca None)
                if not visual_path:
                    logger.critical(f"🔥 ERROR FATAL: No se pudo crear ningún clip para escena {idx + 1}. Esto no debería pasar.")
                    logger.critical(f"🔥 La escena será omitida y el video puede fallar si todas las escenas fallan.")
                else:
                    logger.info(f"✅ Visual asignado para escena {idx + 1}: {os.path.basename(visual_path) if isinstance(visual_path, str) else 'Clip en memoria'}")
                
                scene['video_path'] = visual_path
            
            # Verificar que al menos una escena tenga visual antes de renderizar
            scenes_with_visual = [s for s in script_data if s.get('video_path') is not None]
            
            # Verificar también que los archivos existen (si son rutas de archivo)
            valid_scenes = []
            for scene in scenes_with_visual:
                video_path = scene.get('video_path')
                if video_path and isinstance(video_path, str):
                    if os.path.exists(video_path):
                        valid_scenes.append(scene)
                    else:
                        logger.warning(f"⚠️ Archivo de video no existe: {video_path}. Omitiendo escena.")
                elif video_path:
                    # Si no es string, puede ser un clip en memoria (no debería pasar con la nueva implementación)
                    valid_scenes.append(scene)
            
            if not valid_scenes:
                raise ValueError("❌ ¡CRÍTICO! Ninguna escena tiene visual válido. El video no puede ser renderizado.")
            
            missing_count = len(script_data) - len(valid_scenes)
            if missing_count > 0:
                logger.warning(f"⚠️ {missing_count} escena(s) quedaron sin visual válido y serán filtradas del render.")
                # Filtrar escenas sin visual antes de renderizar
                script_data = valid_scenes
            else:
                logger.success(f"✅ Todas las {len(script_data)} escenas tienen visuales válidos.")

            # 4. RENDER
            notify(75, "🎬 Renderizando Master (Esto toma tiempo)...")
            final_path = os.path.join(OUTPUT_DIR, f"metratron_{int(time.time())}.mp4")
            
            # Música
            bg_music = self.music_manager.get_random_music(config["style"])
            
            self.video_editor.render_final_video(
                script_data,
                output_path=final_path,
                background_music=bg_music,
                music_volume=config["music_vol"],
                use_subtitles=config["subtitles"],
                watermark_text=kwargs.get("watermark_text", None),
                enable_color_grading=kwargs.get("enable_color_grading", False),
                use_crossfade=kwargs.get("use_crossfade_transitions", False),
                style_code=style_code,
                style_label=style_label,
                target_resolution=(1080, 1920)
            )

            # 5. POST-PRODUCCIÓN
            notify(90, "✨ Empaquetando producto...")
            thumb_path = final_path.replace(".mp4", ".jpg")
            try:
                hook = script_data[0].get('text', topic)
                self.thumbnail_maker.generate_thumbnail(final_path, hook, thumb_path)
            except: pass

            # Registro
            self.analytics.log_generation("Auto", topic, config["duration"]*60, "Success")
            self.cleaner.clean_temp_folder()

            notify(100, "✅ Producción Finalizada.")
            return {"video_path": final_path, "thumbnail_path": thumb_path, "status": "success"}

        except Exception as e:
            logger.exception("🔥 ERROR CRÍTICO EN PRODUCCIÓN")
            notify(0, f"❌ Error: {str(e)}")
            raise e