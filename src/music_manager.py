"""
MusicManager: Gestor de música de fondo por estilo.
Selecciona música aleatoria de carpetas locales con fallback inteligente.
"""

import random
from pathlib import Path
from typing import Optional, Dict
from loguru import logger


class MusicManager:
    """Gestiona la selección de música de fondo por estilo."""
    
    def __init__(self):
        """
        Inicializa el gestor de música.
        """
        self.music_base = Path("assets/music")
        self.music_base.mkdir(parents=True, exist_ok=True)
        
        # Mapeo de estilos a carpetas (soporta nombres con emojis y variaciones)
        self.style_to_folder = {
            # Variaciones de Horror
            "horror": "horror",
            "Horror": "horror",
            "HORROR": "horror",
            "😱 Horror": "horror",
            "🎃 Horror": "horror",
            
            # Variaciones de Motivación
            "motivación": "motivation",
            "Motivación": "motivation",
            "MOTIVACIÓN": "motivation",
            "motivation": "motivation",
            "Motivation": "motivation",
            "MOTIVATION": "motivation",
            "💪 Motivación": "motivation",
            "🔥 Motivación": "motivation",
            
            # Variaciones de Lujo
            "lujo": "luxury",
            "Lujo": "luxury",
            "LUJO": "luxury",
            "luxury": "luxury",
            "Luxury": "luxury",
            "LUXURY": "luxury",
            "💎 Lujo": "luxury",
            "✨ Lujo": "luxury",
            
            # Variaciones de Tech
            "tech": "tech",
            "Tech": "tech",
            "TECH": "tech",
            "tecnología": "tech",
            "Tecnología": "tech",
            "TECNOLOGÍA": "tech",
            "🤖 Tech": "tech",
            "💻 Tech": "tech",
            
            # Otros estilos comunes
            "curiosidades": "curiosity",
            "Curiosidades": "curiosity",
            "CURIOSIDADES": "curiosity",
            "lofi": "lofi",
            "LoFi": "lofi",
            "LOFI": "lofi",
            "musical": "lofi",
            "Musical": "lofi",
            "MUSICAL": "lofi",
        }
        
        logger.info("MusicManager inicializado")
    
    def _normalize_style(self, style_name: str) -> str:
        """
        Normaliza el nombre del estilo a una carpeta válida.
        
        Args:
            style_name: Nombre del estilo (puede tener emojis, mayúsculas, etc.)
        
        Returns:
            Nombre de carpeta normalizado
        """
        if not style_name:
            return "general"
        
        # Limpiar espacios y convertir a string
        style_clean = str(style_name).strip()
        
        # Buscar en el mapeo
        folder = self.style_to_folder.get(style_clean)
        if folder:
            return folder
        
        # Si no está en el mapeo, intentar búsqueda case-insensitive
        style_lower = style_clean.lower()
        for key, value in self.style_to_folder.items():
            if key.lower() == style_lower:
                return value
        
        # Si contiene palabras clave, intentar mapear
        if any(word in style_lower for word in ["horror", "terror", "miedo", "scary"]):
            return "horror"
        elif any(word in style_lower for word in ["motiv", "inspir", "éxito", "exito"]):
            return "motivation"
        elif any(word in style_lower for word in ["lujo", "luxury", "rico", "premium"]):
            return "luxury"
        elif any(word in style_lower for word in ["tech", "tecnolog", "futuro", "ai", "robot"]):
            return "tech"
        elif any(word in style_lower for word in ["curios", "dato", "interesante"]):
            return "curiosity"
        elif any(word in style_lower for word in ["lofi", "lo-fi", "chill", "relax"]):
            return "lofi"
        
        # Default
        return "general"
    
    def _find_music_files(self, folder_path: Path) -> list:
        """
        Encuentra archivos de música en una carpeta.
        
        Args:
            folder_path: Ruta de la carpeta a escanear
        
        Returns:
            Lista de rutas absolutas de archivos de música
        """
        music_files = []
        
        if not folder_path.exists():
            return music_files
        
        # Buscar archivos .mp3, .wav, .m4a, .flac
        extensions = ["*.mp3", "*.wav", "*.m4a", "*.flac", "*.ogg"]
        for ext in extensions:
            music_files.extend(folder_path.glob(ext))
            music_files.extend(folder_path.glob(ext.upper()))
        
        # Convertir a rutas absolutas y filtrar solo archivos (no directorios)
        music_files = [str(f.resolve()) for f in music_files if f.is_file()]
        
        return music_files
    
    def get_random_music(self, style_name: str = None) -> Optional[str]:
        """
        Obtiene una canción aleatoria según el estilo especificado.
        
        Args:
            style_name: Nombre del estilo (puede tener emojis, variaciones, etc.)
                       Si es None o vacío, usa "general"
        
        Returns:
            Ruta absoluta de un archivo de música aleatorio, o None si no hay música disponible
        """
        # Normalizar el estilo a una carpeta
        folder_name = self._normalize_style(style_name)
        logger.info(f"🎵 Buscando música para estilo: '{style_name}' -> carpeta: '{folder_name}'")
        
        # 1. Intentar en la carpeta del estilo
        style_folder = self.music_base / folder_name
        music_files = self._find_music_files(style_folder)
        
        if music_files:
            selected = random.choice(music_files)
            logger.success(f"✅ Música seleccionada: {Path(selected).name} (estilo: {folder_name})")
            return selected
        
        logger.warning(f"⚠️ No se encontraron archivos de música en '{folder_name}'")
        
        # 2. FALLBACK: Buscar en carpeta "general"
        if folder_name != "general":
            general_folder = self.music_base / "general"
            music_files = self._find_music_files(general_folder)
            
            if music_files:
                selected = random.choice(music_files)
                logger.info(f"✅ Música seleccionada desde 'general': {Path(selected).name}")
                return selected
        
        # 3. FALLBACK FINAL: Retornar None (el video se hará sin música)
        logger.warning("⚠️ No se encontró música en ninguna carpeta. El video se generará sin música de fondo.")
        return None
    
    def get_music_count_by_genre(self) -> Dict[str, int]:
        """
        Retorna el conteo de pistas de música por género/carpeta.
        
        Returns:
            Diccionario con {género: cantidad} donde las claves son nombres de géneros
            con mayúscula inicial (ej: {"Horror": 5, "Tech": 2, "General": 10})
        """
        # Mapeo de nombres de carpetas a nombres de géneros para mostrar
        folder_to_genre_name = {
            "horror": "Horror",
            "motivation": "Motivation",
            "luxury": "Luxury",
            "tech": "Tech",
            "curiosity": "Curiosity",
            "lofi": "Lofi",
            "general": "General"
        }
        
        # Obtener todas las carpetas únicas del mapeo de estilos
        unique_folders = set(self.style_to_folder.values())
        # Agregar "general" que siempre existe como fallback
        unique_folders.add("general")
        
        # También incluir carpetas comunes que pueden existir
        common_folders = ["horror", "motivation", "lofi", "curiosity", "luxury", "tech", "general"]
        
        # Combinar y eliminar duplicados
        all_folders = list(set(unique_folders) | set(common_folders))
        
        counts = {}
        
        # Iterar sobre cada carpeta y contar archivos de audio
        for folder_name in all_folders:
            folder_path = self.music_base / folder_name
            music_files = self._find_music_files(folder_path)
            # Usar el nombre del género capitalizado, o capitalizar el nombre de la carpeta
            genre_name = folder_to_genre_name.get(folder_name, folder_name.capitalize())
            counts[genre_name] = len(music_files)
        
        logger.debug(f"📊 Conteo de música por género: {counts}")
        return counts
