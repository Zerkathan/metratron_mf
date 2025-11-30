"""
MetadataGenerator: Genera títulos, descripciones y hashtags optimizados para SEO.
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from loguru import logger


def _clean_json_payload(raw_text: str) -> str:
    """Elimina fences ``` y espacios extra antes de parsear JSON."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


class MetadataGenerator:
    """Generador de metadatos optimizados para SEO y engagement."""
    
    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no encontrada. Configúrala en .env o pásala al constructor.")
        
        genai.configure(api_key=api_key)
        self.model_name = self._select_model()
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"MetadataGenerator inicializado con modelo: {self.model_name}")
    
    def _select_model(self) -> str:
        """Selecciona el mejor modelo disponible de Gemini."""
        priorities = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-2.5-pro",
        ]
        available = [
            m.name for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        for name in priorities:
            full_name = f"models/{name}"
            if full_name in available:
                logger.debug(f"Modelo Gemini seleccionado: {full_name}")
                return full_name
        if available:
            logger.warning(f"Usando primer modelo disponible: {available[0]}")
            return available[0]
        raise RuntimeError("No se encontraron modelos Gemini disponibles.")
    
    def generate_metadata(
        self,
        script_text: str,
        topic: str,
        style: str = "CURIOSIDADES",
        duration_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Genera metadatos optimizados para SEO y engagement.
        
        Args:
            script_text: Texto completo del guion (todas las escenas concatenadas)
            topic: Tema principal del video
            style: Estilo del video (HORROR, MOTIVACION, etc.)
            duration_seconds: Duración del video en segundos (opcional)
        
        Returns:
            Diccionario con title_viral, title_seo, description, hashtags
        """
        logger.info(f"Generando metadatos para: {topic} (estilo: {style})")
        
        # Construir el prompt del sistema
        system_instruction = """Eres un Experto en YouTube SEO y Copywriting Viral.
Tu objetivo es crear metadatos que maximicen el CTR (Click-Through Rate) y el engagement.

REGLAS PARA TÍTULOS:
- title_viral: Máximo 60 caracteres, clickbait, con 1-2 emojis relevantes, genera curiosidad
- title_seo: Máximo 100 caracteres, incluye palabras clave de búsqueda, sin emojis, descriptivo

REGLAS PARA DESCRIPCIÓN:
- Máximo 3 líneas (150-200 caracteres)
- Primera línea debe ser el gancho más fuerte
- Incluye palabras clave naturales
- Termina con un CTA sutil (ej: "¿Qué opinas?", "Comparte tu experiencia")

REGLAS PARA HASHTAGS:
- Exactamente 10 hashtags relevantes
- Mezcla hashtags populares (#viral, #shorts) con específicos del tema
- Formato: "#hashtag1 #hashtag2 #hashtag3 ..."
- En español o inglés según el tema

FORMATO DE SALIDA (JSON estricto):
{
  "title_viral": "Título clickbait con emojis (máx 60 chars)",
  "title_seo": "Título SEO optimizado (máx 100 chars)",
  "description": "Descripción de 3 líneas con palabras clave",
  "hashtags": "#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5 #hashtag6 #hashtag7 #hashtag8 #hashtag9 #hashtag10"
}"""

        # Construir el prompt del usuario
        duration_info = f"\nDuración del video: {duration_seconds:.0f} segundos" if duration_seconds else ""
        
        user_prompt = f"""Genera metadatos optimizados para este video:

TEMA: {topic}
ESTILO: {style}{duration_info}

CONTENIDO DEL VIDEO (Guion completo):
{script_text}

IMPORTANTE:
- Los títulos deben ser irresistibles y generar curiosidad
- La descripción debe resumir el valor del video en 3 líneas
- Los hashtags deben ser relevantes y populares
- Todo debe estar en ESPAÑOL (excepto hashtags que pueden ser en inglés si son más populares)
- Entrega ÚNICAMENTE el JSON sin explicación adicional, sin markdown, sin código."""

        generation_config = {
            "temperature": 0.9,  # Más creativo para títulos clickbait
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json",
        }
        
        safety = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        try:
            response = self.model.generate_content(
                [system_instruction, user_prompt],
                generation_config=generation_config,
                safety_settings=safety,
            )
        except Exception as exc:
            logger.error(f"Error generando metadatos con Gemini: {exc}")
            raise
        
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            reason = response.prompt_feedback.block_reason
            logger.error(f"Respuesta bloqueada por seguridad: {reason}")
            raise ValueError(f"Gemini bloqueó la solicitud: {reason}")
        
        if not response.text:
            logger.error("Gemini devolvió respuesta vacía para metadatos.")
            raise ValueError("Respuesta vacía del modelo.")
        
        raw_json = _clean_json_payload(response.text)
        
        try:
            metadata: Dict[str, Any] = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.error(f"JSON inválido en metadatos: {exc}")
            logger.error(f"Payload recibido: {raw_json[:500]}")
            raise
        
        # Validar que tenga los campos requeridos
        required_fields = ["title_viral", "title_seo", "description", "hashtags"]
        for field in required_fields:
            if field not in metadata:
                logger.warning(f"Campo '{field}' faltante en metadatos. Usando valor por defecto.")
                if field == "title_viral":
                    metadata[field] = f"{topic} - Video Viral"
                elif field == "title_seo":
                    metadata[field] = f"{topic} - Información Completa"
                elif field == "description":
                    metadata[field] = f"Descubre todo sobre {topic}. No te lo pierdas."
                elif field == "hashtags":
                    metadata[field] = "#viral #shorts #trending"
        
        # Limpiar y validar longitudes
        metadata["title_viral"] = metadata["title_viral"][:60].strip()
        metadata["title_seo"] = metadata["title_seo"][:100].strip()
        metadata["description"] = metadata["description"][:300].strip()
        
        # Asegurar que hashtags tenga el formato correcto
        hashtags_str = metadata.get("hashtags", "")
        if not hashtags_str.startswith("#"):
            # Si no empieza con #, intentar parsear como lista o string
            if isinstance(hashtags_str, list):
                hashtags_str = " ".join([h if h.startswith("#") else f"#{h}" for h in hashtags_str])
            else:
                hashtags_str = " ".join([f"#{h.strip()}" for h in hashtags_str.split() if h.strip()])
        metadata["hashtags"] = hashtags_str
        
        logger.success(f"✅ Metadatos generados: {metadata['title_viral']}")
        
        return metadata
    
    def save_metadata(self, metadata: Dict[str, Any], output_dir: str = "output", base_filename: Optional[str] = None) -> str:
        """
        Guarda los metadatos en un archivo JSON.
        
        Args:
            metadata: Diccionario con los metadatos
            output_dir: Directorio donde guardar el archivo
            base_filename: Nombre base del archivo (sin extensión). Si se proporciona, se usa este nombre.
                          Si no, se genera uno con timestamp.
        
        Returns:
            Ruta del archivo guardado
        """
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        if base_filename:
            # Usar el nombre base proporcionado
            filename = f"{base_filename}.json"
        else:
            # Generar nombre con timestamp (comportamiento original)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metadata_{timestamp}.json"
        
        filepath = output_path / filename
        
        # Si el archivo ya existe, agregar número secuencial
        if filepath.exists():
            stem = filepath.stem
            counter = 1
            while filepath.exists():
                filename = f"{stem}_{counter:03d}.json"
                filepath = output_path / filename
                counter += 1
                if counter > 999:
                    # Como último recurso, agregar timestamp corto
                    timestamp = datetime.now().strftime("%H%M%S")
                    filename = f"{stem}_{timestamp}.json"
                    filepath = output_path / filename
                    break
        
        # Agregar timestamp a los metadatos
        metadata_with_timestamp = {
            **metadata,
            "generated_at": datetime.now().isoformat(),
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(metadata_with_timestamp, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Metadatos guardados en: {filepath}")
        return str(filepath)





