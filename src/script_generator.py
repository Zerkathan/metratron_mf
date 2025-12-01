"""
ViralScriptGenerator: Genera guiones virales estructurados con indicaciones visuales.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from loguru import logger


def _clean_json_payload(raw_text: str) -> str:
    """Elimina fences ``` y espacios extra antes de parsear JSON."""
    cleaned = raw_text.strip()
    
    # Eliminar bloques de código Markdown (```json ... ```)
    if "```json" in cleaned:
        # Buscar el contenido entre ```json y ```
        match = re.search(r'```json\s*(.*?)\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        else:
            # Fallback: eliminar manualmente
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        # Buscar el contenido entre ``` y ```
        match = re.search(r'```\s*(.*?)\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        else:
            # Fallback: eliminar manualmente
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
    
    return cleaned.strip()


def _ensure_descriptive_query(query: str, fallback: str) -> str:
    """
    Garantiza que la visual_query tenga al menos 5 palabras y sea descriptiva.
    Si no cumple, se refuerza con términos visuales del fallback.
    """
    words = query.strip().split()
    if len(words) >= 5 and all(len(w) > 2 for w in words):
        return query
    enriched = f"{query} cinematic detailed rich colors dramatic lighting 4k"
    if len(enriched.split()) < 5:
        enriched = f"{fallback} cinematic macro shot dramatic lighting 4k"
    return enriched


def _append_keywords(query: str, keywords: str) -> str:
    """Agrega palabras clave visuales evitando duplicados."""
    if not keywords:
        return query
    existing = set(query.lower().split())
    additions = [kw for kw in keywords.split() if kw.lower() not in existing]
    if not additions:
        return query
    return f"{query} {' '.join(additions)}".strip()


def _compress_keywords(text: str) -> str:
    """Convierte descripciones largas en una lista compacta de palabras clave."""
    sanitized = text.replace(",", " ").replace("\n", " ")
    words = [w for w in sanitized.split() if len(w) > 2]
    return " ".join(words[:15])


# Instrucción común para humanizar el texto
COMMON_INSTRUCTION = """
IMPORTANTE: Escribe como un humano, no como una IA. Usa lenguaje coloquial, directo y emocional. Estructura lógica: Gancho -> Problema -> Solución/Dato -> Conclusión. Evita frases genéricas como 'En el mundo de hoy...'.
"""

# PROMPT PERSONAS: Personalidades específicas para cada estilo narrativo
STYLE_PROMPTS = {
    "HORROR": """Eres un Narrador de Cuentos Prohibidos. Voz grave.

REGLAS:
- Gancho (0-3s): Empieza in media res o con una advertencia. Ej: 'No mires debajo de tu cama'.
- Tono: Frío, clínico, aterrador.
- Visuales (JSON): Usa términos en inglés: 'eerie, dark, fog, liminal space, shadow figure, vhs glitch'.
- Estructura: Misterio cotidiano -> Giro sobrenatural -> Cierre paranoico.""" + COMMON_INSTRUCTION,

    "MOTIVACION": """Eres un Emperador Estoico Moderno. No tienes paciencia para excusas.

REGLAS:
- Gancho: Ataque al ego o verdad incómoda. Ej: 'Nadie va a venir a salvarte'.
- Tono: Autoritario, masculino, poderoso.
- Visuales (JSON): 'greek statue, marcus aurelius, lion hunting, man in suit, boxing training, dark gym'.
- Estructura: Dolor -> Perspectiva Estoica -> Llamada a la Acción.""" + COMMON_INSTRUCTION,

    "CURIOSIDADES": """Eres un Científico Loco obsesionado con fallos en la realidad.

REGLAS:
- Gancho: Rompe una creencia común. Ej: 'Este color no existe'.
- Tono: Frenético, rápido.
- Visuales (JSON): 'macro eye, galaxy spiral, optical illusion, neural network, time lapse, fluid simulation'.
- Estructura: Dato shockeante -> Explicación rápida -> Pregunta final.""" + COMMON_INSTRUCTION,

    "LUJO": """Eres un Multimillonario Anónimo. Compartes códigos de éxito.

REGLAS:
- Gancho: Asocia dinero con libertad.
- Tono: Sofisticado, minimalista, susurrado.
- Visuales (JSON): 'luxury mansion, rolls royce, gold bars, dubai skyline, private jet, champagne'.
- Estilo: Old Money aesthetic.""" + COMMON_INSTRUCTION,

    "MUSICAL": """Eres un Artista Visual Abstracto. NO escribas una historia.

REGLAS:
- Texto: Solo frases muy cortas y poéticas o palabras sueltas cada 5 segundos.
- Visuales (JSON): PRIORIDAD TOTAL. Busca loops perfectos.
  * Si el tema es ESPECÍFICO (ej: "Piano", "Jazz", "Guitarra"): Usa visuales relacionados con ESE tema.
    Ejemplo: Tema="Piano" → 'piano keys aesthetic, slow motion, classic music mood, elegant piano room'.
    Ejemplo: Tema="Jazz Café" → 'jazz cafe atmosphere, warm lighting, saxophone, vinyl records'.
  * Si el tema es GENÉRICO o VACÍO: Usa visuales abstractos: 'neon tunnel, synthwave sunset, rain on window, cyberpunk street, abstract geometry'.
- Objetivo: Video hipnótico para fondo musical que coincida con el tema proporcionado.""" + COMMON_INSTRUCTION,

    "CRIMEN": """Eres un Investigador de Casos Reales. Voz documental seria.

REGLAS:
- Gancho: Hecho real impactante o pregunta sin respuesta.
- Tono: Serio, objetivo, misterioso.
- Visuales (JSON): 'black and white, grainy, police files, mystery, shadowy figure, detective office, evidence board'.
- Estructura: Caso real -> Detalles escalofriantes -> Teoría final.""" + COMMON_INSTRUCTION,

    "HUMOR": """Eres un Comediante Absurdo. Ritmo rápido y remates inesperados.

REGLAS:
- Gancho: Situación ridícula o observación absurda.
- Tono: Desenfadado, exagerado, divertido.
- Visuales (JSON): 'goofy meme, reaction shot, slapstick, exaggerated face, neon colors, absurd props'.
- Estructura: Setup absurdo -> Desarrollo cómico -> Remate inesperado.""" + COMMON_INSTRUCTION,

    "FUTURISMO": """Eres un Visionario Tecnológico. Hablas del futuro como si fuera presente.

REGLAS:
- Gancho: Predicción impactante o tecnología disruptiva.
- Tono: Visionario, entusiasta, futurista.
- Visuales (JSON): 'cyberpunk, robots, AI, matrix code, neon city, spaceship, hologram, neural interface'.
- Estructura: Futuro cercano -> Implicaciones -> Reflexión final.""" + COMMON_INSTRUCTION,

    "SALUD": """Eres un Coach de Bienestar Holístico y Nutricionista. Tu voz es calmada, inspiradora y saludable.

REGLAS:
- Gancho: Empieza con un dolor común o un secreto de salud. Ej: '¿Te sientes cansado siempre?', 'Tu hígado te está pidiendo ayuda'.
- Tono: Empático, limpio, motivador, científico pero simple.
- Visuales (JSON): Usa términos 'clean aesthetic'. Keywords: 'fresh fruits, yoga sunrise, running shoes, water splash, meditation, spa, healthy salad, bright kitchen, nature walk'.
- Estructura: Problema (Síntoma) -> Solución Natural -> Beneficio inmediato.""" + COMMON_INSTRUCTION,

    "RELIGION": """Eres un Guía Espiritual con voz cálida y profunda. Tu objetivo es dar esperanza y paz en 60 segundos.

REGLAS:
- Gancho: Una pregunta al alma o una bendición directa. Ej: 'Dios tiene un mensaje para ti hoy', 'Si estás triste, escucha esto'.
- Tono: Solemne, suave, con pausas reflexivas.
- Visuales (JSON): Keywords etéreas: 'sun rays through clouds, praying hands, candle light, church stained glass, open bible, cross silhouette, peaceful river, dove flying'. Evita imágenes religiosas muy específicas de una sola doctrina, busca lo espiritual universal.
- Estructura: Versículo/Frase Poderosa -> Reflexión Breve -> Bendición Final (Amén).""" + COMMON_INSTRUCTION,

    "TECH": """Eres un Analista de Tecnología del Futuro. Tu voz es nítida, rápida y geek.

REGLAS:
- Gancho: Una noticia de impacto o una herramienta nueva. Ej: 'La IA acaba de reemplazar a los médicos', 'Este robot cuesta menos que tu iPhone'.
- Tono: Informativo, futurista, entusiasta pero con datos.
- Visuales (JSON): Keywords High-Tech. 'humanoid robot face, microchip macro, server room lights, hologram interface, virtual reality headset, futuristic city drone shot, matrix code rain'.
- Estructura: La Noticia -> La Implicación -> Pregunta Ética.""" + COMMON_INSTRUCTION,

    "CUSTOM": """Eres un Director Creativo Personalizado. Sigue exactamente las indicaciones del usuario.

REGLAS:
- Adapta tu personalidad según las instrucciones personalizadas proporcionadas.
- Mantén coherencia visual y narrativa.""" + COMMON_INSTRUCTION,

    "DEFAULT": """Eres un Director Creativo de Videos Virales. Obsesionado con retención y coherencia visual.

REGLAS:
- Gancho (0-3s): Frase polémica, pregunta imposible o dato shockeante.
- Tono: Cinematográfico, frases cortas y potentes.
- Visuales (JSON): Describe escenas concretas en inglés, mínimo 5 palabras.
- Estructura: Gancho -> Desarrollo -> Cierre inesperado.""" + COMMON_INSTRUCTION
}

# Keywords visuales por estilo (para enriquecer las visual queries)
VISUAL_KEYWORDS = {
    "HORROR": "dark eerie fog shadowy cursed ritual glitch horror 4k liminal space",
    "MOTIVACION": "greek statue marcus aurelius lion hunting man in suit boxing training dark gym",
    "CURIOSIDADES": "macro eye galaxy spiral optical illusion neural network time lapse fluid simulation",
    "LUJO": "luxury mansion rolls royce gold bars dubai skyline private jet champagne",
    "MUSICAL": "neon tunnel synthwave sunset rain on window cyberpunk street abstract geometry loop",
    "CRIMEN": "noir black white police files detective desk evidence grainy shadowy figure",
    "HUMOR": "goofy meme reaction shot slapstick exaggerated face neon absurd props",
    "FUTURISMO": "cyberpunk neon city ai robot matrix code hologram spaceship neural interface",
    "TECH": "humanoid robot face microchip macro server room lights hologram interface virtual reality headset futuristic city drone shot matrix code rain",
    "SALUD": "fresh fruits yoga sunrise running shoes water splash meditation spa healthy salad bright kitchen nature walk clean aesthetic",
    "RELIGION": "sun rays through clouds praying hands candle light church stained glass open bible cross silhouette peaceful river dove flying spiritual",
    "CUSTOM": "",
    "DEFAULT": "cinematic detailed dramatic lighting shallow depth realistic"
}


class ViralScriptGenerator:
    """Generador de guiones virales con estructura Hook / Body / Twist."""

    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no encontrada. Configúrala en .env o pásala al constructor.")

        genai.configure(api_key=api_key)
        self.model_name = self._select_model()
        self.model = genai.GenerativeModel(self.model_name)
        logger.success(f"ViralScriptGenerator inicializado con modelo: {self.model_name}")

    def _select_model(self) -> str:
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
                logger.info(f"Modelo Gemini seleccionado: {full_name}")
                return full_name
        if available:
            logger.warning(f"Usando primer modelo disponible: {available[0]}")
            return available[0]
        raise RuntimeError("No se encontraron modelos Gemini disponibles.")

    def generate_script(
        self,
        topic: str,
        duration_minutes: float = 1.0,
        style_prompt: str = "",
        style_code: str = "CURIOSIDADES",
        custom_visual_mood: Optional[str] = None,
        use_news_mode: bool = False,
        news_data: Optional[str] = None,
        news_context: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Genera un script estructurado con campos `text`, `visual_query` y `duration`.

        Returns:
            Lista de diccionarios con las escenas del guion. Cada escena contiene:
            - text: Texto de la narración
            - visual_query: Query para búsqueda de visuales
            - duration: Duración en segundos
            - scene_number: Número de escena
            - segment: Segmento narrativo (HOOK/BODY/TWIST)
            
            Retorna None si hay un error en el parseo del JSON.
        """
        logger.info(f"Generando guion estructurado para: {topic}")
        normalized_style = (style_code or "DEFAULT").upper()
        
        # Obtener el Prompt Persona según el estilo
        system_instruction = STYLE_PROMPTS.get(normalized_style, STYLE_PROMPTS["DEFAULT"])
        logger.info(f"🎭 Prompt Persona activado: {normalized_style}")
        
        # Obtener keywords visuales para enriquecer las queries
        visual_keywords = VISUAL_KEYWORDS.get(normalized_style, VISUAL_KEYWORDS["DEFAULT"])
        
        # FIX MODO MUSICAL: Si el tema es específico, usar contexto del tema para visuales
        if normalized_style == "MUSICAL" and topic and topic.strip():
            topic_lower = topic.lower().strip()
            # Verificar si el topic es específico (contiene palabras relacionadas con instrumentos/música)
            musical_keywords = ["piano", "guitarra", "guitar", "jazz", "rock", "clásica", "classical", 
                               "violín", "violin", "saxofón", "saxophone", "trumpet", "trompeta",
                               "drum", "batería", "bass", "bajo", "café", "cafe", "vinyl", "vinilo"]
            is_specific_topic = any(keyword in topic_lower for keyword in musical_keywords)
            
            if is_specific_topic:
                logger.info(f"🎵 Tema musical específico detectado: '{topic}'. Usando contexto del tema para visuales.")
                # Agregar instrucción especial al prompt
                system_instruction += f"\n\nCONTEXTO ESPECÍFICO: El tema es '{topic}'. Las visual queries DEBEN reflejar este tema específico. Si menciona un instrumento o género musical, busca visuales relacionados con ese instrumento/género, NO visuales abstractos genéricos."
            else:
                logger.info(f"🎵 Tema musical genérico. Usando visuales abstractos por defecto.")
        
        # Si hay un estilo personalizado adicional, agregarlo
        if style_prompt and normalized_style != "CUSTOM":
            system_instruction += f"\n\nNotas adicionales de estilo: {style_prompt}"
        
        # Si hay custom visual mood, agregarlo
        if custom_visual_mood:
            system_instruction += f"\n\nNotas visuales personalizadas: {custom_visual_mood}"
            visual_keywords = f"{visual_keywords} {_compress_keywords(custom_visual_mood)}".strip()
        
        # ============================================================
        # MODO NOTICIAS: Inyectar noticias reales en el prompt
        # ============================================================
        # Usar news_context si está disponible, sino usar news_data (compatibilidad)
        effective_news_context = news_context or news_data
        
        if effective_news_context and effective_news_context.strip():
            logger.info("📰 Modo Noticias activado: Inyectando noticias reales en el prompt...")
            # Cambiar el prompt persona a modo reportero según especificaciones
            system_instruction = f"""Actúa como un Reportero de Noticias Viral. Usa ESTA información real para crear el guion: {effective_news_context}

NO inventes datos, usa los proporcionados. Hazlo emocionante y urgente.

REGLAS ADICIONALES:
- Gancho: Una noticia de impacto o un dato sorprendente de las noticias reales.
- Tono: Informativo, actual, entusiasta pero con datos verificables.
- Visuales (JSON): Keywords High-Tech y actualidad. 'breaking news studio, journalist reporting, tech conference, smartphone close-up, data visualization, modern office, newsroom'.
- Estructura: La Noticia -> La Implicación -> Pregunta Ética o Reflexión Final.
- IMPORTANTE: Usa SOLO las noticias reales proporcionadas. NO inventes datos."""
            
            logger.success("✅ Noticias inyectadas en el prompt del LLM")
        elif use_news_mode and not effective_news_context:
            logger.warning("⚠️ Modo Noticias activado pero no hay datos de noticias. Continuando sin noticias.")

        # User prompt con instrucciones técnicas y formato JSON
        news_section = ""
        if effective_news_context and effective_news_context.strip():
            news_section = f"\n\nINFORMACIÓN DE NOTICIAS REALES:\n{effective_news_context}\n"
        
        # Construir el prompt base
        if effective_news_context and effective_news_context.strip():
            base_task = "Genera un guion viral estructurado en formato JSON basado en NOTICIAS REALES y RECIENTES."
            important_note = f"\n\nIMPORTANTE: Usa esta información real y reciente para el guion:\n{effective_news_context}\n\nNO inventes datos. Usa SOLO la información proporcionada."
        else:
            base_task = "Genera un guion viral estructurado en formato JSON."
            important_note = ""
        
        user_prompt = f"""
TAREA: {base_task}

Tema principal / Búsqueda: "{topic}"
Duración objetivo: {duration_minutes * 60:.0f} segundos
{important_note}

FORMATO DE SALIDA OBLIGATORIO (JSON array estricto):
[
  {{
    "text": "Texto exacto en español que dirá la voz",
    "visual_query": "Descripción visual hiper específica en inglés (mínimo 5 palabras)",
    "duration": 4
  }}
]

REGLAS TÉCNICAS:
- El campo "text" debe estar en ESPAÑOL (idioma de la narración).
- El campo "visual_query" debe estar en INGLÉS (para búsqueda en Pexels/Runway).
- Visual queries deben ser descriptivas y concretas, nunca abstractas.
- Duración en segundos (típicamente 3-6 segundos por escena).
- El array debe tener suficientes escenas para cubrir la duración objetivo.

IMPORTANTE: 
- Sigue estrictamente las reglas de personalidad definidas en el system prompt.
- Aplica el estilo visual indicado en cada visual_query.
- Entrega ÚNICAMENTE el JSON sin explicación adicional, sin markdown, sin código.
"""

        generation_config = {
            "temperature": 0.85,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,
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
            logger.error(f"No se pudo contactar a Gemini: {exc}")
            raise

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            reason = response.prompt_feedback.block_reason
            logger.error(f"Respuesta bloqueada por seguridad: {reason}")
            raise ValueError(f"Gemini bloqueó la solicitud: {reason}")

        if not response.text:
            logger.error("Gemini devolvió respuesta vacía.")
            raise ValueError("Respuesta vacía del modelo.")

        response_text = response.text.strip()
        
        # Limpieza de Markdown (Bloques de código)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        # Intento de parseo
        try:
            script_data = json.loads(response_text)
            
            # Validación extra: Debe ser una lista
            if isinstance(script_data, list):
                scenes_array = script_data
            else:
                logger.warning("⚠️ La IA devolvió un JSON válido pero no es una lista. Envolviendo en lista.")
                scenes_array = [script_data]  # Lo envolvemos en lista si es un solo objeto
                
        except json.JSONDecodeError as exc:
            logger.error(f"❌ Error parseando JSON de la IA: {exc}")
            logger.error(f"Texto crudo recibido: {response_text[:500]}")
            # Aquí retornamos None para que el bot sepa que falló
            return None

        processed_scenes = []
        for idx, scene in enumerate(scenes_array, start=1):
            text = scene.get("text") or scene.get("narration")
            visual_query = scene.get("visual_query") or scene.get("visual_search_query")
            duration = float(scene.get("duration", scene.get("duration_estimate", 4)))

            if not text or not visual_query:
                logger.warning(f"Escena {idx} incompleta, se omitirá.")
                continue

            if duration <= 0:
                duration = 4.0

            visual_query = _ensure_descriptive_query(
                visual_query,
                fallback=f"{topic} {text}",
            )
            if visual_keywords:
                visual_query = _append_keywords(visual_query, visual_keywords)

            processed_scenes.append({
                "scene_number": idx,
                "text": text.strip(),
                "visual_query": visual_query.strip(),
                "duration": round(duration, 2),
            })

        if not processed_scenes:
            raise ValueError("Gemini no generó escenas válidas.")

        # Etiquetar estructura básica por segmentos narrativos.
        if len(processed_scenes) >= 3:
            processed_scenes[0]["segment"] = "HOOK"
            processed_scenes[-1]["segment"] = "TWIST"
            for middle in processed_scenes[1:-1]:
                middle["segment"] = "BODY"
        else:
            for scene in processed_scenes:
                scene["segment"] = "BODY"

        # ============================================================
        # AJUSTE DE DURACIÓN (SCALING)
        # ============================================================
        # La IA a veces falla en la suma total. Ajustamos proporcionalmente
        # para que coincida EXACTAMENTE con la duración objetivo.
        
        current_total_duration = sum(scene["duration"] for scene in processed_scenes)
        target_total_duration = duration_minutes * 60.0
        
        if current_total_duration > 0:
            scale_factor = target_total_duration / current_total_duration
            
            # Solo escalar si la desviación es significativa (>10%)
            if abs(scale_factor - 1.0) > 0.1:
                logger.info(f"⏱️ Ajustando duración del guion: {current_total_duration:.1f}s -> {target_total_duration:.1f}s (Factor: {scale_factor:.2f})")
                for scene in processed_scenes:
                    scene["duration"] = round(scene["duration"] * scale_factor, 2)
            else:
                logger.info(f"⏱️ Duración del guion precisa ({current_total_duration:.1f}s). No se requiere ajuste.")
        
        final_total_duration = sum(scene["duration"] for scene in processed_scenes)

        logger.success(
            f"Guion generado con {len(processed_scenes)} escenas "
            f"(duración final {final_total_duration:.1f}s)."
        )
        for scene in processed_scenes:
            logger.info(
                f"[Escena {scene['scene_number']}] {scene['segment']} "
                f"({scene['duration']}s) → visual_query: {scene['visual_query']}"
            )

        # Retornar directamente la lista de escenas para compatibilidad con main.py
        return processed_scenes
