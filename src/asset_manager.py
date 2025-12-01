"""
AssetManager: Descarga videos de stock desde múltiples fuentes o genera videos con Runway.
Ahora usa StockEngine para combinar Pexels, Pixabay y soportar imágenes animadas.

🔧 VERSIÓN CORREGIDA - Fix para error "Clip contiene componentes None inválidos"
"""

import os
import requests
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

# Importar StockEngine
try:
    from src.stock_manager import StockEngine
    STOCK_ENGINE_AVAILABLE = True
except ImportError as e:
    STOCK_ENGINE_AVAILABLE = False
    logger.warning(f"⚠️ StockEngine no disponible: {e}")

# Importar RunwayGenerator si está disponible
try:
    from src.runway_manager import RunwayGenerator, create_runway_generator
    RUNWAY_AVAILABLE = True
except (ImportError, ValueError) as e:
    RUNWAY_AVAILABLE = False
    logger.debug(f"Runway no disponible: {e}")


class AssetManager:
    """Gestiona la descarga de assets (videos de stock) o generación con Runway."""
    
    def __init__(
        self,
        pexels_api_key: Optional[str] = None,
        use_runway: bool = False,
        runway_api_key: Optional[str] = None,
        runway_mode: str = "Solo Gancho (Escena 1)",
        motion_intensity: int = 5
    ):
        """
        Inicializa el gestor de assets.
        
        Args:
            pexels_api_key: Clave API de Pexels (opcional, puede estar en .env)
            use_runway: Si True, usa Runway para generar videos
            runway_api_key: Clave API de Runway (opcional, puede estar en .env)
            runway_mode: "Solo Gancho (Escena 1)" o "Todas las Escenas"
            motion_intensity: Intensidad de movimiento para Runway (1-10)
        """
        self.api_key = pexels_api_key or os.getenv("PEXELS_API_KEY")
        if not self.api_key:
            raise ValueError("PEXELS_API_KEY no encontrada. Configúrala en .env o pasa pexels_api_key.")
        
        self.base_url = "https://api.pexels.com/videos"
        self.headers = {"Authorization": self.api_key}
        
        # Inicializar StockEngine para búsqueda unificada
        self.stock_engine = None
        if STOCK_ENGINE_AVAILABLE:
            try:
                self.stock_engine = StockEngine()
                logger.success("✅ StockEngine inicializado (Pexels + Pixabay)")
            except Exception as e:
                logger.warning(f"⚠️ Error inicializando StockEngine: {e}. Usando solo Pexels.")
                self.stock_engine = None
        
        # Configuración de Runway
        self.use_runway = use_runway
        self.runway_mode = runway_mode
        self.motion_intensity = motion_intensity
        self.runway_generator = None
        
        if use_runway and RUNWAY_AVAILABLE:
            try:
                self.runway_generator = create_runway_generator(runway_api_key)
                if self.runway_generator:
                    logger.success("✅ RunwayGenerator activado")
                else:
                    logger.warning("⚠️ Runway no disponible, usando Pexels")
                    self.use_runway = False
            except Exception as e:
                logger.warning(f"⚠️ Error inicializando Runway: {e}. Usando Pexels.")
                self.use_runway = False
        
        logger.info(f"AssetManager inicializado (Runway: {'✅' if self.use_runway else '❌'})")
    
    def _create_placeholder_clip(self, output_dir: Path, scene_idx: int, duration: float = 5.0) -> Optional[str]:
        """
        🔧 NUEVO: Crea un clip de video negro como placeholder cuando no hay recurso disponible.
        Esto evita el error "Clip contiene componentes None inválidos" en get_frame.
        
        Args:
            output_dir: Directorio donde guardar el placeholder
            scene_idx: Índice de la escena
            duration: Duración del placeholder en segundos
        
        Returns:
            Ruta del archivo de placeholder o None si falla
        """
        try:
            from moviepy.editor import ColorClip
            
            placeholder_path = output_dir / f"scene_{scene_idx:02d}_placeholder.mp4"
            
            logger.info(f"🎬 Creando placeholder negro para escena {scene_idx + 1} ({duration}s)...")
            
            # Crear clip negro de 1080x1920 (vertical 9:16)
            black_clip = ColorClip(size=(1080, 1920), color=(0, 0, 0), duration=duration)
            black_clip = black_clip.set_fps(30)
            
            # Exportar con configuración mínima para rapidez
            black_clip.write_videofile(
                str(placeholder_path),
                codec='libx264',
                fps=30,
                preset='ultrafast',
                audio=False,
                logger=None,
                verbose=False
            )
            black_clip.close()
            
            logger.success(f"✅ Placeholder negro creado: {placeholder_path.name}")
            return str(placeholder_path)
            
        except Exception as e:
            logger.error(f"❌ Error creando placeholder: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _search_video(self, query: str, per_page: int = 1) -> Optional[Dict]:
        """
        Busca un video en Pexels.
        
        Args:
            query: Consulta de búsqueda
            per_page: Videos por página
        
        Returns:
            Datos del primer video encontrado o None
        """
        logger.info(f"Buscando video en Pexels: {query}")
        
        try:
            response = requests.get(
                f"{self.base_url}/search",
                headers=self.headers,
                params={"query": query, "per_page": per_page}
            )
            response.raise_for_status()
            
            data = response.json()
            videos = data.get("videos", [])
            
            if videos:
                logger.success(f"Video encontrado: {query}")
                return videos[0]
            else:
                logger.warning(f"No se encontraron videos para: {query}")
                return None
                
        except Exception as e:
            logger.error(f"Error buscando video: {e}")
            return None
    
    def _download_video(self, video_data: Dict, output_path: str) -> bool:
        """
        Descarga un video desde Pexels.
        
        Args:
            video_data: Datos del video de la API
            output_path: Ruta de salida
        
        Returns:
            True si la descarga fue exitosa
        """
        logger.info(f"Descargando video: {Path(output_path).name}")
        
        try:
            # Obtener la mejor calidad disponible
            video_files = video_data.get("video_files", [])
            if not video_files:
                logger.error("No hay archivos de video disponibles")
                return False
            
            # Preferir HD, luego menor calidad
            video_file = None
            for quality in ["hd", "sd", "sd", "hd"]:  # Intentar HD primero
                for vf in video_files:
                    if vf.get("quality") == quality or quality == "sd":
                        video_file = vf
                        break
                if video_file:
                    break
            
            if not video_file:
                video_file = video_files[0]  # Usar el primero disponible
            
            video_url = video_file["link"]
            
            # Descargar el video
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            # Guardar el video
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.success(f"Video descargado: {Path(output_path).name}")
            return True
            
        except Exception as e:
            logger.error(f"Error descargando video: {e}")
            return False
    
    def download_videos_for_script(self, script_data: Dict, output_dir: str = "assets/temp") -> List[str]:
        """
        Descarga videos para todas las escenas de un guion.
        Usa Runway si está activo, sino usa Pexels.
        
        🔧 CORREGIDO: Ya no agrega None a la lista. Si falla, crea un placeholder negro.
        
        Args:
            script_data: Diccionario con el guion (debe tener 'scenes')
            output_dir: Directorio de salida
        
        Returns:
            Lista de rutas de videos descargados (sin None)
        """
        scenes = script_data.get("scenes", [])
        logger.info(f"Iniciando {'generación' if self.use_runway else 'descarga'} de {len(scenes)} videos...")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        video_files = []
        skipped_scenes = []  # 🔧 NUEVO: Tracking de escenas omitidas
        
        for idx, scene in enumerate(scenes):
            # Normalizar: buscar visual_search_query primero, luego visual_query como fallback
            visual_query = scene.get("visual_search_query") or scene.get("visual_query", "")
            if not visual_query:
                logger.warning(f"Escena {idx + 1} no tiene visual_query ni visual_search_query")
                # 🔧 CORREGIDO: Crear placeholder en lugar de agregar None
                placeholder = self._create_placeholder_clip(output_path, idx, 5.0)
                if placeholder:
                    video_files.append(placeholder)
                    logger.warning(f"⚠️ Usando placeholder negro para escena {idx + 1} (sin query)")
                else:
                    skipped_scenes.append(idx + 1)
                    logger.error(f"❌ Escena {idx + 1} omitida completamente")
                continue
            
            # Logging mejorado para mostrar la query específica
            scene_text = scene.get("narration") or scene.get("text", "")[:50]
            logger.info(f"🎬 Escena {idx + 1}: '{scene_text}...'")
            logger.info(f"   🔍 Query visual: {visual_query}")
            
            # Decidir si usar Runway o Pexels
            should_use_runway = False
            if self.use_runway and self.runway_generator:
                if self.runway_mode == "Todas las Escenas":
                    should_use_runway = True
                elif self.runway_mode == "Solo Gancho (Escena 1)" and idx == 0:
                    should_use_runway = True
                    logger.info("💎 Usando Runway para el gancho (Escena 1)")
            
            # Variable para trackear si se obtuvo recurso
            resource_obtained = False
            
            if should_use_runway:
                # Generar video con Runway
                logger.info(f"🎨 Generando video con Runway para escena {idx + 1}: {visual_query}")
                video_file = output_path / f"scene_{idx:02d}_video.mp4"
                
                runway_video = self.runway_generator.generate_clip(
                    prompt=visual_query,
                    duration=5,  # Máximo para gen3a_turbo
                    aspect_ratio="9:16",
                    motion_intensity=self.motion_intensity,
                    output_dir=str(output_path)
                )
                
                if runway_video and Path(runway_video).exists():
                    # Renombrar al formato esperado
                    if Path(runway_video).name != video_file.name:
                        shutil.move(runway_video, str(video_file))
                    video_files.append(str(video_file))
                    logger.success(f"✅ Video Runway generado: Escena {idx + 1}")
                    resource_obtained = True
                else:
                    logger.warning(f"⚠️ Runway falló para escena {idx + 1}, usando Pexels como fallback")
                    # Fallback a Pexels
                    video_data = self._search_video(visual_query)
                    if video_data and self._download_video(video_data, str(video_file)):
                        video_files.append(str(video_file))
                        resource_obtained = True
            else:
                # Usar StockEngine (método unificado: Pexels + Pixabay + imágenes)
                video_file = output_path / f"scene_{idx:02d}_video.mp4"
                
                if self.stock_engine:
                    # Usar StockEngine para búsqueda unificada
                    # Crear ruta temporal para el recurso (StockEngine determinará la extensión)
                    temp_resource = output_path / f"scene_{idx:02d}_resource"
                    resource_path, resource_type = self.stock_engine.get_best_visual(
                        query=visual_query,
                        orientation="portrait",
                        output_path=temp_resource,
                        prefer_video=True
                    )
                    
                    if resource_path:
                        resource_path_obj = Path(resource_path)
                        if resource_type == "video":
                            # Renombrar a .mp4 si es necesario
                            if resource_path_obj.suffix != ".mp4":
                                final_video = video_file
                                shutil.move(resource_path, final_video)
                                video_files.append(str(final_video))
                            else:
                                video_files.append(str(resource_path))
                            logger.success(f"✅ Video descargado para escena {idx + 1}")
                            resource_obtained = True
                        elif resource_type == "image":
                            # Mantener la extensión original de la imagen (.jpg, .png, etc.)
                            # video_editor.py detectará automáticamente si es imagen
                            video_files.append(str(resource_path))
                            resource_obtained = True
                            
                            # Detectar si es imagen de DALL-E (contiene "dalle" en el nombre)
                            if "dalle" in str(resource_path).lower():
                                logger.info(f"🎨 Imagen DALL-E 3 generada para escena {idx + 1} (se animará con Ken Burns)")
                            else:
                                logger.info(f"📸 Imagen de stock descargada para escena {idx + 1} (se animará con Ken Burns)")
                        else:
                            logger.error(f"❌ No se pudo obtener recurso visual para escena {idx + 1}")
                else:
                    # Fallback: Usar método tradicional de Pexels
                    video_data = self._search_video(visual_query)
                    if video_data and self._download_video(video_data, str(video_file)):
                        video_files.append(str(video_file))
                        resource_obtained = True
            
            # 🔧 CORREGIDO: Si no se obtuvo recurso, crear placeholder en lugar de None
            if not resource_obtained:
                logger.warning(f"⚠️ No se encontró recurso para escena {idx + 1}, creando placeholder...")
                placeholder = self._create_placeholder_clip(output_path, idx, 5.0)
                if placeholder:
                    video_files.append(placeholder)
                    logger.warning(f"⚠️ Usando placeholder negro para escena {idx + 1}")
                else:
                    skipped_scenes.append(idx + 1)
                    logger.error(f"❌ Escena {idx + 1} omitida completamente (falló placeholder)")
        
        # Estadísticas finales
        success_count = len(video_files)
        placeholder_count = sum(1 for v in video_files if v and "placeholder" in v)
        real_count = success_count - placeholder_count
        
        logger.success(f"Videos procesados: {success_count}/{len(scenes)}")
        logger.info(f"   📹 Recursos reales: {real_count}")
        logger.info(f"   ⬛ Placeholders: {placeholder_count}")
        
        if skipped_scenes:
            logger.warning(f"   ⚠️ Escenas omitidas: {skipped_scenes}")
        
        # 🔧 VALIDACIÓN FINAL: Asegurar que no hay None en la lista
        video_files = [v for v in video_files if v is not None]
        
        return video_files