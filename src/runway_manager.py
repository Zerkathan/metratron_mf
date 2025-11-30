"""
RunwayManager: Genera videos originales usando RunwayML Gen-3 API.
Permite crear clips personalizados en lugar de usar stock de Pexels.
"""

import os
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger

try:
    from runwayml import RunwayML
    RUNWAY_SDK_AVAILABLE = True
except ImportError:
    RUNWAY_SDK_AVAILABLE = False
    logger.warning("⚠️ runwayml SDK no está instalado. Instala con: pip install runwayml")

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    logger.warning("⚠️ deep_translator no está instalado. Instala con: pip install deep-translator")


class RunwayGenerator:
    """Generador de videos usando RunwayML Gen-3 API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el generador de Runway.
        
        Args:
            api_key: Clave API de Runway (opcional, puede estar en .env)
        """
        self.api_key = api_key or os.getenv("RUNWAY_API_KEY")
        if not self.api_key:
            raise ValueError("RUNWAY_API_KEY no encontrada. Configúrala en .env o pasa api_key.")
        
        if not RUNWAY_SDK_AVAILABLE:
            raise ImportError("runwayml SDK no está instalado. Ejecuta: pip install runwayml")
        
        try:
            self.client = RunwayML(api_key=self.api_key)
            logger.success("✅ RunwayGenerator inicializado")
        except Exception as e:
            logger.error(f"Error inicializando RunwayML: {e}")
            raise
    
    def _translate_to_english(self, text: str) -> str:
        """
        Traduce un texto al inglés para Runway.
        
        Args:
            text: Texto a traducir
        
        Returns:
            Texto traducido al inglés
        """
        if not TRANSLATOR_AVAILABLE:
            logger.warning("⚠️ deep_translator no disponible, usando texto original")
            return text
        
        try:
            translator = GoogleTranslator(source='es', target='en')
            translated = translator.translate(text)
            logger.debug(f"Traducción: '{text}' -> '{translated}'")
            return translated
        except Exception as e:
            logger.warning(f"Error traduciendo texto, usando original: {e}")
            return text
    
    def generate_clip(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "9:16",
        motion_intensity: int = 5,
        output_dir: str = "assets/temp"
    ) -> Optional[str]:
        """
        Genera un clip de video usando Runway Gen-3.
        
        Args:
            prompt: Descripción del video a generar (en español, se traduce automáticamente)
            duration: Duración del video en segundos (máx 5 para gen3a_turbo)
            aspect_ratio: Aspecto del video ("9:16" para vertical, "16:9" para horizontal)
            motion_intensity: Intensidad de movimiento (1-10, afecta el prompt)
            output_dir: Directorio donde guardar el video
        
        Returns:
            Ruta del archivo de video generado o None si falla
        """
        logger.info(f"🎨 Runway cocinando video: {prompt}")
        
        try:
            # Traducir prompt a inglés
            english_prompt = self._translate_to_english(prompt)
            
            # Ajustar prompt según intensidad de movimiento
            if motion_intensity > 7:
                english_prompt += ", dynamic camera movement, cinematic motion"
            elif motion_intensity > 4:
                english_prompt += ", subtle camera movement"
            else:
                english_prompt += ", static composition"
            
            logger.info(f"📝 Prompt en inglés: {english_prompt}")
            
            # Crear tarea de generación
            # Nota: El SDK puede variar, ajusta según la versión actual
            try:
                # Intentar con gen3a_turbo (más rápido y económico)
                task = self.client.image_to_video.create(
                    model='gen3a_turbo',
                    prompt_text=english_prompt,
                    duration=duration,
                    ratio=aspect_ratio
                )
            except Exception as e:
                logger.warning(f"Error con gen3a_turbo, intentando gen3a: {e}")
                # Fallback a gen3a estándar
                task = self.client.image_to_video.create(
                    model='gen3a',
                    prompt_text=english_prompt,
                    duration=duration,
                    ratio=aspect_ratio
                )
            
            task_id = task.id if hasattr(task, 'id') else str(task)
            logger.info(f"📋 Task ID: {task_id} - Esperando render...")
            
            # Polling: esperar hasta que la tarea termine
            video_url = self._wait_for_completion(task_id, max_wait_time=300)  # 5 minutos máximo
            
            if not video_url:
                logger.error("❌ La generación de video falló o excedió el tiempo de espera")
                return None
            
            # Descargar el video
            output_path = self._download_video(video_url, prompt, output_dir)
            
            if output_path:
                logger.success(f"✅ Video generado exitosamente: {output_path}")
                return output_path
            else:
                logger.error("❌ Error descargando el video generado")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error generando video con Runway: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _wait_for_completion(self, task_id: str, max_wait_time: int = 300, poll_interval: int = 5) -> Optional[str]:
        """
        Espera a que una tarea de Runway termine usando polling.
        
        Args:
            task_id: ID de la tarea
            max_wait_time: Tiempo máximo de espera en segundos
            poll_interval: Intervalo entre consultas en segundos
        
        Returns:
            URL del video generado o None si falla
        """
        start_time = time.time()
        logger.info(f"⏳ Esperando generación (máx {max_wait_time}s)...")
        
        while (time.time() - start_time) < max_wait_time:
            try:
                # Consultar estado de la tarea
                # Nota: El método exacto puede variar según la versión del SDK
                status_response = self.client.tasks.get(task_id)
                
                status = getattr(status_response, 'status', None) or status_response.get('status', 'UNKNOWN')
                
                logger.debug(f"Estado de la tarea: {status}")
                
                if status == 'SUCCEEDED':
                    # Obtener URL del video
                    video_url = getattr(status_response, 'output', None) or status_response.get('output', None)
                    if isinstance(video_url, dict):
                        video_url = video_url.get('url') or video_url.get('video_url')
                    
                    if video_url:
                        logger.success("✅ Video generado exitosamente")
                        return video_url
                    else:
                        logger.error("❌ Video generado pero no se encontró URL")
                        return None
                
                elif status == 'FAILED':
                    error_msg = getattr(status_response, 'error', None) or status_response.get('error', 'Error desconocido')
                    logger.error(f"❌ La generación falló: {error_msg}")
                    return None
                
                elif status in ['PENDING', 'RUNNING', 'PROCESSING']:
                    elapsed = int(time.time() - start_time)
                    logger.info(f"⏳ Generando... ({elapsed}s/{max_wait_time}s)")
                    time.sleep(poll_interval)
                    continue
                
                else:
                    logger.warning(f"⚠️ Estado desconocido: {status}")
                    time.sleep(poll_interval)
                    continue
                    
            except Exception as e:
                logger.warning(f"Error consultando estado: {e}")
                time.sleep(poll_interval)
                continue
        
        logger.error(f"❌ Tiempo de espera excedido ({max_wait_time}s)")
        return None
    
    def _download_video(self, video_url: str, prompt: str, output_dir: str) -> Optional[str]:
        """
        Descarga un video desde una URL.
        
        Args:
            video_url: URL del video
            prompt: Prompt usado (para nombrar el archivo)
            output_dir: Directorio de salida
        
        Returns:
            Ruta del archivo descargado o None si falla
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Crear nombre de archivo seguro
            safe_name = "".join(c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            filename = f"runway_{safe_name}_{int(time.time())}.mp4"
            file_path = output_path / filename
            
            logger.info(f"📥 Descargando video: {filename}")
            
            # Descargar el video
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.success(f"✅ Video descargado: {filename}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error descargando video: {e}")
            return None


def create_runway_generator(api_key: Optional[str] = None) -> Optional[RunwayGenerator]:
    """
    Factory function para crear un RunwayGenerator de forma segura.
    
    Args:
        api_key: Clave API de Runway (opcional)
    
    Returns:
        RunwayGenerator o None si no está disponible
    """
    try:
        return RunwayGenerator(api_key=api_key)
    except (ValueError, ImportError) as e:
        logger.warning(f"RunwayGenerator no disponible: {e}")
        return None










