"""
StockEngine: Gestor Unificado de Recursos Visuales
Combina múltiples fuentes (Pexels, Pixabay, DALL-E 3) y soporta imágenes estáticas animadas.
"""

import os
import random
import requests
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from loguru import logger
import shutil
import time

# Importar OpenAI client
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI SDK no está instalado. Instala con: pip install openai")


class StockEngine:
    """Motor unificado para búsqueda y descarga de recursos visuales."""
    
    def __init__(self):
        """
        Inicializa el gestor de recursos.
        Carga API Keys de .env (PEXELS_API_KEY, PIXABAY_API_KEY).
        """
        self.pexels_key = os.getenv("PEXELS_API_KEY")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        if not self.pexels_key:
            logger.warning("⚠️ PEXELS_API_KEY no encontrada en .env")
        if not self.pixabay_key:
            logger.warning("⚠️ PIXABAY_API_KEY no encontrada en .env")
        if not self.openai_key:
            logger.warning("⚠️ OPENAI_API_KEY no encontrada en .env")
        
        self.pexels_base_url = "https://api.pexels.com"
        self.pixabay_base_url = "https://pixabay.com/api"
        
        # Inicializar cliente OpenAI si está disponible
        self.openai_client = None
        if OPENAI_AVAILABLE and self.openai_key:
            try:
                self.openai_client = OpenAI(api_key=self.openai_key)
                logger.success("✅ Cliente OpenAI (DALL-E 3) inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Error inicializando OpenAI: {e}")
                self.openai_client = None
        
        logger.info(f"StockEngine inicializado (Pexels: {'✅' if self.pexels_key else '❌'}, Pixabay: {'✅' if self.pixabay_key else '❌'}, DALL-E 3: {'✅' if self.openai_client else '❌'})")
    
    def search_pexels(self, query: str, orientation: str = "portrait") -> Optional[str]:
        """
        Busca y descarga un recurso visual de Pexels (video o imagen).
        Prioriza videos sobre imágenes.
        
        Args:
            query: Consulta de búsqueda
            orientation: 'portrait' o 'landscape'
        
        Returns:
            Ruta del archivo descargado o None si falla
        """
        # Usar directorio de assets/temp del proyecto
        output_dir = Path("assets/temp")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Intentar videos primero
        videos = self.search_pexels_video(query, per_page=5)
        if videos:
            video_data = random.choice(videos)
            # Crear archivo con timestamp único
            temp_file = output_dir / f"pexels_video_{int(time.time())}_{random.randint(1000, 9999)}.mp4"
            if self._download_pexels_video(video_data, temp_file):
                return str(temp_file)
        
        # Fallback a imágenes
        images = self.search_pexels_image(query, per_page=5)
        if images:
            image_data = random.choice(images)
            # Crear archivo con timestamp único
            temp_file = output_dir / f"pexels_image_{int(time.time())}_{random.randint(1000, 9999)}.jpg"
            if self._download_pexels_image(image_data, temp_file):
                return str(temp_file)
        
        return None
    
    def search_pixabay(self, query: str, orientation: str = "portrait") -> Optional[str]:
        """
        Busca y descarga un recurso visual de Pixabay (video o imagen).
        Prioriza videos sobre imágenes.
        
        Args:
            query: Consulta de búsqueda
            orientation: 'portrait' o 'landscape'
        
        Returns:
            Ruta del archivo descargado o None si falla
        """
        # Usar directorio de assets/temp del proyecto
        output_dir = Path("assets/temp")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Intentar videos primero
        videos = self.search_pixabay_video(query, per_page=5)
        if videos:
            video_data = random.choice(videos)
            # Crear archivo con timestamp único
            temp_file = output_dir / f"pixabay_video_{int(time.time())}_{random.randint(1000, 9999)}.mp4"
            if self._download_pixabay_video(video_data, temp_file):
                return str(temp_file)
        
        # Fallback a imágenes
        images = self.search_pixabay_image(query, per_page=5)
        if images:
            image_data = random.choice(images)
            # Crear archivo con timestamp único
            temp_file = output_dir / f"pixabay_image_{int(time.time())}_{random.randint(1000, 9999)}.jpg"
            if self._download_pixabay_image(image_data, temp_file):
                return str(temp_file)
        
        return None
    
    def get_visual(self, query: str, orientation: str = "portrait") -> Optional[str]:
        """
        Método maestro: Obtiene un recurso visual con balanceo de carga entre fuentes.
        
        Args:
            query: Consulta de búsqueda
            orientation: 'portrait' o 'landscape'
        
        Returns:
            Ruta del archivo descargado o None si no se encuentra nada
        """
        # 1. Decidir fuente inicial (Balanceo de carga)
        sources = [self.search_pexels, self.search_pixabay]
        random.shuffle(sources)
        
        video_url = None
        
        # 2. Intentar fuentes
        for source_func in sources:
            try:
                logger.info(f"🔍 Buscando en {source_func.__name__}...")
                video_url = source_func(query, orientation)
                if video_url:
                    logger.success(f"✅ Recurso encontrado: {video_url}")
                    return video_url  # Éxito
            except Exception as e:
                logger.warning(f"⚠️ Error en fuente {source_func.__name__}: {e}")
                continue
                
        # 3. Si nada funciona, retorna None (Main.py se encargará de usar DALL-E)
        logger.warning("❌ No se encontró stock en ninguna fuente.")
        return None
    
    def search_pexels_video(self, query: str, per_page: int = 10) -> List[Dict]:
        """
        Busca videos en Pexels.
        
        Args:
            query: Consulta de búsqueda
            per_page: Número de resultados por página
        
        Returns:
            Lista de diccionarios con datos de videos
        """
        if not self.pexels_key:
            return []
        
        try:
            response = requests.get(
                f"{self.pexels_base_url}/videos/search",
                headers={"Authorization": self.pexels_key},
                params={"query": query, "per_page": per_page, "orientation": "portrait"}
            )
            response.raise_for_status()
            
            data = response.json()
            videos = data.get("videos", [])
            
            if videos:
                logger.debug(f"✅ Pexels: {len(videos)} videos encontrados para '{query}'")
                return videos
            else:
                logger.debug(f"⚠️ Pexels: No se encontraron videos para '{query}'")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error buscando videos en Pexels: {e}")
            return []
    
    def search_pexels_image(self, query: str, per_page: int = 10) -> List[Dict]:
        """
        Busca imágenes en Pexels.
        
        Args:
            query: Consulta de búsqueda
            per_page: Número de resultados por página
        
        Returns:
            Lista de diccionarios con datos de imágenes
        """
        if not self.pexels_key:
            return []
        
        try:
            response = requests.get(
                f"{self.pexels_base_url}/v1/search",
                headers={"Authorization": self.pexels_key},
                params={"query": query, "per_page": per_page, "orientation": "portrait"}
            )
            response.raise_for_status()
            
            data = response.json()
            photos = data.get("photos", [])
            
            if photos:
                logger.debug(f"✅ Pexels: {len(photos)} imágenes encontradas para '{query}'")
                return photos
            else:
                logger.debug(f"⚠️ Pexels: No se encontraron imágenes para '{query}'")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error buscando imágenes en Pexels: {e}")
            return []
    
    def _simplify_pixabay_query(self, query: str, max_words: int = 5, max_chars: int = 100) -> str:
        """
        Simplifica una query para Pixabay, limitando palabras y caracteres.
        Pixabay tiene límites en la longitud de la URL y puede rechazar queries muy largas (Error 400).
        
        Args:
            query: Query original (puede ser muy larga con múltiples términos separados por comas)
            max_words: Número máximo de palabras a usar (default: 5)
            max_chars: Número máximo de caracteres (default: 100)
        
        Returns:
            Query simplificada y limitada
        """
        if not query or not query.strip():
            return ""
        
        # Decodificar URL si viene codificada (ej: %2C, %20, +)
        try:
            from urllib.parse import unquote_plus
            query_clean = unquote_plus(query)
        except Exception:
            query_clean = query
        
        # Limpiar y dividir en palabras
        query_clean = query_clean.strip()
        
        # Remover comas, signos de más y otros separadores que alargan la query
        query_clean = query_clean.replace(",", " ").replace("+", " ").replace("  ", " ")
        query_clean = " ".join(query_clean.split())  # Normalizar espacios múltiples
        
        # Dividir en palabras y tomar las más importantes (primeras)
        words = query_clean.split()
        
        # Limitar por número de palabras (tomar las primeras N palabras)
        if len(words) > max_words:
            words = words[:max_words]
            query_limited = " ".join(words)
            logger.debug(f"📝 Query Pixabay limitada a {max_words} palabras: '{query_limited}' (original tenía {len(query_clean.split())} palabras)")
        else:
            query_limited = " ".join(words)
        
        # Limitar por caracteres (por seguridad adicional)
        if len(query_limited) > max_chars:
            # Cortar en el último espacio completo para no romper palabras
            query_limited = query_limited[:max_chars].rsplit(" ", 1)[0]
            logger.debug(f"📝 Query Pixabay limitada a {max_chars} caracteres: '{query_limited}'")
        
        return query_limited.strip()
    
    def search_pixabay_video(self, query: str, per_page: int = 10) -> List[Dict]:
        """
        Busca videos en Pixabay.
        
        Args:
            query: Consulta de búsqueda (se simplificará si es muy larga)
            per_page: Número de resultados por página
        
        Returns:
            Lista de diccionarios con datos de videos
        """
        if not self.pixabay_key:
            return []
        
        # Simplificar query para evitar URLs demasiado largas
        query_simplified = self._simplify_pixabay_query(query, max_words=5, max_chars=100)
        
        if not query_simplified:
            logger.warning("⚠️ Query vacía después de simplificación, usando query original básica")
            query_simplified = query.split()[0] if query.split() else "video"
        
        try:
            response = requests.get(
                self.pixabay_base_url,
                params={
                    "key": self.pixabay_key,
                    "q": query_simplified,
                    "video_type": "all",
                    "orientation": "vertical",
                    "per_page": per_page,
                    "safesearch": "true"
                }
            )
            response.raise_for_status()
            
            data = response.json()
            videos = data.get("hits", [])
            
            if videos:
                logger.debug(f"✅ Pixabay: {len(videos)} videos encontrados para '{query_simplified}'")
                return videos
            else:
                logger.debug(f"⚠️ Pixabay: No se encontraron videos para '{query_simplified}'")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error buscando videos en Pixabay: {e}")
            return []
    
    def search_pixabay_image(self, query: str, per_page: int = 10) -> List[Dict]:
        """
        Busca imágenes en Pixabay.
        
        Args:
            query: Consulta de búsqueda (se simplificará si es muy larga)
            per_page: Número de resultados por página
        
        Returns:
            Lista de diccionarios con datos de imágenes
        """
        if not self.pixabay_key:
            return []
        
        # Simplificar query para evitar URLs demasiado largas
        query_simplified = self._simplify_pixabay_query(query, max_words=5, max_chars=100)
        
        if not query_simplified:
            logger.warning("⚠️ Query vacía después de simplificación, usando query original básica")
            query_simplified = query.split()[0] if query.split() else "image"
        
        try:
            response = requests.get(
                self.pixabay_base_url,
                params={
                    "key": self.pixabay_key,
                    "q": query_simplified,
                    "image_type": "photo",
                    "orientation": "vertical",
                    "per_page": per_page,
                    "safesearch": "true",
                    "category": "all"
                }
            )
            response.raise_for_status()
            
            data = response.json()
            images = data.get("hits", [])
            
            if images:
                logger.debug(f"✅ Pixabay: {len(images)} imágenes encontradas para '{query_simplified}'")
                return images
            else:
                logger.debug(f"⚠️ Pixabay: No se encontraron imágenes para '{query_simplified}'")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error buscando imágenes en Pixabay: {e}")
            return []
    
    def _download_pexels_video(self, video_data: Dict, output_path: Path) -> bool:
        """Descarga un video de Pexels."""
        try:
            # Obtener la mejor calidad disponible
            video_files = video_data.get("video_files", [])
            if not video_files:
                logger.error("No hay archivos de video disponibles")
                return False
            
            # Buscar la mejor calidad (preferir 1080p o la más alta disponible)
            best_video = None
            best_height = 0
            
            for vf in video_files:
                height = vf.get("height", 0)
                if height > best_height:
                    best_height = height
                    best_video = vf
            
            if not best_video:
                best_video = video_files[0]  # Fallback al primero
            
            video_url = best_video.get("link")
            if not video_url:
                logger.error("No se encontró URL de video")
                return False
            
            logger.info(f"📥 Descargando video de Pexels: {video_url}")
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            
            logger.success(f"✅ Video descargado: {output_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error descargando video de Pexels: {e}")
            return False
    
    def _download_pixabay_video(self, video_data: Dict, output_path: Path) -> bool:
        """Descarga un video de Pixabay."""
        try:
            # Pixabay devuelve videos en diferentes formatos
            videos = video_data.get("videos", {})
            if not videos:
                logger.error("No hay videos disponibles en Pixabay")
                return False
            
            # Preferir medium o large
            video_url = videos.get("medium", {}).get("url") or videos.get("large", {}).get("url") or videos.get("small", {}).get("url")
            
            if not video_url:
                logger.error("No se encontró URL de video en Pixabay")
                return False
            
            logger.info(f"📥 Descargando video de Pixabay: {video_url}")
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            
            logger.success(f"✅ Video descargado: {output_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error descargando video de Pixabay: {e}")
            return False
    
    def _download_pexels_image(self, image_data: Dict, output_path: Path) -> bool:
        """Descarga una imagen de Pexels."""
        try:
            # Obtener la mejor calidad disponible
            src = image_data.get("src", {})
            if not src:
                logger.error("No hay datos de imagen disponibles")
                return False
            
            # Preferir large2x o large
            image_url = src.get("large2x") or src.get("large") or src.get("original")
            
            if not image_url:
                logger.error("No se encontró URL de imagen")
                return False
            
            # Determinar extensión desde la URL
            url_lower = image_url.lower()
            if '.jpg' in url_lower or '.jpeg' in url_lower:
                ext = '.jpg'
            elif '.png' in url_lower:
                ext = '.png'
            elif '.webp' in url_lower:
                ext = '.webp'
            else:
                ext = '.jpg'  # Default
            
            # Asegurar que el output_path tenga la extensión correcta
            if output_path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.webp']:
                output_path = output_path.with_suffix(ext)
            
            logger.info(f"📥 Descargando imagen de Pexels: {image_url}")
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            
            logger.success(f"✅ Imagen descargada: {output_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error descargando imagen de Pexels: {e}")
            return False
    
    def _download_pixabay_image(self, image_data: Dict, output_path: Path) -> bool:
        """Descarga una imagen de Pixabay."""
        try:
            # Pixabay devuelve diferentes tamaños
            image_url = image_data.get("largeImageURL") or image_data.get("webformatURL")
            
            if not image_url:
                logger.error("No se encontró URL de imagen en Pixabay")
                return False
            
            # Determinar extensión desde la URL
            url_lower = image_url.lower()
            if '.jpg' in url_lower or '.jpeg' in url_lower:
                ext = '.jpg'
            elif '.png' in url_lower:
                ext = '.png'
            elif '.webp' in url_lower:
                ext = '.webp'
            else:
                ext = '.jpg'  # Default
            
            # Asegurar que el output_path tenga la extensión correcta
            if output_path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.webp']:
                output_path = output_path.with_suffix(ext)
            
            logger.info(f"📥 Descargando imagen de Pixabay: {image_url}")
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            
            logger.success(f"✅ Imagen descargada: {output_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error descargando imagen de Pixabay: {e}")
            return False
    
    def get_best_visual(
        self,
        query: str,
        orientation: str = "portrait",
        output_path: Optional[Path] = None,
        prefer_video: bool = True
    ) -> Tuple[Optional[str], str]:
        """
        Método maestro: Obtiene el mejor recurso visual disponible.
        
        Lógica de balanceo:
        - 50% Pexels, 50% Pixabay (aleatorio)
        - Si no encuentra video, busca imágenes como fallback
        - Retorna la ruta del archivo y el tipo ('video' o 'image')
        
        Args:
            query: Consulta de búsqueda
            orientation: 'portrait' o 'landscape'
            output_path: Ruta donde guardar el archivo (opcional)
            prefer_video: Si True, prefiere videos sobre imágenes
        
        Returns:
            Tupla (ruta_del_archivo, tipo) donde tipo es 'video' o 'image'
        """
        logger.info(f"🔍 Buscando recurso visual: '{query}' (orientación: {orientation})")
        
        # Decidir aleatoriamente qué fuente usar primero (50/50)
        use_pexels_first = random.choice([True, False])
        
        # Intentar obtener video primero si prefer_video es True
        if prefer_video:
            # Buscar videos
            if use_pexels_first and self.pexels_key:
                pexels_videos = self.search_pexels_video(query, per_page=5)
                if pexels_videos:
                    video_data = random.choice(pexels_videos)
                    if output_path:
                        if self._download_pexels_video(video_data, output_path):
                            return (str(output_path), "video")
            
            if self.pixabay_key:
                pixabay_videos = self.search_pixabay_video(query, per_page=5)
                if pixabay_videos:
                    video_data = random.choice(pixabay_videos)
                    if output_path:
                        if self._download_pixabay_video(video_data, output_path):
                            return (str(output_path), "video")
            
            # Si no se encontraron videos, intentar con la otra fuente
            if not use_pexels_first and self.pexels_key:
                pexels_videos = self.search_pexels_video(query, per_page=5)
                if pexels_videos:
                    video_data = random.choice(pexels_videos)
                    if output_path:
                        if self._download_pexels_video(video_data, output_path):
                            return (str(output_path), "video")
        
        # Fallback: Buscar imágenes si no se encontraron videos o si prefer_video es False
        logger.info(f"📸 No se encontraron videos, buscando imágenes como fallback...")
        
        if use_pexels_first and self.pexels_key:
            pexels_images = self.search_pexels_image(query, per_page=5)
            if pexels_images:
                image_data = random.choice(pexels_images)
                if output_path:
                    if self._download_pexels_image(image_data, output_path):
                        return (str(output_path), "image")
        
        if self.pixabay_key:
            pixabay_images = self.search_pixabay_image(query, per_page=5)
            if pixabay_images:
                image_data = random.choice(pixabay_images)
                if output_path:
                    if self._download_pixabay_image(image_data, output_path):
                        return (str(output_path), "image")
        
        # Último intento con la otra fuente
        if not use_pexels_first and self.pexels_key:
            pexels_images = self.search_pexels_image(query, per_page=5)
            if pexels_images:
                image_data = random.choice(pexels_images)
                if output_path:
                    if self._download_pexels_image(image_data, output_path):
                        return (str(output_path), "image")
        
        # FALLBACK FINAL: Generar con DALL-E 3 si está disponible
        if self.openai_client:
            logger.warning(f"⚠️ No se encontró stock. Generando imagen con DALL-E 3 como fallback...")
            
            # Generar imagen con DALL-E
            dalle_image_path = self.generate_dalle_image(
                prompt=query,
                output_dir=str(output_path.parent) if output_path else "assets/temp"
            )
            
            if dalle_image_path:
                # Si se especificó un output_path, renombrar/mover al formato esperado
                if output_path:
                    dalle_path_obj = Path(dalle_image_path)
                    final_path = output_path.with_suffix(dalle_path_obj.suffix)
                    if dalle_path_obj != final_path:
                        shutil.move(dalle_image_path, str(final_path))
                        return (str(final_path), "image")
                return (dalle_image_path, "image")
        
        logger.warning(f"⚠️ No se encontraron recursos visuales para '{query}' y DALL-E 3 no está disponible")
        return (None, "none")
    
    def _translate_to_english(self, text: str) -> str:
        """
        Traduce el texto al inglés si es necesario (para DALL-E).
        Si ya está en inglés, lo retorna tal cual.
        """
        # Detección simple: si contiene caracteres no ASCII, asumimos que no es inglés
        try:
            text.encode('ascii')
            return text  # Ya está en inglés
        except UnicodeEncodeError:
            # Probablemente no es inglés, intentar traducir
            try:
                from deep_translator import GoogleTranslator
                translated = GoogleTranslator(source='auto', target='en').translate(text)
                logger.debug(f"Traducido para DALL-E: '{text}' -> '{translated}'")
                return translated
            except Exception as e:
                logger.warning(f"⚠️ No se pudo traducir, usando texto original: {e}")
                return text
    
    def generate_dalle_image(self, prompt: str, output_dir: str = "assets/temp") -> Optional[str]:
        """
        Genera una imagen usando DALL-E 3 como fallback cuando no hay stock disponible.
        
        Args:
            prompt: Descripción visual de lo que se quiere generar
            output_dir: Directorio donde guardar la imagen generada
        
        Returns:
            Ruta local del archivo de imagen generado, o None si falla
        """
        if not self.openai_client:
            logger.warning("⚠️ OpenAI client no disponible. DALL-E 3 no se puede usar.")
            return None
        
        if not self.openai_key:
            logger.warning("⚠️ OPENAI_API_KEY no encontrada. DALL-E 3 no se puede usar.")
            return None
        
        logger.info(f"🎨 Generando imagen con DALL-E 3: '{prompt[:50]}...'")
        
        try:
            # Traducir prompt al inglés si es necesario
            english_prompt = self._translate_to_english(prompt)
            
            # Mejorar el prompt para DALL-E 3
            enhanced_prompt = f"{english_prompt}, cinematic, high quality, vertical composition, 9:16 aspect ratio, detailed, professional photography"
            
            logger.info(f"📝 Prompt mejorado para DALL-E: '{enhanced_prompt[:100]}...'")
            
            # Generar imagen con DALL-E 3
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size="1024x1792",  # Vertical (9:16)
                quality="standard",
                n=1
            )
            
            # Obtener URL de la imagen generada
            image_url = response.data[0].url
            
            if not image_url:
                logger.error("❌ DALL-E 3 no devolvió URL de imagen")
                return None
            
            # Crear directorio de salida
            output_path_obj = Path(output_dir)
            output_path_obj.mkdir(parents=True, exist_ok=True)
            
            # Nombre de archivo único
            timestamp = int(time.time())
            output_file = output_path_obj / f"dalle_{timestamp}.png"
            
            # Descargar imagen
            logger.info(f"📥 Descargando imagen de DALL-E 3...")
            img_response = requests.get(image_url, stream=True)
            img_response.raise_for_status()
            
            with open(output_file, 'wb') as f:
                shutil.copyfileobj(img_response.raw, f)
            
            logger.success(f"✅ Imagen DALL-E 3 generada y guardada: {output_file.name}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"❌ Error generando imagen con DALL-E 3: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

