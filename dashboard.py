"""
Metratron Films - Production Suite Dashboard
Professional video production pipeline interface
"""

import streamlit as st
import time
import sys
import os
import asyncio
import json
import shutil
import threading
import random
from pathlib import Path

# --- FIX DE METRATRON: FORZAR UTF-8 EN CONSOLA WINDOWS ---
try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass  # Si falla (ej: en algunos entornos web), no romper nada
# ---------------------------------------------------------
from datetime import datetime, timedelta, time as dt_time, time as dt_time
from typing import List, Optional
from dotenv import load_dotenv
from loguru import logger
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips

# Importar el bot
from main import AutoViralBot
from src.profile_manager import ProfileManager
from src.analytics import AnalyticsManager
from src.cleaner import DiskCleaner
from src.audio_preview import generate_voice_preview

IG_SESSION_FILE = Path("ig_session.json")


def clean_style_name(style_input: str) -> str:
    """
    Sanitiza el nombre del estilo, quitando emojis y normalizando a la clave del diccionario STYLES.
    
    Args:
        style_input: Nombre del estilo con o sin emoji (ej: "💀 Horror / Creepypasta" o "HORROR")
    
    Returns:
        Clave limpia del estilo (ej: "HORROR", "MOTIVACION", "CURIOSIDADES")
    """
    if not style_input:
        return "CURIOSIDADES"
    
    # Si ya es una clave válida, devolverla directamente
    style_upper = style_input.upper().strip()
    valid_styles = ["HORROR", "MOTIVACION", "CURIOSIDADES", "MUSICAL", "LUJO", 
                   "CRIMEN", "HUMOR", "FUTURISMO", "TECH", "SALUD", "RELIGION", "CUSTOM"]
    if style_upper in valid_styles:
        return style_upper
    
    # Mapeo de patrones en el texto a claves limpias
    style_input_lower = style_input.lower()
    
    if "horror" in style_input_lower or "creepypasta" in style_input_lower:
        return "HORROR"
    if "motivacion" in style_input_lower or "estoicismo" in style_input_lower:
        return "MOTIVACION"
    if "curiosidades" in style_input_lower or "hechos" in style_input_lower:
        return "CURIOSIDADES"
    if "musical" in style_input_lower or "visualizer" in style_input_lower:
        return "MUSICAL"
    if "lujo" in style_input_lower or "business" in style_input_lower:
        return "LUJO"
    if "crimen" in style_input_lower or "misterio" in style_input_lower:
        return "CRIMEN"
    if "humor" in style_input_lower or "random" in style_input_lower:
        return "HUMOR"
    if "futurismo" in style_input_lower:
        return "FUTURISMO"
    if "tech" in style_input_lower or "noticias tech" in style_input_lower or "ia" in style_input_lower:
        return "TECH"
    if "salud" in style_input_lower or "bienestar" in style_input_lower:
        return "SALUD"
    if "religion" in style_input_lower or "fe" in style_input_lower or "religión" in style_input_lower:
        return "RELIGION"
    if "personalizado" in style_input_lower or "custom" in style_input_lower:
        return "CUSTOM"
    
    # Fallback: intentar usar el input tal cual o devolver el default
    return style_upper if style_upper in valid_styles else "CURIOSIDADES"


def parse_hashtags_from_text(text: str) -> List[str]:
    """Convierte un string en una lista de hashtags normalizados."""
    if not text:
        return []
    separators = text.replace(",", " ").split()
    hashtags = []
    for token in separators:
        cleaned = token.strip()
        if not cleaned:
            continue
        if not cleaned.startswith("#"):
            cleaned = f"#{cleaned}"
        hashtags.append(cleaned)
    return hashtags

# Importar uploaders (con manejo de errores si no están instalados)
try:
    from src.uploader import YouTubeUploader, TikTokUploader
    UPLOADERS_AVAILABLE = True
except ImportError as e:
    UPLOADERS_AVAILABLE = False
    logger.warning(f"⚠️ Uploaders no disponibles: {e}")
    logger.info("💡 Para habilitar uploads, instala: pip install google-auth-oauthlib google-api-python-client tiktok-uploader")

# Cargar variables de entorno
load_dotenv()

# --- CONFIGURACIÓN DE ESTILOS ---
CURRENT_STYLE = "CURIOSIDADES"  # Estilo por defecto

STYLES = {
    "HORROR": {
        "style_prompt": """ESTILO: HORROR / CREEPYPASTA
TONO: Siniestro, pausado, con susurros y silencios.
VISUALES: Oscuro, brumoso, luces rojas, símbolos ocultos.
VOZ: Profunda, lenta, susurrante.""",
        "voice": "es-MX-JorgeNeural",
        "voice_rate": "+0%",
        "music_query": "suspense scary"
    },
    "MOTIVACION": {
        "style_prompt": """ESTILO: MOTIVACIÓN / ESTOICISMO
TONO: Enérgico, firme, mentor exigente.
VISUALES: Amaneceres, gimnasios, atletas, paisajes épicos.
VOZ: Clara, enérgica, apasionada.""",
        "voice": "es-AR-TomasNeural",
        "voice_rate": "+5%",
        "music_query": "epic cinematic"
    },
    "CURIOSIDADES": {
        "style_prompt": """ESTILO: CURIOSIDADES / HECHOS
TONO: Rápido, informativo, directo al dato.
VISUALES: Colores vivos, gráficos, macro shots.
VOZ: Clara, rápida, entusiasta.""",
        "voice": "es-MX-DaliaNeural",
        "voice_rate": "+5%",
        "music_query": "lofi hiphop beat"
    },
    "MUSICAL": {
        "style_prompt": """ESTILO: VIDEO MUSICAL / VISUALIZER
TONO: Letras cortas, repetitivas, sensoriales.
VISUALES: Abstracto, neón, loops hipnóticos, glitch.
VOZ: Flotante, suave, melódica.""",
        "voice": "es-US-PalomaNeural",
        "voice_rate": "+0%",
        "music_query": "synthwave neon"
    },
    "LUJO": {
        "style_prompt": """ESTILO: LUJO / BUSINESS
TONO: Seguro, autoritario, mentor millonario.
VISUALES: Supercars, mansiones, relojes, skyline de Dubai.
VOZ: Masculina elegante, pausada.""",
        "voice": "es-ES-AlvaroNeural",
        "voice_rate": "-5%",
        "music_query": "trap luxury"
    },
    "CRIMEN": {
        "style_prompt": """ESTILO: TRUE CRIME / MISTERIO
TONO: Sobrio, investigativo, documental.
VISUALES: Blanco y negro, archivos policiales, sombras, detectives.
VOZ: Grave, seria, con pausas.""",
        "voice": "es-US-AlonsoNeural",
        "voice_rate": "-5%",
        "music_query": "noir ambient"
    },
    "HUMOR": {
        "style_prompt": """ESTILO: HUMOR / RANDOM
TONO: Sarcástico, hiperactivo, inesperado.
VISUALES: Memes, colores chillones, reacciones exageradas.
VOZ: Aguda, juguetona, acelerada.""",
        "voice": "es-MX-CeciliaNeural",
        "voice_rate": "+10%",
        "music_query": "comedy quirky"
    },
    "FUTURISMO": {
        "style_prompt": """ESTILO: FUTURISMO / TECH
TONO: Visionario, acelerado, como narrador sci-fi.
VISUALES: Cyberpunk, robots, neón, hologramas, código Matrix.
VOZ: Neutra, clara, ligeramente robótica.""",
        "voice": "es-ES-ElviraNeural",
        "voice_rate": "+3%",
        "music_query": "cyberpunk pulse"
    },
    "TECH": {
        "style_prompt": """ESTILO: IA / NOTICIAS TECH
TONO: Informativo, futurista, entusiasta pero con datos.
VISUALES: Robots humanoides, microchips, salas de servidores, interfaces holográficas, cascos de realidad virtual, ciudades futuristas, código Matrix.
VOZ: Nítida, rápida, geek.""",
        "voice": "es-ES-ElviraNeural",
        "voice_rate": "+5%",
        "music_query": "tech electronic"
    },
    "SALUD": {
        "style_prompt": """ESTILO: SALUD / BIENESTAR
TONO: Calmado, empático, inspirador, científico pero simple.
VISUALES: Frutas frescas, yoga al amanecer, zapatillas corriendo, agua, meditación, spa, ensaladas saludables, cocina brillante, caminatas en naturaleza.
VOZ: Suave, calmada, motivadora.""",
        "voice": "es-ES-ElviraNeural",
        "voice_rate": "-5%",
        "music_query": "calm meditation"
    },
    "RELIGION": {
        "style_prompt": """ESTILO: FE / RELIGIÓN
TONO: Solemne, suave, con pausas reflexivas, cálido y profundo.
VISUALES: Rayos de sol entre nubes, manos rezando, luz de velas, vitrales de iglesia, biblia abierta, silueta de cruz, río pacífico, paloma volando.
VOZ: Cálida, profunda, solemne.""",
        "voice": "es-ES-AlvaroNeural",
        "voice_rate": "-10%",
        "music_query": "peaceful ambient"
    },
    "CUSTOM": {
        "style_prompt": "",
        "voice": "es-MX-DaliaNeural",
        "voice_rate": "+0%",
        "music_query": "ambient focus"
    }
}

# Configuración de la página (Estilo Cyberpunk/Dark)
st.set_page_config(
    page_title="Metratron Films | Production Suite",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FUNCIONES PARA CARGAR CSS Y JS ---
def load_css():
    """Carga los archivos CSS cyberpunk."""
    css_files = ['cursor.css', 'theme.css']
    css_content = ""
    
    for css_file in css_files:
        css_path = Path(css_file)
        if css_path.exists():
            try:
                with open(css_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    
                    # Si es cursor.css, reemplazar referencias a cursor.svg con data URI
                    if css_file == 'cursor.css':
                        svg_path = Path('cursor.svg')
                        if svg_path.exists():
                            with open(svg_path, 'r', encoding='utf-8') as svg_f:
                                svg_content = svg_f.read()
                                # Convertir SVG a data URI
                                import base64
                                svg_encoded = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                                data_uri = f"data:image/svg+xml;base64,{svg_encoded}"
                                # Reemplazar referencias al SVG
                                file_content = file_content.replace(
                                    "url('cursor.svg')",
                                    f"url('{data_uri}')"
                                )
                                # También reemplazar referencias al PNG
                                png_path = Path('cursor.png')
                                if png_path.exists():
                                    with open(png_path, 'rb') as png_f:
                                        png_content = png_f.read()
                                        png_encoded = base64.b64encode(png_content).decode('utf-8')
                                        png_data_uri = f"data:image/png;base64,{png_encoded}"
                                        file_content = file_content.replace(
                                            "url('cursor.png')",
                                            f"url('{png_data_uri}')"
                                        )
                    
                    css_content += f"\n/* {css_file} */\n{file_content}\n"
            except Exception as e:
                logger.warning(f"No se pudo cargar {css_file}: {e}")
        else:
            logger.warning(f"Archivo CSS no encontrado: {css_file}")
    
    if css_content:
        st.markdown(f'<style>{css_content}</style>', unsafe_allow_html=True)

def load_js():
    """Carga el archivo JavaScript para efectos del cursor."""
    js_file = Path('cursor.js')
    if js_file.exists():
        try:
            with open(js_file, 'r', encoding='utf-8') as f:
                js_content = f.read()
                st.markdown(f'<script>{js_content}</script>', unsafe_allow_html=True)
        except Exception as e:
            logger.warning(f"No se pudo cargar cursor.js: {e}")
    else:
        logger.warning("Archivo cursor.js no encontrado")

# Cargar estilos cyberpunk al inicio
load_css()
load_js()

# --- PARCHE DE LIMPIEZA VISUAL (METRATRON FIX) ---
st.markdown("""
    <style>
    /* 1. Matar bordes fantasmas en los contenedores */
    div[data-testid="stVerticalBlock"], div[data-testid="stHorizontalBlock"], div[data-testid="stBlock"] {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }
    
    /* 2. Forzar fondo limpio (elimina patrones repetidos o líneas) */
    .stApp {
        background-image: none !important;
        background: #0e1117 !important; /* Negro Cyberpunk Puro */
    }
    
    /* 3. Asegurar que el header no tenga líneas */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    </style>
""", unsafe_allow_html=True)

# Inicializar sesión
if 'generated_script' not in st.session_state:
    st.session_state.generated_script = None
    st.session_state.generated_script_text = None
    st.session_state.generated_audio_path = None
    st.session_state.current_video = None
    st.session_state.viral_title = None
    st.session_state.viral_hook = None

# Streamlit Logger para capturar logs
class StreamlitLogger:
    def __init__(self):
        self.logs = []
    
    def write(self, message):
        if message.strip():
            self.logs.append(message.strip())
            if len(self.logs) > 100:
                self.logs.pop(0)
    
    def get_logs(self):
        return self.logs
    
    def clear(self):
        self.logs = []

if 'streamlit_logger' not in st.session_state:
    st.session_state.streamlit_logger = StreamlitLogger()

if 'profile_manager' not in st.session_state:
    st.session_state.profile_manager = ProfileManager()

if 'analytics_manager' not in st.session_state:
    st.session_state.analytics_manager = AnalyticsManager()

if 'disk_cleaner' not in st.session_state:
    st.session_state.disk_cleaner = DiskCleaner()

if 'voice_override' not in st.session_state:
    default_voice = STYLES.get(CURRENT_STYLE, STYLES["CURIOSIDADES"]).get('voice', 'es-MX-DaliaNeural')
    st.session_state.voice_override = default_voice
    st.session_state.voice_override_label = "Voz por defecto"

if 'default_hashtags' not in st.session_state:
    st.session_state.default_hashtags = []

if 'instagram_hashtags' not in st.session_state:
    st.session_state.instagram_hashtags = " ".join(st.session_state.default_hashtags)

if 'current_thumbnail' not in st.session_state:
    st.session_state.current_thumbnail = None

if 'voice_preview_text' not in st.session_state:
    st.session_state.voice_preview_text = "Hola, soy la voz de tu próximo video viral."

if 'voice_preview_path' not in st.session_state:
    st.session_state.voice_preview_path = None

if 'voice_preview_sidebar_text' not in st.session_state:
    st.session_state.voice_preview_sidebar_text = "Probando, probando, 1, 2, 3."

if 'use_crossfade_transitions' not in st.session_state:
    st.session_state.use_crossfade_transitions = False

if 'voice_speed_factor' not in st.session_state:
    st.session_state.voice_speed_factor = 1.1

if 'trim_voice_silence' not in st.session_state:
    st.session_state.trim_voice_silence = True

if 'use_branding' not in st.session_state:
    st.session_state.use_branding = False

def apply_profile_to_session(profile_data: dict):
    """Actualiza los valores del dashboard según un perfil guardado."""
    if not profile_data:
        return
    style_code = profile_data.get("style") or CURRENT_STYLE
    style_label = profile_data.get("style_label")
    style_map = {
        "HORROR": "Horror / Creepypasta",
        "MOTIVACION": "Motivación / Estoicismo",
        "CURIOSIDADES": "Curiosidades / Hechos",
        "MUSICAL": "🎵 Video Musical / Visualizer",
        "LUJO": "💸 Lujo / Business",
        "CRIMEN": "🕵️ Crimen Real / Misterio",
        "HUMOR": "🤣 Humor / Random",
        "FUTURISMO": "🔮 Futurismo / Tech",
        "SALUD": "🌿 Salud / Bienestar",
        "RELIGION": "🙏 Fe / Religión",
        "CUSTOM": "✨ Estilo Personalizado (Escribir abajo)",
    }
    if not style_label:
        style_label = style_map.get(style_code, style_map["CURIOSIDADES"])
    st.session_state.selected_style_code = style_code
    st.session_state.selected_style_label = style_label
    st.session_state.custom_style_prompt = profile_data.get("system_prompt", "")
    st.session_state.voice_override = profile_data.get("voice") or st.session_state.voice_override
    st.session_state.voice_override_label = profile_data.get("voice_label", st.session_state.voice_override_label)
    # RunwayML deshabilitado - Siempre False
    st.session_state.use_runway = False
    st.session_state.runway_mode = None
    st.session_state.runway_api_key = None
    hashtags = profile_data.get("hashtags", [])
    st.session_state.default_hashtags = hashtags
    st.session_state.instagram_hashtags = " ".join(hashtags)
    st.session_state.watermark_text = profile_data.get("watermark_text", "")
    st.session_state.watermark_position = profile_data.get("watermark_position", "bottom-right")

def build_profile_payload(profile_name: str) -> dict:
    """Construye el payload del perfil basándose en la configuración actual."""
    hashtags_text = st.session_state.get("instagram_hashtags")
    if hashtags_text is None:
        hashtags_list = st.session_state.get("default_hashtags", [])
    else:
        hashtags_list = parse_hashtags_from_text(hashtags_text)
    st.session_state.default_hashtags = hashtags_list
    return {
        "name": profile_name,
        "style": st.session_state.get("selected_style_code", CURRENT_STYLE),
        "style_label": st.session_state.get("selected_style_label"),
        "system_prompt": st.session_state.get("custom_style_prompt", ""),
        "voice": st.session_state.get("voice_override"),
        "voice_label": st.session_state.get("voice_override_label"),
        "apis": {
            "use_runway": False,  # RunwayML deshabilitado
            "runway_mode": None,
            "runway_api_key": None,
        },
        "hashtags": hashtags_list,
        "watermark_text": st.session_state.get("watermark_text"),
        "watermark_position": st.session_state.get("watermark_position", "bottom-right"),
    }

# --- SIDEBAR (CONFIGURACIÓN) ---
with st.sidebar:
    # --- LOGO DE LA EMPRESA ---
    # Opción 1: Logo Local (Si existe el archivo logo.png en la carpeta)
    if os.path.exists("logo.png"):
        st.image("logo.png", width=200)
    # Opción 2: Logo Cloud (Fallback profesional - Cámara de Cine 3D)
    else:
        st.image("https://img.icons8.com/3d-fluency/375/cinema-camera.png", width=180)
    
    st.markdown("---")  # Separador visual
    st.title("⚙️ Configuración")
    
    profile_manager: ProfileManager = st.session_state.profile_manager
    analytics_manager: AnalyticsManager = st.session_state.analytics_manager
    
    profiles = ["Configuración Actual"] + profile_manager.list_profiles()
    active_profile = st.session_state.get("active_profile", profiles[0])
    if active_profile not in profiles:
        active_profile = profiles[0]
    selected_profile_sidebar = st.selectbox("Seleccionar Perfil", profiles, index=profiles.index(active_profile))
    if selected_profile_sidebar != active_profile:
        st.session_state.active_profile = selected_profile_sidebar
        if selected_profile_sidebar != "Configuración Actual":
            loaded_profile = profile_manager.load_profile(selected_profile_sidebar)
            if loaded_profile:
                apply_profile_to_session(loaded_profile)
        st.experimental_rerun()
    
    profile_name_input = st.text_input("Nombre del Perfil", value=st.session_state.get("pending_profile_name", ""))
    if st.button("💾 Guardar Configuración Actual como Perfil", use_container_width=True):
        if not profile_name_input.strip():
            st.warning("Ingresa un nombre para el perfil.")
        else:
            payload = build_profile_payload(profile_name_input.strip())
            profile_manager.save_profile(profile_name_input.strip(), payload)
            st.session_state.pending_profile_name = ""
            st.success(f"Perfil '{profile_name_input.strip()}' guardado.")
            st.session_state.active_profile = profile_name_input.strip().title()
            st.experimental_rerun()

    # Estado de APIs
    api_status = st.empty()
    gemini_key = os.getenv("GEMINI_API_KEY")
    pexels_key = os.getenv("PEXELS_API_KEY")
    
    if gemini_key and pexels_key:
        api_status.success("✅ APIs Conectadas")
    elif gemini_key:
        api_status.warning("⚠️ Falta Pexels API")
    elif pexels_key:
        api_status.warning("⚠️ Falta Gemini API")
    else:
        api_status.error("❌ APIs No Configuradas")
    
    st.divider()
    
    # Selector de estilo/nicho con experiencias ampliadas (todos con emojis uniformes)
    style_choices = [
        ("💀 Horror / Creepypasta", "HORROR"),
        ("🦁 Motivación / Estoicismo", "MOTIVACION"),
        ("🧠 Curiosidades / Hechos", "CURIOSIDADES"),
        ("🎵 Video Musical / Visualizer", "MUSICAL"),
        ("💸 Lujo / Business", "LUJO"),
        ("🕵️ Crimen Real / Misterio", "CRIMEN"),
        ("🤣 Humor / Random", "HUMOR"),
        ("🔮 Futurismo / Tech", "FUTURISMO"),
        ("🤖 IA / Noticias Tech", "TECH"),
        ("🌿 Salud / Bienestar", "SALUD"),
        ("🙏 Fe / Religión", "RELIGION"),
        ("✨ Estilo Personalizado", "CUSTOM"),
    ]
    label_to_code = {label: code for label, code in style_choices}
    style_labels = [label for label, _ in style_choices]
    stored_style_code = st.session_state.get("selected_style_code", CURRENT_STYLE)
    default_index = next(
        (idx for idx, (_, code) in enumerate(style_choices) if code == stored_style_code),
        0
    )
    
    selected_style_label = st.selectbox(
        "🎨 Estilo / Nicho Narrativo",
        style_labels,
        index=default_index,
        help="Elige la vibra creativa del video: terror, motivación, curiosidades, lujo, true crime, humor, futurismo, tech, salud, religión o define tu propio estilo."
    )
    selected_style = label_to_code[selected_style_label]
    style_info_sidebar = STYLES.get(selected_style, STYLES["CURIOSIDADES"])
    st.session_state.selected_style_label = selected_style_label
    st.session_state.selected_style_code = selected_style
    
    custom_style_prompt_input = ""
    if selected_style == "CUSTOM":
        custom_style_prompt_input = st.text_input(
            "🧪 Describe tu estilo personalizado",
            placeholder="Ej: Voz sensual, visuales vaporwave glitch con neón morado y lluvia digital",
            key="custom_style_prompt_input"
        )
    st.session_state.custom_style_prompt = custom_style_prompt_input.strip()
    
    # Selector de plataforma
    platform = st.selectbox(
        "📢 Plataforma Destino",
        ["TikTok", "Instagram Reels", "YouTube Shorts"],
        index=2,
        help="El formato vertical 9:16 funciona para todas"
    )
    
    # Duración
    duration_minutes = st.slider(
        "⏱️ Duración (minutos)",
        0.5, 3.0, 1.0, 0.1,
        help="Duración objetivo del video generado"
    )
    
    # Volumen de música
    music_volume = st.slider(
        "🔊 Volumen Música de Fondo",
        0.0, 0.5, 0.1, 0.05,
        help="Volumen de la música de fondo (0.0 = sin música, 0.5 = muy fuerte)"
    )

    smooth_transitions = st.checkbox(
        "🎬 Usar Transiciones Suaves (Crossfade)",
        value=st.session_state.get("use_crossfade_transitions", False),
        help="Activa un fundido de 0.5s entre escenas para un look más cinematográfico."
    )
    st.session_state.use_crossfade_transitions = smooth_transitions

    voice_speed_factor = st.slider(
        "⚡ Velocidad de Voz (Ritmo)",
        min_value=1.0,
        max_value=1.5,
        value=float(st.session_state.get("voice_speed_factor", 1.1)),
        step=0.01,
        help="Acelera ligeramente la voz para mejorar la retención (ideal 1.10x - 1.20x)."
    )
    st.session_state.voice_speed_factor = voice_speed_factor

    trim_voice_silence = st.checkbox(
        "✂️ Recortar Silencios (Inicio/Fin)",
        value=st.session_state.get("trim_voice_silence", True),
        help="Elimina el aire muerto antes y después de cada narración generada."
    )
    st.session_state.trim_voice_silence = trim_voice_silence

    use_branding = st.checkbox(
        "📢 Añadir Branding (Intro/Outro)",
        value=st.session_state.get("use_branding", False),
        help="Agrega automáticamente los clips de intro/outro y el call-to-action 'Suscríbete' si están disponibles en assets/branding."
    )
    st.session_state.use_branding = use_branding

    with st.expander("🔊 Probador de Voces en Vivo", expanded=False):
        current_voice_id = st.session_state.get("voice_override") or style_info_sidebar.get('voice', 'es-MX-DaliaNeural')
        current_voice_label = st.session_state.get("voice_override_label", current_voice_id)
        st.caption(f"Voz actual: **{current_voice_label}**")

        default_live_text = "Probando, probando, 1, 2, 3."
        sidebar_preview_text = st.text_input(
            "Texto de prueba",
            value=st.session_state.get("voice_preview_sidebar_text", default_live_text),
            key="voice_preview_sidebar_text_input"
        )
        st.session_state.voice_preview_sidebar_text = sidebar_preview_text

        preview_sidebar_btn = st.button("▶️ Escuchar Voz Actual", key="voice_preview_sidebar_button")
        if preview_sidebar_btn:
            if current_voice_id == "NO_VOICE":
                st.warning("Selecciona una voz diferente a 'Sin Narración' para escuchar la previsualización.")
            else:
                clean_text = (sidebar_preview_text or default_live_text).strip()
                try:
                    with st.spinner("🎧 Generando preview..."):
                        preview_path = generate_voice_preview(
                            clean_text,
                            current_voice_id,
                            filename="voice_preview_live.mp3"
                        )
                except Exception as e:
                    preview_path = None
                    logger.error(f"❌ Error generando preview en vivo: {e}")

                if preview_path and Path(preview_path).exists():
                    st.session_state.voice_preview_path = preview_path
                    st.success("✅ Vista previa lista. Reprodúcela abajo.")
                else:
                    st.error("❌ No se pudo generar la vista previa. Inténtalo nuevamente.")

        stored_sidebar_preview = st.session_state.get("voice_preview_path")
        if stored_sidebar_preview and Path(stored_sidebar_preview).exists():
            st.audio(stored_sidebar_preview)
            st.caption("🔁 Última vista previa generada")
    
    st.divider()
    
    # --- MARCA DE AGUA (WATERMARK) ---
    st.subheader("© Marca de Agua")
    
    watermark_text = st.text_input(
        "© Marca de Agua (Usuario)",
        value=st.session_state.get("watermark_text", ""),
        placeholder="@MiCanal o Mi Nombre",
        help="Texto que aparecerá como marca de agua en todos los videos generados"
    )
    st.session_state.watermark_text = watermark_text.strip() if watermark_text else None
    
    watermark_position = st.selectbox(
        "📍 Posición de la Marca de Agua",
        ["bottom-right", "top-center", "bottom-left", "top-right"],
        index=0,
        help="Dónde aparecerá la marca de agua en el video"
    )
    st.session_state.watermark_position = watermark_position
    
    if watermark_text:
        st.info(f"💡 La marca de agua '{watermark_text}' aparecerá en la esquina {watermark_position.replace('-', ' ')} del video.")
    else:
        st.caption("💡 Deja vacío para no agregar marca de agua.")
    
    st.divider()
    
    # --- CONFIGURACIÓN DE FORMATO Y RESOLUCIÓN ---
    st.subheader("📐 Formato y Resolución")
    
    # Selector de Aspect Ratio
    aspect_ratio_options = {
        "Vertical 9:16 (TikTok/Shorts)": (9, 16),
        "Horizontal 16:9 (YouTube)": (16, 9),
        "Cuadrado 1:1 (Instagram/Facebook)": (1, 1)
    }
    
    selected_aspect = st.selectbox(
        "📐 Formato (Aspect Ratio)",
        list(aspect_ratio_options.keys()),
        index=0,
        help="Selecciona el formato del video final"
    )
    
    # Calcular dimensiones objetivo basado en aspect ratio
    # Nota: La exportación final siempre será Super 1080p (1080x1920) para máxima calidad
    aspect_w, aspect_h = aspect_ratio_options[selected_aspect]
    base_resolution = 1080  # Siempre usar 1080 como base para procesamiento
    
    # Calcular width y height basado en aspect ratio (para procesamiento interno)
    if aspect_w / aspect_h > 1:  # Horizontal
        target_width = int(base_resolution * (aspect_w / aspect_h))
        target_height = base_resolution
    elif aspect_w / aspect_h < 1:  # Vertical
        target_width = base_resolution
        target_height = int(base_resolution * (aspect_h / aspect_w))
    else:  # Cuadrado
        target_width = base_resolution
        target_height = base_resolution
    
    # Guardar en session_state para usar en el procesamiento
    st.session_state.target_width = target_width
    st.session_state.target_height = target_height
    st.session_state.aspect_ratio = (aspect_w, aspect_h)
    
    # Mostrar información de calidad optimizada
    st.info("⚙️ **Calidad: Super 1080p (60 FPS / High Bitrate)** - Optimizado para máxima calidad en TikTok/Reels")
    st.caption(f"📐 Formato de procesamiento: **{target_width}x{target_height}** ({aspect_w}:{aspect_h}) → Exportación final: **1080x1920** @ 60 FPS")
    
    st.divider()
    
    # --- CONFIGURACIÓN DE SUBTÍTULOS ---
    st.subheader("📝 Subtítulos")
    
    use_subtitles = st.checkbox(
        "📝 Incrustar Subtítulos (Burn-in)",
        value=True,
        help="Si está activado, los subtítulos se incrustarán permanentemente en el video. Si está desactivado, el video se renderiza sin texto (Clean Feed)."
    )
    
    # Guardar en session_state para usar en el procesamiento
    st.session_state.use_subtitles = use_subtitles
    
    if not use_subtitles:
        st.info("💡 **Clean Feed**: El video se renderizará sin subtítulos (solo video + audio). Más rápido y menor tamaño de archivo.")
    
    st.divider()
    
    # --- CONFIGURACIÓN DE COLOR GRADING ---
    st.subheader("🎨 Post-Producción")
    
    enable_color_grading = st.checkbox(
        "🎨 Aplicar Filtros de Cine (Color Grading)",
        value=st.session_state.get("enable_color_grading", False),
        help="Aplica corrección de color profesional (saturación y contraste mejorados) para que los videos no parezcan 'stock crudo'. Aumenta ligeramente el tiempo de renderizado."
    )
    
    # Guardar en session_state
    st.session_state.enable_color_grading = enable_color_grading
    
    if enable_color_grading:
        st.info("💡 **Color Grading Activado**: Los videos tendrán mejor saturación y contraste para un look más profesional.")
    
    st.divider()
    
    # --- FUENTES DE VÍDEO DISPONIBLES ---
    st.info("🎬 **Fuentes de Video:** Stock gratuito (Pexels/Pixabay) y DALL-E 3 como fallback para imágenes.")
    
    # Configuración interna: RunwayML siempre deshabilitado
    st.session_state.use_runway = False
    st.session_state.runway_api_key = None
    st.session_state.runway_mode = None
    st.session_state.motion_intensity = 5
    
    st.divider()
    
    # --- BIBLIOTECA MUSICAL (AUTO-DJ) ---
    st.subheader("🎵 Biblioteca Musical")
    
    # Inicializar MusicManager si no existe
    if 'music_manager' not in st.session_state:
        from src.music_manager import MusicManager
        st.session_state.music_manager = MusicManager()
    
    music_manager = st.session_state.music_manager
    music_counts = music_manager.get_music_count_by_genre()
    
    # Mostrar conteo por género
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Horror", music_counts.get("Horror", 0))
        st.metric("Motivation", music_counts.get("Motivation", 0))
    with col_m2:
        st.metric("Lofi", music_counts.get("Lofi", 0))
        st.metric("Curiosity", music_counts.get("Curiosity", 0))
    st.metric("General", music_counts.get("General", 0))
    
    # Selector de género para subir música
    genre_to_upload = st.selectbox(
        "Género para subir música",
        ["horror", "motivation", "lofi", "curiosity", "general"],
        help="Selecciona el género donde quieres agregar música"
    )
    
    uploaded_music = st.file_uploader(
        "Subir archivo MP3/WAV",
        type=['mp3', 'wav'],
        help="Sube música para que el Auto-DJ la seleccione aleatoriamente"
    )
    
    if uploaded_music:
        genre_folder = Path(f"assets/music/{genre_to_upload}")
        genre_folder.mkdir(parents=True, exist_ok=True)
        target_path = genre_folder / uploaded_music.name
        
        try:
            with open(target_path, "wb") as f:
                f.write(uploaded_music.getbuffer())
            st.success(f"✅ Música guardada en: {genre_to_upload}/{uploaded_music.name}")
            st.rerun()
        except Exception as e:
            st.error(f"Error guardando música: {e}")
    
    st.divider()
    
    # Información del sistema
    st.caption("**MF-Studio v2.5 (Enterprise)**")
    st.caption("© 2025 Metratron Films - Internal Tools")
    st.caption(f"Estilo activo: **{selected_style_label}**")
    
    # Consola de logs en sidebar
    st.subheader("📡 Logs")
    log_container = st.container(height=200, border=True)
    with log_container:
        logs = st.session_state.streamlit_logger.get_logs()
        if logs:
            for log in logs[-10:]:  # Últimos 10 logs
                if "ERROR" in log or "❌" in log:
                    st.error(log, icon="❌")
                elif "SUCCESS" in log or "✅" in log:
                    st.success(log, icon="✅")
                elif "WARNING" in log or "⚠️" in log:
                    st.warning(log, icon="⚠️")
                else:
                    st.caption(log)
        else:
            st.info("Esperando acciones...")
    
    if st.button("🗑️ Limpiar Logs", use_container_width=True):
        st.session_state.streamlit_logger.clear()
        st.rerun()

    if st.button("🧹 Limpiar Archivos Temporales Ahora", use_container_width=True):
        freed = st.session_state.disk_cleaner.clean_temp_folder(0)
        st.success(f"✅ Se liberaron {freed} MB de espacio.")

analytics_manager: AnalyticsManager = st.session_state.analytics_manager
disk_cleaner: DiskCleaner = st.session_state.disk_cleaner

# --- PANEL PRINCIPAL CON TABS ---
st.title("🎬 METRATRON FILMS: Studio Console")
st.markdown('<p style="color: #00ff41; font-size: 14px; margin-top: -10px;">Professional Video Production Pipeline</p>', unsafe_allow_html=True)
st.markdown("---")

# Tabs principales
tabs = st.tabs(["⚡ Production Pipeline", "📝 Solo Guion", "🎙️ Solo Audio", "🎬 Solo Video", "🎨 Mezclador Manual", "📂 Galería / Biblioteca", "📈 Analytics"])

# ============================================================
# TAB 1: FULL AUTO (Flujo completo actual)
# ============================================================
with tabs[0]:
    st.header("⚡ Production Pipeline")
    st.caption("Complete video production workflow: Script → Audio → Video → Upload")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Mostrar título y hook si hay uno generado
        if st.session_state.viral_title:
            st.header(f"📌 {st.session_state.viral_title}")
        if st.session_state.viral_hook:
            st.subheader(f"🎣 {st.session_state.viral_hook}")
        
        # Checkbox para modo de noticias
        use_news_mode = st.checkbox(
            "🌍 Modo Noticias (Buscar Tendencias)",
            value=st.session_state.get('use_news_mode', False),
            help="Activa el modo de búsqueda de noticias en tiempo real. El tema se usará como término de búsqueda para encontrar noticias actuales."
        )
        st.session_state.use_news_mode = use_news_mode
        
        # Campo de tema (cambia el label según el modo)
        topic_label = "Tema de Búsqueda (ej: IA, Bitcoin)" if use_news_mode else "Tema del Video"
        topic_placeholder = "Ej: IA, Bitcoin, Tecnología..." if use_news_mode else "Ej: La verdad sobre los gatos negros..."
        topic_help = "Término de búsqueda para encontrar noticias recientes. El bot buscará noticias reales sobre este tema." if use_news_mode else "Describe el tema sobre el cual quieres generar el video"
        
        topic = st.text_input(
            topic_label,
            placeholder=topic_placeholder,
            help=topic_help
        )
        
        col_style_desc, col_duration_display = st.columns(2)
        with col_style_desc:
            style_info = STYLES.get(selected_style, STYLES["CURIOSIDADES"])
            voice_label = st.session_state.get('voice_override_label', style_info.get('voice', 'N/A'))
            st.info(f"**Estilo:** {selected_style_label}\n**Voz:** {voice_label}")
        
        with col_duration_display:
            st.metric("Duración Objetivo", f"{duration_minutes:.1f} min")
        
        prompt_custom = st.text_area(
            "Instrucciones Extra para el Guion (Opcional)",
            placeholder="Ej: Haz que el gancho sea muy agresivo, usa más emoción...",
            help="Instrucciones adicionales para personalizar el guion generado"
        )
        
        # --- MODO BUCLE INFINITO INTELIGENTE (SCHEDULER) ---
        with st.expander("🔄 Continuous Render Mode (Production Scheduler)", expanded=False):
            modo_bucle = st.checkbox(
                "🔄 Activate Continuous Render Mode",
                value=st.session_state.get('modo_bucle_activo', False),
                help="Activates automated continuous video production. The system will work automatically: generates videos, respects sleep schedules, and maintains humanized intervals."
            )
            
            st.session_state.modo_bucle_activo = modo_bucle
            
            if modo_bucle:
                st.info("🎬 **Continuous Render Mode Active:** The production pipeline will work automatically according to the configured schedule. You can stop it at any time.")
                
                # Intervalo base
                intervalo_base = st.slider(
                    "⏱️ Intervalo Base entre videos (minutos)",
                    min_value=30,
                    max_value=720,
                    value=st.session_state.get('intervalo_bucle', 120),
                    step=15,
                    help="Tiempo base de espera entre videos. Se randomizará entre -20% y +20% para parecer más humano."
                )
                st.session_state.intervalo_bucle = intervalo_base
                
                # Calcular rango randomizado
                intervalo_min = int(intervalo_base * 0.8)  # -20%
                intervalo_max = int(intervalo_base * 1.2)  # +20%
                st.caption(f"📊 Intervalo real: {intervalo_min}-{intervalo_max} minutos (randomizado)")
                
                # Horario de trabajo con slider doble
                st.markdown("#### 🕐 Horario de Trabajo")
                st.caption("Define el horario de producción activa. Fuera de este horario, el sistema entrará en modo reposo.")
                
                horario_default = st.session_state.get('horario_trabajo', [9, 22])
                horario_trabajo = st.slider(
                    "Horario de Trabajo (horas)",
                    min_value=0,
                    max_value=23,
                    value=horario_default,
                    help="Rango de horas en que el sistema trabajará activamente (ej: 9-22 = 9 AM a 10 PM)"
                )
                st.session_state.horario_trabajo = horario_trabajo
                hora_inicio_h = horario_trabajo[0]
                hora_fin_h = horario_trabajo[1]
                
                # Convertir a objetos time para compatibilidad
                hora_inicio = dt_time(hora_inicio_h, 0)
                hora_fin = dt_time(hora_fin_h, 0)
                st.session_state.hora_inicio_bucle = hora_inicio
                st.session_state.hora_fin_bucle = hora_fin
                st.session_state.horario_activo = True  # Siempre activo si el bucle está activo
                
                # Mostrar horario actual
                hora_actual = datetime.now().hour
                if hora_inicio_h <= hora_fin_h:
                    en_horario = hora_inicio_h <= hora_actual < hora_fin_h
                else:  # Cruza medianoche
                    en_horario = hora_actual >= hora_inicio_h or hora_actual < hora_fin_h
                
                if en_horario:
                    st.success(f"✅ **Actualmente en horario de trabajo:** {hora_inicio_h:02d}:00 - {hora_fin_h:02d}:00")
                else:
                    st.warning(f"😴 **Modo Reposo Activo:** El sistema está en pausa fuera del horario {hora_inicio_h:02d}:00 - {hora_fin_h:02d}:00")
                
                # Estado del bucle
                st.markdown("---")
                col_status1, col_status2 = st.columns(2)
                
                with col_status1:
                    if st.session_state.get('bucle_en_ejecucion', False):
                        st.warning("🔄 **BUCLE EN EJECUCIÓN**")
                        if st.button("🛑 DETENER BUCLE", type="primary", use_container_width=True):
                            st.session_state.detener_bucle = True
                            st.session_state.bucle_en_ejecucion = False
                            st.session_state.modo_bucle_activo = False
                            st.rerun()
                    else:
                        st.info("⏸️ Bucle detenido")
                        st.caption("Presiona 'GENERAR VIDEO COMPLETO' para iniciar el bucle")
                
                with col_status2:
                    if st.session_state.get('bucle_en_ejecucion', False):
                        siguiente_generacion = st.session_state.get('tiempo_proxima_generacion', None)
                        if siguiente_generacion:
                            tiempo_restante = siguiente_generacion - datetime.now()
                            if tiempo_restante.total_seconds() > 0:
                                horas = int(tiempo_restante.total_seconds() // 3600)
                                minutos = int((tiempo_restante.total_seconds() % 3600) // 60)
                                segundos = int(tiempo_restante.total_seconds() % 60)
                                if horas > 0:
                                    st.metric("⏳ Próximo video en", f"{horas:02d}:{minutos:02d}:{segundos:02d}")
                                else:
                                    st.metric("⏳ Próximo video en", f"{minutos:02d}:{segundos:02d}")
                            else:
                                st.metric("⏳ Estado", "Generando...")
                        else:
                            st.metric("⏳ Estado", "Iniciando...")
                    else:
                        st.caption("Esperando inicio...")
                
                # Lista de temas dentro del expander
                st.markdown("---")
                st.markdown("#### 📋 Production Queue")
                st.caption("Uno por línea. El sistema seleccionará temas de esta lista para cada producción.")
                
                lista_temas_default = st.session_state.get('lista_temas_bucle', "La verdad sobre los gatos negros\n5 secretos que NADIE te dice sobre los sueños\nPor qué los perros entienden más de lo que crees\nEl misterio de los colores que no existen\nCosas que pasan en tu cerebro mientras duermes")
                
                lista_temas_text = st.text_area(
                    "Production Topics (uno por línea)",
                    value=lista_temas_default,
                    height=150,
                    help="Escribe un tema por línea. El sistema elegirá uno aleatorio o secuencial para cada video.",
                    key="lista_temas_bucle_text"
                )
                
                temas_lista = [t.strip() for t in lista_temas_text.split('\n') if t.strip()]
                st.session_state.lista_temas_bucle = lista_temas_text
                st.session_state.temas_lista_procesada = temas_lista
                
                if temas_lista:
                    st.success(f"✅ {len(temas_lista)} tema(s) cargado(s)")
                    modo_seleccion = st.radio(
                        "Modo de selección de temas",
                        ["Aleatorio", "Secuencial"],
                        index=0,
                        horizontal=True,
                        help="Aleatorio: Elige un tema al azar. Secuencial: Sigue el orden de la lista.",
                        key="modo_seleccion_temas_radio"
                    )
                    st.session_state.modo_seleccion_temas = modo_seleccion
                else:
                    st.warning("⚠️ No hay temas en la lista. El sistema usará el tema del campo 'Tema del Video'.")
                    temas_lista = [topic] if topic else []
        
        # --- CONFIGURACIÓN DE SUBIDA AUTOMÁTICA ---
        with st.expander("📡 Configuración de Subida Automática", expanded=False):
            if not UPLOADERS_AVAILABLE:
                st.warning("⚠️ Los uploaders no están disponibles. Instala las dependencias:")
                st.code("pip install google-auth-oauthlib google-api-python-client tiktok-uploader", language="bash")
            
            col_yt, col_tt, col_ig = st.columns(3)
            
            with col_yt:
                subir_youtube = st.checkbox(
                    "📺 Subir a YouTube",
                    value=False,
                    disabled=not UPLOADERS_AVAILABLE,
                    help="Sube el video a YouTube automáticamente después de generarlo"
                )
                if subir_youtube and UPLOADERS_AVAILABLE:
                    youtube_privacy = st.selectbox(
                        "Privacidad de YouTube",
                        ["private", "unlisted", "public"],
                        index=0,
                        key="youtube_privacy"
                    )
                    st.caption("💡 Por defecto: 'private' (solo tú puedes verlo)")
            
            with col_tt:
                subir_tiktok = st.checkbox(
                    "🎵 Subir a TikTok",
                    value=False,
                    disabled=not UPLOADERS_AVAILABLE,
                    help="Sube el video a TikTok automáticamente después de generarlo"
                )
                if subir_tiktok and UPLOADERS_AVAILABLE:
                    tiktok_cookies = st.text_input(
                        "Ruta de Cookies de TikTok",
                        value="tiktok_cookies.txt",
                        key="tiktok_cookies_path",
                        help="Ruta al archivo de cookies de TikTok (formato Netscape)"
                    )
                    st.caption("💡 Exporta las cookies desde tu navegador")
            
            with col_ig:
                subir_instagram = st.checkbox(
                    "📸 Subir a Instagram Reels",
                    value=st.session_state.get("subir_instagram", False),
                    help="Publica el video como Reel en Instagram (y opcionalmente comparte en Facebook desde la app)."
                )
                st.session_state.subir_instagram = subir_instagram
                ig_username = None
                ig_password = None
                if subir_instagram:
                    ig_username = st.text_input(
                        "Usuario IG",
                        value=st.session_state.get("instagram_username", ""),
                        key="instagram_username"
                    )
                    ig_password = st.text_input(
                        "Contraseña IG",
                        value=st.session_state.get("instagram_password", ""),
                        type="password",
                        key="instagram_password"
                    )
                    st.caption("Meta recomienda habilitar 2FA y usar una cuenta profesional.")
                    
                    st.text_area(
                        "Hashtags default",
                        key="instagram_hashtags",
                        height=80,
                        help="Espacio o coma separada. Se agregan automáticamente al subir."
                    )
                    if st.button("Borrar Sesión Guardada", key="clear_ig_session_btn"):
                        if IG_SESSION_FILE.exists():
                            IG_SESSION_FILE.unlink()
                            st.success("Sesión de Instagram eliminada. Se pedirá login nuevamente.")
                        else:
                            st.info("No hay sesión guardada actualmente.")
        
        # --- PERSONALIZACIÓN DE METADATOS (OPCIONAL) ---
        with st.expander("📝 Personalizar Título y Descripción (Opcional)", expanded=False):
            st.caption("💡 Si dejas los campos vacíos, el sistema generará automáticamente los metadatos con IA. Si los llenas, usará tus valores personalizados.")
            
            custom_title = st.text_input(
                "📌 Título del Video",
                value=st.session_state.get('custom_title', ''),
                placeholder="Ej: 😱 Este Color NO EXISTE (La Ciencia lo Confirma)",
                help="Deja vacío para que la IA genere el título automáticamente"
            )
            
            custom_desc = st.text_area(
                "📝 Descripción / Caption",
                value=st.session_state.get('custom_desc', ''),
                placeholder="Ej: Descubre el secreto científico detrás de este fenómeno visual único...",
                height=100,
                help="Deja vacío para que la IA genere la descripción automáticamente"
            )
            
            custom_tags = st.text_input(
                "🏷️ Hashtags (Separados por coma o espacio)",
                value=st.session_state.get('custom_tags', ''),
                placeholder="Ej: #viral #shorts #curiosidades #ciencia",
                help="Deja vacío para que la IA genere los hashtags automáticamente"
            )
            
            # Guardar en session_state
            st.session_state.custom_title = custom_title.strip() if custom_title else None
            st.session_state.custom_desc = custom_desc.strip() if custom_desc else None
            st.session_state.custom_tags = custom_tags.strip() if custom_tags else None
            
            if st.session_state.custom_title or st.session_state.custom_desc or st.session_state.custom_tags:
                st.info("✅ Se usarán tus valores personalizados. Los campos vacíos se generarán con IA.")
        
        generate_btn = st.button("🔥 GENERAR VIDEO COMPLETO", type="primary", use_container_width=True)
    
    with col2:
        st.info("💡 **Modo Automático**\n\nEste modo ejecuta todo el proceso:\n1. Genera el guion\n2. Crea el audio\n3. Descarga videos\n4. Renderiza el video final")
        
        if st.session_state.current_video and Path(st.session_state.current_video).exists():
            st.success("✅ Último video generado disponible")
            st.caption(f"📹 {Path(st.session_state.current_video).name}")
    
    # Función para verificar si estamos en horario activo (mejorada)
    def esta_en_horario_activo() -> bool:
        """Verifica si la hora actual está dentro del horario activo configurado."""
        if not st.session_state.get('horario_activo', False):
            return True  # Sin restricción de horario
        
        hora_actual = datetime.now().hour
        horario_trabajo = st.session_state.get('horario_trabajo', [9, 22])
        
        if not horario_trabajo or len(horario_trabajo) < 2:
            # Fallback a valores por defecto
            hora_inicio = st.session_state.get('hora_inicio_bucle', dt_time(9, 0))
            hora_fin = st.session_state.get('hora_fin_bucle', dt_time(22, 0))
            hora_inicio_h = hora_inicio.hour
            hora_fin_h = hora_fin.hour
        else:
            hora_inicio_h = horario_trabajo[0]
            hora_fin_h = horario_trabajo[1]
        
        if hora_inicio_h <= hora_fin_h:
            # Horario normal (ej: 9 a 22)
            return hora_inicio_h <= hora_actual < hora_fin_h
        else:
            # Horario que cruza medianoche (ej: 22 a 9)
            return hora_actual >= hora_inicio_h or hora_actual < hora_fin_h
    
    # Función para verificar modo sueño (Humanizer)
    def esta_en_modo_sueno() -> bool:
        """Verifica si la hora actual está en el rango de modo sueño (02:00 AM a 07:00 AM)."""
        hora_actual = datetime.now().time()
        hora_sueno_inicio = dt_time(2, 0)  # 02:00 AM
        hora_sueno_fin = dt_time(7, 0)     # 07:00 AM
        
        return hora_sueno_inicio <= hora_actual <= hora_sueno_fin
    
    # Función para randomizar intervalo (Humanizer mejorado)
    def randomizar_intervalo(intervalo_minutos: int) -> int:
        """
        Randomiza el intervalo de espera para simular comportamiento humano.
        Usa variación de -20% a +20% del intervalo base.
        
        Args:
            intervalo_minutos: Intervalo base en minutos
        
        Returns:
            Intervalo randomizado en segundos
        """
        # Randomizar entre -20% y +20% del intervalo base
        variacion_min = max(1, int(intervalo_minutos * 0.8))  # -20%, mínimo 1 minuto
        variacion_max = int(intervalo_minutos * 1.2)  # +20%
        
        intervalo_random = random.randint(variacion_min, variacion_max)
        intervalo_segundos = intervalo_random * 60
        
        variacion_porcentaje = ((intervalo_random - intervalo_minutos) / intervalo_minutos) * 100
        logger.debug(f"Intervalo randomizado: {intervalo_minutos} min → {intervalo_random} min ({variacion_porcentaje:+.1f}%)")
        st.session_state.streamlit_logger.write(f"[BUCLE] Intervalo randomizado: {intervalo_minutos} min → {intervalo_random} min ({variacion_porcentaje:+.1f}%)")
        return intervalo_segundos
    
    # Función para seleccionar tema
    def seleccionar_tema(lista_temas: list, modo: str = "Aleatorio") -> str:
        """Selecciona un tema de la lista según el modo."""
        if not lista_temas:
            return None
        
        if modo == "Aleatorio":
            return random.choice(lista_temas)
        else:  # Secuencial
            indice_actual = st.session_state.get('indice_tema_secuencial', 0)
            tema = lista_temas[indice_actual % len(lista_temas)]
            st.session_state.indice_tema_secuencial = (indice_actual + 1) % len(lista_temas)
            return tema
    
    # Función para ejecutar una generación con subida
    def ejecutar_generacion_con_subida(topic: str, style: str, duration: float, music_vol: float, custom_prompt: str, subir_yt: bool, subir_tt: bool, youtube_priv: str, tiktok_cookies: str):
        """Ejecuta una generación completa y sube a plataformas si está configurado."""
        try:
            st.session_state.streamlit_logger.write(f"[BUCLE] Iniciando generacion: {topic}")
            
            # Obtener metadatos personalizados desde session_state (pueden ser None)
            custom_title = st.session_state.get('custom_title')
            custom_desc = st.session_state.get('custom_desc')
            custom_tags = st.session_state.get('custom_tags')
            
            # Sanitizar el estilo antes de pasarlo a execute_full_generation
            clean_style = clean_style_name(style)
            
            result = execute_full_generation(
                topic, 
                clean_style, 
                duration, 
                music_vol, 
                custom_prompt,
                progress_callback=None,  # Sin callback de progreso en el bucle
                custom_title=custom_title,
                custom_desc=custom_desc,
                custom_tags=custom_tags
            )
            
            if result:
                video_path = result.get('output_path')
                st.session_state.current_video = video_path
                st.session_state.viral_title = result.get('viral_title')
                st.session_state.viral_hook = result.get('viral_hook')
                st.session_state.streamlit_logger.write(f"[BUCLE] Video generado: {video_path}")
                upload_success = False
                ig_result = result.get('instagram_upload')
                if ig_result is True:
                    st.session_state.streamlit_logger.write("[BUCLE] Instagram: Reel publicado")
                    upload_success = True
                elif ig_result is False:
                    st.session_state.streamlit_logger.write("[BUCLE] Instagram: Error al subir Reel")
                
                # Subir a YouTube
                if subir_yt and UPLOADERS_AVAILABLE and video_path:
                    try:
                        # Retardo aleatorio antes de subir (Humanizer - simula preparación humana)
                        delay_pre_upload = random.uniform(2.0, 5.5)
                        st.session_state.streamlit_logger.write(f"[BUCLE] Preparando subida a YouTube... (esperando {delay_pre_upload:.1f}s)")
                        time.sleep(delay_pre_upload)
                        
                        st.session_state.streamlit_logger.write("[BUCLE] Subiendo a YouTube...")
                        youtube_uploader = YouTubeUploader()
                        
                        # Usar metadatos finales (personalizados o generados por IA)
                        metadata = result.get('metadata', {})
                        title = metadata.get('title_viral') or metadata.get('title_seo') or st.session_state.viral_title or "Metratron Films Production"
                        description = metadata.get('description', '') or st.session_state.viral_hook or ""
                        
                        # Agregar hashtags a la descripción si existen
                        if metadata.get('hashtags'):
                            description = f"{description}\n\n{metadata['hashtags']}".strip()
                        
                        if not description:
                            description = "Produced by Metratron Films"
                        
                        success, message, video_id = youtube_uploader.upload_video(
                            file_path=video_path,
                            title=title,
                            description=description,
                            privacy=youtube_priv
                        )
                        if success:
                            st.session_state.streamlit_logger.write(f"[BUCLE] YouTube: {message}")
                            upload_success = True
                        else:
                            st.session_state.streamlit_logger.write(f"[BUCLE] Error YouTube: {message}")
                    except Exception as e:
                        st.session_state.streamlit_logger.write(f"[BUCLE] Error YouTube: {str(e)}")
                
                # Subir a TikTok
                if subir_tt and UPLOADERS_AVAILABLE and video_path:
                    try:
                        # Retardo aleatorio antes de subir (Humanizer - simula preparación humana)
                        delay_pre_upload = random.uniform(2.0, 5.5)
                        st.session_state.streamlit_logger.write(f"[BUCLE] Preparando subida a TikTok... (esperando {delay_pre_upload:.1f}s)")
                        time.sleep(delay_pre_upload)
                        
                        st.session_state.streamlit_logger.write("[BUCLE] Subiendo a TikTok...")
                        tiktok_uploader = TikTokUploader()
                        
                        # Usar metadatos finales (personalizados o generados por IA)
                        metadata = result.get('metadata', {})
                        title = metadata.get('title_viral') or st.session_state.viral_title or ""
                        desc_meta = metadata.get('description', '') or st.session_state.viral_hook or ""
                        
                        # Construir descripción para TikTok (título + descripción + hashtags)
                        description_parts = []
                        if title:
                            description_parts.append(title)
                        if desc_meta:
                            description_parts.append(desc_meta)
                        if metadata.get('hashtags'):
                            description_parts.append(metadata['hashtags'])
                        
                        description = " ".join(description_parts).strip()
                        if not description:
                            description = "Metratron Films Production"
                        
                        success, message = tiktok_uploader.upload_video(
                            file_path=video_path,
                            description=description,
                            cookies_path=tiktok_cookies
                        )
                        if success:
                            st.session_state.streamlit_logger.write(f"[BUCLE] TikTok: {message}")
                            upload_success = True
                        else:
                            st.session_state.streamlit_logger.write(f"[BUCLE] Error TikTok: {message}")
                    except Exception as e:
                        st.session_state.streamlit_logger.write(f"[BUCLE] Error TikTok: {str(e)}")
                
                upload_state = "Subido" if upload_success else "Solo Render"
                profile_name = st.session_state.get("active_profile", "Configuración Actual")
                analytics_manager.log_generation(profile_name, topic, duration, upload_state)
                
                freed_mb = disk_cleaner.clean_temp_folder(0)
                if freed_mb > 0:
                    st.session_state.streamlit_logger.write(f"[BUCLE] Limpieza automática: {freed_mb} MB liberados.")
                
                return True
            else:
                st.session_state.streamlit_logger.write("[BUCLE] Error: No se genero video")
                return False
                
        except Exception as e:
            st.session_state.streamlit_logger.write(f"[BUCLE] Error en generacion: {str(e)}")
            return False
    
    # Función del modo de render continuo (se ejecuta en thread separado)
    def bucle_infinito():
        """Función principal del modo de render continuo. Se ejecuta en un thread separado."""
        # Mostrar banner del sistema de producción
        try:
            from src.console_ui import Console
            Console.print_cronos_banner()
        except ImportError:
            pass  # Si rich no está instalado, continuar sin el banner
        
        st.session_state.bucle_en_ejecucion = True
        st.session_state.detener_bucle = False
        
        # Obtener y sanitizar todas las variables del session_state (evita variables no definidas)
        selected_style_raw = st.session_state.get('selected_style_code', 'CURIOSIDADES')
        style = clean_style_name(selected_style_raw)  # Sanitizar nombre del estilo (quita emojis)
        duration = st.session_state.get('duration_minutes', 1.0)
        music_vol = st.session_state.get('music_volume', 0.1)
        custom_prompt = st.session_state.get('custom_style_prompt', '').strip()
        intervalo_base_minutos = st.session_state.get('intervalo_bucle', 120)  # En minutos
        subir_yt = st.session_state.get('subir_youtube', False)
        subir_tt = st.session_state.get('subir_tiktok', False)
        youtube_priv = st.session_state.get('youtube_privacy', 'private')
        tiktok_cookies = st.session_state.get('tiktok_cookies', 'tiktok_cookies.txt')
        
        temas_lista = st.session_state.get('temas_lista_procesada', [])
        modo_seleccion = st.session_state.get('modo_seleccion_temas', 'Aleatorio')
        
        iteracion = 0
        
        while not st.session_state.get('detener_bucle', False):
            iteracion += 1
            st.session_state.streamlit_logger.write(f"[BUCLE] Iteracion {iteracion} iniciada")
            
            # Verificar modo sueño (Humanizer)
            if esta_en_modo_sueno():
                hora_actual = datetime.now().time()
                st.session_state.streamlit_logger.write(f"😴 Modo Sueño Activado (Humanizando comportamiento) - Hora: {hora_actual}")
                # Esperar 30 minutos antes de verificar de nuevo
                for _ in range(1800):  # 30 minutos en segundos
                    if st.session_state.get('detener_bucle', False):
                        break
                    time.sleep(1)
                continue
            
            # Verificar horario activo
            if not esta_en_horario_activo():
                hora_actual = datetime.now()
                hora_actual_str = hora_actual.strftime("%H:%M")
                st.session_state.streamlit_logger.write(f"😴 Modo Sueño Activo. Esperando amanecer... (Hora actual: {hora_actual_str})")
                
                # Calcular cuándo será el próximo horario de trabajo
                horario_trabajo = st.session_state.get('horario_trabajo', [9, 22])
                hora_inicio_h = horario_trabajo[0] if horario_trabajo else 9
                
                # Calcular próxima hora de inicio
                if hora_actual.hour < hora_inicio_h:
                    # Aún no ha llegado la hora de inicio hoy
                    proxima_hora = hora_actual.replace(hour=hora_inicio_h, minute=0, second=0, microsecond=0)
                else:
                    # Ya pasó la hora de inicio, será mañana
                    proxima_hora = (hora_actual + timedelta(days=1)).replace(hour=hora_inicio_h, minute=0, second=0, microsecond=0)
                
                tiempo_espera_sueno = (proxima_hora - hora_actual).total_seconds()
                
                # Esperar en modo sueño, actualizando cada minuto
                while tiempo_espera_sueno > 0 and not st.session_state.get('detener_bucle', False):
                    horas_restantes = int(tiempo_espera_sueno // 3600)
                    minutos_restantes = int((tiempo_espera_sueno % 3600) // 60)
                    
                    # Actualizar cada 60 segundos
                    if int(tiempo_espera_sueno) % 60 == 0:
                        st.session_state.streamlit_logger.write(
                            f"😴 Modo Sueño: Despertando en {horas_restantes:02d}:{minutos_restantes:02d} (Próximo trabajo: {proxima_hora.strftime('%H:%M')})"
                        )
                        st.session_state.tiempo_proxima_generacion = proxima_hora
                    
                    time.sleep(1)
                    tiempo_espera_sueno -= 1
                
                if st.session_state.get('detener_bucle', False):
                    break
                continue
            
            # Seleccionar tema
            if temas_lista:
                tema_actual = seleccionar_tema(temas_lista, modo_seleccion)
            else:
                tema_actual = topic if topic else "Tema generico"
            
            if not tema_actual:
                st.session_state.streamlit_logger.write("[BUCLE] No hay temas disponibles. Deteniendo bucle.")
                break
            
            st.session_state.streamlit_logger.write(f"[BUCLE] Tema seleccionado: {tema_actual}")
            
            # Ejecutar generación
            try:
                exito = ejecutar_generacion_con_subida(
                    tema_actual, style, duration, music_vol, custom_prompt,
                    subir_yt, subir_tt, youtube_priv, tiktok_cookies
                )
                
                if exito:
                    st.session_state.streamlit_logger.write(f"[BUCLE] Iteracion {iteracion} completada exitosamente")
                else:
                    st.session_state.streamlit_logger.write(f"[BUCLE] Iteracion {iteracion} fallo")
            except Exception as e:
                st.session_state.streamlit_logger.write(f"[BUCLE] Error en iteracion {iteracion}: {str(e)}")
            
            # Randomizar intervalo para comportamiento humano (Humanizer)
            intervalo_randomizado = randomizar_intervalo(intervalo_base_minutos)
            intervalo_minutos_random = intervalo_randomizado // 60
            
            # Calcular tiempo de próxima generación
            tiempo_proxima = datetime.now() + timedelta(seconds=intervalo_randomizado)
            st.session_state.tiempo_proxima_generacion = tiempo_proxima
            
            # Esperar antes de la siguiente iteración con cuenta regresiva visual
            st.session_state.streamlit_logger.write(f"[BUCLE] Esperando {intervalo_minutos_random} minutos (randomizado de {intervalo_base_minutos} min) antes de la siguiente generacion...")
            
            tiempo_espera = intervalo_randomizado
            tiempo_inicio_espera = datetime.now()
            
            while tiempo_espera > 0 and not st.session_state.get('detener_bucle', False):
                # Verificar horario activo durante la espera
                if not esta_en_horario_activo():
                    hora_actual = datetime.now()
                    st.session_state.streamlit_logger.write(f"😴 Modo Sueño Activado durante espera - Hora: {hora_actual.strftime('%H:%M')}")
                    # Entrar en modo sueño hasta el próximo horario de trabajo
                    horario_trabajo = st.session_state.get('horario_trabajo', [9, 22])
                    hora_inicio_h = horario_trabajo[0] if horario_trabajo else 9
                    
                    if hora_actual.hour < hora_inicio_h:
                        proxima_hora = hora_actual.replace(hour=hora_inicio_h, minute=0, second=0, microsecond=0)
                    else:
                        proxima_hora = (hora_actual + timedelta(days=1)).replace(hour=hora_inicio_h, minute=0, second=0, microsecond=0)
                    
                    tiempo_espera_sueno = (proxima_hora - hora_actual).total_seconds()
                    
                    # Esperar en modo sueño
                    while tiempo_espera_sueno > 0 and not st.session_state.get('detener_bucle', False):
                        if int(tiempo_espera_sueno) % 60 == 0:
                            horas = int(tiempo_espera_sueno // 3600)
                            minutos = int((tiempo_espera_sueno % 3600) // 60)
                            st.session_state.streamlit_logger.write(f"😴 Modo Sueño: Despertando en {horas:02d}:{minutos:02d}")
                            st.session_state.tiempo_proxima_generacion = proxima_hora
                        time.sleep(1)
                        tiempo_espera_sueno -= 1
                    
                    if st.session_state.get('detener_bucle', False):
                        break
                    # Recalcular tiempo de espera restante después del modo sueño
                    tiempo_espera = max(0, intervalo_randomizado - (datetime.now() - tiempo_inicio_espera).total_seconds())
                
                # Actualizar cuenta regresiva cada segundo
                tiempo_restante = datetime.now() + timedelta(seconds=tiempo_espera)
                st.session_state.tiempo_proxima_generacion = tiempo_restante
                
                # Log cada minuto para no saturar
                if int(tiempo_espera) % 60 == 0:
                    horas_restantes = int(tiempo_espera // 3600)
                    minutos_restantes = int((tiempo_espera % 3600) // 60)
                    if horas_restantes > 0:
                        st.session_state.streamlit_logger.write(f"⏳ Próximo video en {horas_restantes:02d}:{minutos_restantes:02d}")
                    else:
                        st.session_state.streamlit_logger.write(f"⏳ Próximo video en {minutos_restantes:02d} minutos")
                
                time.sleep(1)
                tiempo_espera -= 1
        
        st.session_state.bucle_en_ejecucion = False
        st.session_state.streamlit_logger.write("[BUCLE] Bucle detenido")
    
    # Función para ejecutar generación completa
    def execute_full_generation(topic: str, style: str, duration: float, music_vol: float, custom_prompt: str = "", progress_callback=None, custom_title: Optional[str] = None, custom_desc: Optional[str] = None, custom_tags: Optional[str] = None):
        """Wrapper síncrono para generar video completo.
        
        Args:
            progress_callback: Función(opcional) que recibe (progress: float, message: str)
                - progress: Progreso de 0.0 a 1.0
                - message: Mensaje de estado actual
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Función helper para reportar progreso
        def report_progress(progress: float, message: str):
            """Reporta progreso tanto al callback como al logger."""
            if progress_callback:
                try:
                    progress_callback(progress, message)
                except Exception as e:
                    logger.warning(f"Error en callback de progreso: {e}")
            st.session_state.streamlit_logger.write(f"[PROGRESO {progress*100:.0f}%] {message}")
        
        try:
            # Iniciar generación
            report_progress(0.0, "Iniciando generación de video...")
            # RunwayML siempre deshabilitado - Solo usar Stock (Pexels/Pixabay) y DALL-E 3
            use_runway = False
            
            custom_style_prompt_sidebar = st.session_state.get('custom_style_prompt', '').strip()
            style_label_sidebar = st.session_state.get('selected_style_label', selected_style_label)
            
            voice_override = st.session_state.get('voice_override')
            subir_instagram = st.session_state.get('subir_instagram', False)
            ig_username = st.session_state.get('instagram_username', "").strip()
            ig_password = st.session_state.get('instagram_password', "")
            hashtags_text = st.session_state.get('instagram_hashtags', "")
            instagram_hashtags = parse_hashtags_from_text(hashtags_text)
            if instagram_hashtags:
                st.session_state.default_hashtags = instagram_hashtags
            instagram_credentials = None
            if subir_instagram:
                if ig_username and ig_password:
                    instagram_credentials = {
                        "username": ig_username,
                        "password": ig_password,
                        "hashtags": instagram_hashtags
                    }
                else:
                    st.warning("Completa usuario y contraseña de Instagram para subir Reels.")
                    subir_instagram = False
            
            bot = AutoViralBot()
            # Sanitizar el estilo antes de usarlo (quitar emojis y normalizar)
            clean_style = clean_style_name(style)
            style_config = STYLES.get(clean_style, STYLES["CURIOSIDADES"])
            style_prompt = style_config.get("style_prompt", "")
            
            if clean_style == "CUSTOM" and custom_style_prompt_sidebar:
                style_prompt += f"\n\nESTILO PERSONALIZADO DEFINIDO POR EL USUARIO:\n{custom_style_prompt_sidebar}"
            
            if custom_prompt:
                style_prompt += f"\n\nINSTRUCCIONES ADICIONALES DEL USUARIO:\n{custom_prompt}"
            
            # Obtener configuración de subtítulos desde session_state
            use_subtitles = st.session_state.get('use_subtitles', True)
            
            # Obtener configuración de watermark desde session_state
            watermark_text = st.session_state.get('watermark_text', None)
            watermark_position = st.session_state.get('watermark_position', 'bottom-right')
            
            # Obtener configuración de color grading desde session_state
            enable_color_grading = st.session_state.get('enable_color_grading', False)

            use_crossfade_transitions = st.session_state.get('use_crossfade_transitions', False)
            
            # Obtener use_news_mode del session_state ANTES de usarlo (evita UnboundLocalError)
            use_news_mode = st.session_state.get('use_news_mode', False)
            
            # Crear callback wrapper para pasar a generate_video
            def progress_wrapper(progress: float, message: str):
                """Wrapper que recibe progreso en formato 0.0-1.0 y lo reporta."""
                # El progreso ya viene en formato 0.0-1.0 desde main.py
                report_progress(progress, message)
            
            report_progress(0.1, "Configurando bot...")
            
            # ============================================================
            # MODO NOTICIAS: Buscar noticias reales si está activado
            # ============================================================
            news_context = None
            if use_news_mode and topic:
                try:
                    report_progress(0.15, "🔍 Buscando noticias recientes en Internet...")
                    from src.news_hunter import NewsHunter
                    
                    news_hunter = NewsHunter()
                    news_context = news_hunter.get_trends(topic=topic, max_results=3)
                    
                    if news_context and news_context.strip():
                        logger.success(f"✅ Noticias encontradas sobre '{topic}'")
                        report_progress(0.2, "✅ Noticias encontradas")
                    else:
                        logger.warning(f"⚠️ No se encontraron noticias sobre '{topic}'. Continuando sin modo noticias.")
                        report_progress(0.2, "⚠️ No se encontraron noticias. Continuando sin modo noticias.")
                        use_news_mode = False  # Desactivar modo noticias si no hay resultados
                        news_context = None
                except Exception as e:
                    logger.error(f"❌ Error buscando noticias: {e}")
                    logger.warning("⚠️ Continuando sin modo noticias debido a error.")
                    use_news_mode = False
                    news_context = None
            
            result = loop.run_until_complete(
                bot.generate_video(
                    topic=topic,
                    duration_minutes=duration,
                    music_volume=music_vol,
                    style_prompt=style_prompt,
                    use_subtitles=use_subtitles,
                    upload_instagram=subir_instagram,
                    instagram_credentials=instagram_credentials,
                    instagram_session_path=str(IG_SESSION_FILE),
                    watermark_text=watermark_text,
                    watermark_position=watermark_position,
                    enable_color_grading=enable_color_grading,
                    use_crossfade_transitions=use_crossfade_transitions,
                    progress_callback=progress_wrapper,
                    custom_title=custom_title,
                    custom_desc=custom_desc,
                    custom_tags=custom_tags,
                    use_news_mode=use_news_mode,
                    news_context=news_context
                )
            )
            
            report_progress(1.0, "✅ Generación completada!")
            return result
        finally:
            loop.close()
    
    # Procesar generación completa
    if generate_btn:
        modo_bucle = st.session_state.get('modo_bucle_activo', False)
        
        # Inicializar variables del bucle si no existen
        if 'bucle_en_ejecucion' not in st.session_state:
            st.session_state.bucle_en_ejecucion = False
        if 'detener_bucle' not in st.session_state:
            st.session_state.detener_bucle = False
        if 'indice_tema_secuencial' not in st.session_state:
            st.session_state.indice_tema_secuencial = 0
        
        if modo_bucle:
            # Continuous Render Mode
            if st.session_state.bucle_en_ejecucion:
                st.warning("⚠️ Continuous Render Mode ya está en ejecución. Usa el botón de detener si quieres reiniciarlo.")
            else:
                # Verificar que hay temas
                temas_lista = st.session_state.get('temas_lista_procesada', [])
                if not temas_lista and not topic:
                    st.error("❌ Necesitas temas para el modo continuo. Agrega temas en la lista o escribe uno en 'Tema del Video'.")
                else:
                    st.success("🔄 Iniciando Continuous Render Mode...")
                    st.session_state.streamlit_logger.write("[PRODUCTION] Continuous Render Mode activado - Iniciando generacion continua...")
                    
                    # Iniciar thread del bucle
                    bucle_thread = threading.Thread(target=bucle_infinito, daemon=True)
                    bucle_thread.start()
                    
                    st.info("🔄 Bucle iniciado. El bot generará videos automáticamente. Puedes detenerlo con el botón de emergencia.")
                    time.sleep(1)  # Dar tiempo para que el thread inicie
                    st.rerun()
        else:
            # Modo normal (una sola generación)
            if not topic:
                st.error("❌ ¡Escribe un tema primero!")
            else:
                st.session_state.streamlit_logger.write(f"[FULL AUTO] Iniciando generacion: {topic}")
                
                # Crear contenedor de estado para feedback visual
                status_container = st.container()
                progress_bar = status_container.progress(0)
                status_text = status_container.empty()
                
                # Función callback para actualizar progreso
                def update_progress(progress: float, message: str):
                    """Actualiza la barra de progreso y el mensaje de estado."""
                    progress_bar.progress(progress)
                    status_text.info(f"🔄 {message}")
                
                try:
                    # Obtener metadatos personalizados desde session_state
                    custom_title = st.session_state.get('custom_title')
                    custom_desc = st.session_state.get('custom_desc')
                    custom_tags = st.session_state.get('custom_tags')
                    
                    # Sanitizar el estilo antes de pasarlo (quitar emojis)
                    clean_style = clean_style_name(selected_style)
                    result = execute_full_generation(
                        topic, 
                        clean_style, 
                        duration_minutes, 
                        music_volume, 
                        prompt_custom,
                        progress_callback=update_progress,
                        custom_title=custom_title,
                        custom_desc=custom_desc,
                        custom_tags=custom_tags
                    )
                    
                    if result:
                        video_path = result.get('output_path')
                        st.session_state.current_video = video_path
                        st.session_state.viral_title = result.get('viral_title')
                        st.session_state.viral_hook = result.get('viral_hook')
                        st.session_state.current_thumbnail = result.get('thumbnail_path')
                        st.session_state.current_metadata = result.get('metadata')
                        st.session_state.streamlit_logger.write(f"Video generado: {video_path}")
                        st.success("¡Video Generado con Exito!")
                        
                        # --- PROCESO DE SUBIDA AUTOMÁTICA ---
                        upload_messages = []
                        ig_flag = result.get('instagram_upload')
                        if ig_flag is True:
                            upload_messages.append(("success", "Instagram: Reel publicado"))
                        elif ig_flag is False:
                            upload_messages.append(("error", "Instagram: Falló la subida del Reel"))
                        
                        # Subir a YouTube
                        if subir_youtube and UPLOADERS_AVAILABLE and video_path:
                            try:
                                with st.spinner("Subiendo a YouTube..."):
                                    st.session_state.streamlit_logger.write("Iniciando subida a YouTube...")
                                    
                                    youtube_uploader = YouTubeUploader()
                                    
                                    # Usar metadatos finales (personalizados o generados por IA)
                                    metadata = result.get('metadata', {})
                                    title = metadata.get('title_viral') or metadata.get('title_seo') or st.session_state.viral_title or "Metratron Films Production"
                                    description = metadata.get('description', '') or st.session_state.viral_hook or ""
                                    
                                    # Agregar hashtags a la descripción si existen
                                    if metadata.get('hashtags'):
                                        description = f"{description}\n\n{metadata['hashtags']}".strip()
                                    
                                    if not description:
                                        description = "Produced by Metratron Films"
                                    
                                    success, message, video_id = youtube_uploader.upload_video(
                                        file_path=video_path,
                                        title=title,
                                        description=description,
                                        privacy=youtube_privacy
                                    )
                                    
                                    if success:
                                        upload_messages.append(("success", f"YouTube: {message}"))
                                        st.session_state.streamlit_logger.write(f"YouTube: {message}")
                                    else:
                                        upload_messages.append(("error", f"Error YouTube: {message}"))
                                        st.session_state.streamlit_logger.write(f"Error YouTube: {message}")
                            except Exception as e:
                                error_msg = f"Error al subir a YouTube: {str(e)}"
                                upload_messages.append(("error", error_msg))
                                st.session_state.streamlit_logger.write(error_msg)
                                logger.error(f"Error YouTube upload: {e}")
                        
                        # Subir a TikTok
                        if subir_tiktok and UPLOADERS_AVAILABLE and video_path:
                            try:
                                with st.spinner("Subiendo a TikTok..."):
                                    st.session_state.streamlit_logger.write("Iniciando subida a TikTok...")
                                    
                                    tiktok_uploader = TikTokUploader()
                                    
                                    # Usar metadatos finales (personalizados o generados por IA)
                                    metadata = result.get('metadata', {})
                                    title = metadata.get('title_viral') or st.session_state.viral_title or ""
                                    desc_meta = metadata.get('description', '') or st.session_state.viral_hook or ""
                                    
                                    # Construir descripción para TikTok (título + descripción + hashtags)
                                    description_parts = []
                                    if title:
                                        description_parts.append(title)
                                    if desc_meta:
                                        description_parts.append(desc_meta)
                                    if metadata.get('hashtags'):
                                        description_parts.append(metadata['hashtags'])
                                    
                                    description = " ".join(description_parts).strip()
                                    if not description:
                                        description = "Metratron Films Production"
                                    
                                    success, message = tiktok_uploader.upload_video(
                                        file_path=video_path,
                                        description=description,
                                        cookies_path=tiktok_cookies if subir_tiktok else "tiktok_cookies.txt"
                                    )
                                    
                                    if success:
                                        upload_messages.append(("success", f"TikTok: {message}"))
                                        st.session_state.streamlit_logger.write(f"TikTok: {message}")
                                    else:
                                        upload_messages.append(("error", f"Error TikTok: {message}"))
                                        st.session_state.streamlit_logger.write(f"Error TikTok: {message}")
                            except Exception as e:
                                error_msg = f"Error al subir a TikTok: {str(e)}"
                                upload_messages.append(("error", error_msg))
                                st.session_state.streamlit_logger.write(error_msg)
                                logger.error(f"Error TikTok upload: {e}")
                        
                        # Mostrar mensajes de upload
                        if upload_messages:
                            st.markdown("---")
                            st.subheader("Estado de Subidas")
                            for msg_type, msg_text in upload_messages:
                                if msg_type == "success":
                                    st.success(msg_text)
                                else:
                                    st.error(msg_text)
                        
                        upload_state = "Solo Render"
                        if any(msg_type == "success" for msg_type, _ in upload_messages):
                            upload_state = "Subido"
                        profile_name = st.session_state.get("active_profile", "Configuración Actual")
                        analytics_manager.log_generation(profile_name, topic, duration_minutes, upload_state)
                        
                        st.balloons()
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.session_state.streamlit_logger.write(f"ERROR: {str(e)}")
    
    # Mostrar video y miniatura si existen
    if st.session_state.current_video and Path(st.session_state.current_video).exists():
        st.markdown("---")
        col_video, col_thumb = st.columns([2, 1])
        with col_video:
            st.subheader("🎬 Video Generado")
            st.video(st.session_state.current_video)
            st.caption(f"📹 {st.session_state.current_video}")
        
        thumbnail_path = st.session_state.get("current_thumbnail")
        if thumbnail_path and Path(thumbnail_path).exists():
            with col_thumb:
                st.subheader("🖼️ Miniatura")
                st.image(thumbnail_path, use_column_width=True)
                with open(thumbnail_path, "rb") as thumb_file:
                    st.download_button(
                        "⬇️ Descargar Miniatura",
                        data=thumb_file.read(),
                        file_name=Path(thumbnail_path).name,
                        mime="image/jpeg",
                        use_container_width=True
                    )
        
        # Mostrar metadatos generados
        metadata = st.session_state.get("current_metadata")
        if metadata:
            st.markdown("---")
            st.subheader("📢 Metadatos Generados")
            
            col_meta1, col_meta2 = st.columns(2)
            
            with col_meta1:
                st.markdown("**📌 Título Viral (Clickbait)**")
                title_viral = metadata.get("title_viral", "N/A")
                st.code(title_viral, language=None)
                if st.button("📋 Copiar Título Viral", key="copy_title_viral", use_container_width=True):
                    st.write("✅ Copiado al portapapeles (usa Ctrl+V)")
                    # Nota: Streamlit no tiene acceso directo al portapapeles, pero el usuario puede seleccionar y copiar
                
                st.markdown("**🔍 Título SEO**")
                title_seo = metadata.get("title_seo", "N/A")
                st.code(title_seo, language=None)
                if st.button("📋 Copiar Título SEO", key="copy_title_seo", use_container_width=True):
                    st.write("✅ Copiado al portapapeles (usa Ctrl+V)")
            
            with col_meta2:
                st.markdown("**📝 Descripción**")
                description = metadata.get("description", "N/A")
                st.text_area("", value=description, height=100, key="metadata_description", disabled=True)
                if st.button("📋 Copiar Descripción", key="copy_description", use_container_width=True):
                    st.write("✅ Copiado al portapapeles (usa Ctrl+V)")
            
            st.markdown("**🏷️ Hashtags**")
            hashtags = metadata.get("hashtags", "N/A")
            st.code(hashtags, language=None)
            if st.button("📋 Copiar Hashtags", key="copy_hashtags", use_container_width=True):
                st.write("✅ Copiado al portapapeles (usa Ctrl+V)")

# ============================================================
# TAB 2: SOLO GUION
# ============================================================
with tabs[1]:
    st.header("📝 Generador de Guiones")
    st.caption("Genera solo el guion del video. Puedes editarlo y usarlo en otros modos.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        topic_script = st.text_input(
            "Tema del Video",
            key="topic_script",
            placeholder="Ej: La verdad sobre los gatos negros...",
            help="Describe el tema sobre el cual quieres generar el guion"
        )
        
        prompt_custom_script = st.text_area(
            "Instrucciones Extra (Opcional)",
            key="prompt_script",
            placeholder="Ej: Haz que el gancho sea muy agresivo...",
            help="Instrucciones adicionales para personalizar el guion"
        )
        
        generate_script_btn = st.button("📝 GENERAR GUION", type="primary", use_container_width=True)
    
    with col2:
        st.info("💡 El guion generado se guardará automáticamente y estará disponible en otros modos.")
        
        if st.session_state.generated_script:
            st.success("✅ Guion disponible")
            st.caption(f"📌 Título: {st.session_state.viral_title}")
    
    # Procesar generación de guion
    if generate_script_btn:
        if not topic_script:
            st.error("❌ ¡Escribe un tema primero!")
        else:
            st.session_state.streamlit_logger.write(f"📝 [SOLO GUION] Generando guion: {topic_script}")
            
            try:
                with st.spinner("⚙️ Generando guion con IA..."):
                    custom_style_prompt_sidebar = st.session_state.get('custom_style_prompt', '').strip()
                    voice_override = st.session_state.get('voice_override')
                    bot = AutoViralBot()
                    style_config = STYLES.get(selected_style, STYLES["CURIOSIDADES"])
                    style_prompt = style_config.get("style_prompt", "")
                    
                    if selected_style == "CUSTOM" and custom_style_prompt_sidebar:
                        style_prompt += f"\n\nESTILO PERSONALIZADO DEFINIDO POR EL USUARIO:\n{custom_style_prompt_sidebar}"
                    
                    if prompt_custom_script:
                        style_prompt += f"\n\nINSTRUCCIONES ADICIONALES DEL USUARIO:\n{prompt_custom_script}"
                    
                    script_data = bot.generate_script_only(
                        topic=topic_script,
                        duration_minutes=duration_minutes,
                        style_prompt=style_prompt,
                        custom_prompt=prompt_custom_script if prompt_custom_script else None
                    )
                
                # Guardar en session_state
                st.session_state.generated_script = script_data
                st.session_state.viral_title = script_data.get('viral_title')
                st.session_state.viral_hook = script_data.get('viral_hook_text')
                
                # Crear texto formateado del guion
                script_text = f"TÍTULO VIRAL: {st.session_state.viral_title}\n\n"
                script_text += f"HOOK: {st.session_state.viral_hook}\n\n"
                script_text += "ESCENAS:\n\n"
                for idx, scene in enumerate(script_data.get('scenes', []), 1):
                    script_text += f"--- ESCENA {idx} ---\n"
                    script_text += f"Texto: {scene.get('text', '')}\n"
                    script_text += f"Query Visual: {scene.get('visual_query', '')}\n"
                    script_text += f"Duración estimada: {scene.get('duration_estimate', 0)}s\n\n"
                
                st.session_state.generated_script_text = script_text
                st.session_state.streamlit_logger.write(f"✅ Guion generado exitosamente")
                st.success("✅ ¡Guion Generado!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.session_state.streamlit_logger.write(f"❌ ERROR: {str(e)}")
    
    # Mostrar guion generado
    if st.session_state.generated_script_text:
        st.markdown("---")
        st.subheader("📄 Guion Generado")
        
        # Mostrar título y hook
        if st.session_state.viral_title:
            st.header(f"📌 {st.session_state.viral_title}")
        if st.session_state.viral_hook:
            st.subheader(f"🎣 {st.session_state.viral_hook}")
        
        # Editor de texto para el guion
        edited_script = st.text_area(
            "Guion (editable)",
            value=st.session_state.generated_script_text,
            height=400,
            help="Puedes editar el guion aquí. Copia y pégalo en otros modos si lo necesitas."
        )
        
        # Botón para copiar
        st.caption("💡 Este guion está disponible automáticamente en el modo 'Solo Audio'")

# ============================================================
# TAB 3: SOLO AUDIO
# ============================================================
with tabs[2]:
    st.header("🎙️ Generador de Audio (Texto a Voz)")
    st.caption("Convierte texto a audio usando Edge-TTS. Puedes usar el guion generado o pegar tu propio texto.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Opción: usar guion generado o texto manual
        use_generated_script = st.checkbox(
            "Usar guion generado en 'Solo Guion'",
            value=st.session_state.generated_script_text is not None,
            disabled=st.session_state.generated_script_text is None,
            help="Si está marcado, usará el primer texto del guion generado"
        )
        
        if use_generated_script and st.session_state.generated_script:
            # Extraer texto del primer escena o todas las escenas
            scenes_text = ""
            for scene in st.session_state.generated_script.get('scenes', []):
                scenes_text += scene.get('text', '') + " "
            text_input_audio = st.text_area(
                "Texto a convertir a audio",
                value=scenes_text.strip(),
                height=200,
                help="Texto que se convertirá a audio"
            )
        else:
            text_input_audio = st.text_area(
                "Texto a convertir a audio",
                placeholder="Escribe o pega aquí el texto que quieres convertir a voz...",
                height=200,
                help="Texto que se convertirá a audio"
            )
        
        # Selector de voz
        style_info_audio = STYLES.get(selected_style, STYLES["CURIOSIDADES"])
        default_voice = style_info_audio.get('voice', 'es-MX-DaliaNeural')
        
        # Lista de voces disponibles (puedes expandir esto)
        voice_options = {
            "🚫 Sin Narración (Solo Música)": "NO_VOICE",
            "Dalia (Mexicana)": "es-MX-DaliaNeural",
            "Jorge (Mexicano)": "es-MX-JorgeNeural",
            "Tomas (Argentino)": "es-AR-TomasNeural",
            "Elvira (Española)": "es-ES-ElviraNeural",
            "Alvaro (Español)": "es-ES-AlvaroNeural"
        }
        
        selected_voice_name = st.selectbox(
            "🎙️ Seleccionar Voz",
            list(voice_options.keys()),
            index=list(voice_options.values()).index(default_voice) if default_voice in voice_options.values() else 0,
            help="Selecciona la voz para la síntesis"
        )
        
        selected_voice_id = voice_options[selected_voice_name]
        st.session_state.voice_override = selected_voice_id
        st.session_state.voice_override_label = selected_voice_name

        with st.expander("🔊 Probador de Voces", expanded=False):
            default_preview_text = "Hola, soy la voz de tu próximo video viral."
            preview_text = st.text_input(
                "Texto de prueba",
                value=st.session_state.get("voice_preview_text", default_preview_text),
                key="voice_preview_text_input",
                help="Escribe una frase corta para escuchar cómo suena la voz actual."
            )
            st.session_state.voice_preview_text = preview_text
            
            preview_btn = st.button("▶️ Escuchar Voz", key="voice_preview_button")
            if preview_btn:
                if selected_voice_id == "NO_VOICE":
                    st.warning("Selecciona una voz antes de reproducir la vista previa.")
                else:
                    clean_text = preview_text.strip() or default_preview_text
                    try:
                        with st.spinner("🎧 Generando preview de voz..."):
                            preview_path = generate_voice_preview(clean_text, selected_voice_id)
                    except Exception as e:
                        preview_path = None
                        logger.error(f"❌ Error al generar preview de voz: {e}")
                    
                    if preview_path and Path(preview_path).exists():
                        st.session_state.voice_preview_path = preview_path
                        st.success("✅ Vista previa lista. Reprodúcela abajo.")
                    else:
                        st.error("❌ No se pudo generar la vista previa. Intenta nuevamente.")
            
            stored_preview = st.session_state.get("voice_preview_path")
            if stored_preview and Path(stored_preview).exists() and selected_voice_id != "NO_VOICE":
                st.audio(stored_preview)
                st.caption("🔁 Última vista previa generada")
        
        generate_audio_btn = st.button("🎙️ GENERAR AUDIO", type="primary", use_container_width=True)
    
    with col2:
        st.info("💡 **Solo Audio**\n\nConvierte texto a voz usando Edge-TTS. El audio generado estará disponible para usar en el modo 'Solo Video'.")
        
        if st.session_state.generated_audio_path and Path(st.session_state.generated_audio_path).exists():
            st.success("✅ Audio disponible")
            st.caption(f"🎵 {Path(st.session_state.generated_audio_path).name}")
    
    # Función para ejecutar generación de audio
    async def execute_audio_generation(text: str, voice: str):
        """Genera audio de forma asíncrona."""
        custom_style_prompt_sidebar = st.session_state.get('custom_style_prompt', '').strip()
        voice_override = st.session_state.get('voice_override')
        bot = AutoViralBot()
        audio_path = await bot.generate_audio_only(text=text, voice=voice)
        return audio_path
    
    def execute_audio_sync(text: str, voice: str):
        """Wrapper síncrono."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(execute_audio_generation(text, voice))
            return result
        finally:
            loop.close()
    
    # Procesar generación de audio
    if generate_audio_btn:
        if not text_input_audio or not text_input_audio.strip():
            st.error("❌ ¡Escribe un texto primero!")
        elif selected_voice_id == "NO_VOICE":
            st.warning("⚠️ El modo 'Sin Narración' no genera audio TTS. Selecciona una voz para continuar.")
        else:
            st.session_state.streamlit_logger.write(f"🎙️ [SOLO AUDIO] Generando audio con voz: {selected_voice_name}")
            
            try:
                with st.spinner("⚙️ Generando audio..."):
                    audio_path = execute_audio_sync(text_input_audio.strip(), selected_voice_id)
                
                st.session_state.generated_audio_path = audio_path
                st.session_state.streamlit_logger.write(f"✅ Audio generado: {audio_path}")
                st.success("✅ ¡Audio Generado!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.session_state.streamlit_logger.write(f"❌ ERROR: {str(e)}")
    
    # Mostrar audio generado
    if st.session_state.generated_audio_path and Path(st.session_state.generated_audio_path).exists():
        st.markdown("---")
        st.subheader("🎵 Audio Generado")
        st.audio(st.session_state.generated_audio_path)
        st.caption(f"📁 Ruta: `{st.session_state.generated_audio_path}`")
        st.info("💡 Este audio está disponible automáticamente en el modo 'Solo Video'")

# ============================================================
# TAB 4: SOLO VIDEO
# ============================================================
with tabs[3]:
    st.header("🎬 Renderizador de Video")
    st.caption("Renderiza un video final usando un guion y audio. Puedes usar los generados previamente o proporcionar los tuyos.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Opción: usar guion generado o proporcionar uno
        use_generated_script_video = st.checkbox(
            "Usar guion generado en 'Solo Guion'",
            value=st.session_state.generated_script is not None,
            disabled=st.session_state.generated_script is None,
            help="Si está marcado, usará el guion generado previamente"
        )
        
        if use_generated_script_video and st.session_state.generated_script:
            st.info(f"✅ Usando guion generado: {st.session_state.viral_title}")
            script_data_video = st.session_state.generated_script
        else:
            st.warning("⚠️ Debes proporcionar un guion en formato JSON o usar el modo 'Solo Guion' primero")
            script_json = st.text_area(
                "Guion en formato JSON (o deja vacío para usar guion generado)",
                placeholder='{"scenes": [{"text": "...", "visual_query": "..."}]}',
                height=150,
                help="Pega aquí el guion en formato JSON"
            )
            if script_json.strip():
                try:
                    script_data_video = json.loads(script_json)
                except:
                    script_data_video = None
                    st.error("❌ JSON inválido")
            else:
                script_data_video = None
        
        # Opción: usar audio generado o proporcionar ruta
        use_generated_audio_video = st.checkbox(
            "Usar audio generado en 'Solo Audio'",
            value=st.session_state.generated_audio_path is not None,
            disabled=st.session_state.generated_audio_path is None,
            help="Si está marcado, usará el audio generado previamente"
        )
        
        audio_path_video = None
        if use_generated_audio_video and st.session_state.generated_audio_path:
            audio_path_video = st.session_state.generated_audio_path
            st.info(f"✅ Usando audio: {Path(audio_path_video).name}")
        else:
            audio_path_input = st.text_input(
                "Ruta del archivo de audio (opcional)",
                placeholder="assets/temp/audio_0.mp3",
                help="Ruta al archivo de audio. Si no se proporciona, se generará automáticamente."
            )
            if audio_path_input and Path(audio_path_input).exists():
                audio_path_video = audio_path_input
            elif audio_path_input:
                st.warning(f"⚠️ Archivo no encontrado: {audio_path_input}")
        
        render_video_btn = st.button("🎬 RENDERIZAR VIDEO", type="primary", use_container_width=True)
    
    with col2:
        st.info("💡 **Solo Video**\n\nRenderiza el video final usando:\n- Guion (generado o proporcionado)\n- Audio (generado o proporcionado)\n- Videos de stock de Pexels")
        
        if st.session_state.current_video and Path(st.session_state.current_video).exists():
            st.success("✅ Último video renderizado disponible")
    
    # Función para ejecutar renderizado
    async def execute_video_render_async(script_data: dict, audio_path: str = None):
        """Renderiza video de forma asíncrona."""
        custom_style_prompt_sidebar = st.session_state.get('custom_style_prompt', '').strip()
        voice_override = st.session_state.get('voice_override')
        bot = AutoViralBot()
        # Obtener configuración de subtítulos, watermark y color grading desde session_state
        use_subtitles = st.session_state.get('use_subtitles', True)
        watermark_text = st.session_state.get('watermark_text', None)
        watermark_position = st.session_state.get('watermark_position', 'bottom-right')
        enable_color_grading = st.session_state.get('enable_color_grading', False)
        
        video_path = await bot.render_video_only(
            script_data=script_data,
            audio_path=audio_path,
            background_music=None,
            music_volume=music_volume,
            use_subtitles=use_subtitles,
            watermark_text=watermark_text,
            watermark_position=watermark_position,
            enable_color_grading=enable_color_grading
        )
        return video_path
    
    def execute_video_render(script_data: dict, audio_path: str = None):
        """Wrapper síncrono para renderizar video."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(execute_video_render_async(script_data, audio_path))
            return result
        finally:
            loop.close()
    
    # Procesar renderizado
    if render_video_btn:
        if not script_data_video:
            st.error("❌ ¡Necesitas proporcionar un guion! Usa el modo 'Solo Guion' primero o pega un JSON válido.")
        else:
            st.session_state.streamlit_logger.write(f"🎬 [SOLO VIDEO] Renderizando video...")
            
            try:
                with st.spinner("⚙️ Renderizando video (esto puede tardar varios minutos)..."):
                    video_path = execute_video_render(script_data_video, audio_path_video)
                
                st.session_state.current_video = video_path
                st.session_state.streamlit_logger.write(f"✅ Video renderizado: {video_path}")
                st.success("✅ ¡Video Renderizado!")
                st.balloons()
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.session_state.streamlit_logger.write(f"❌ ERROR: {str(e)}")
    
    # Mostrar video renderizado
    if st.session_state.current_video and Path(st.session_state.current_video).exists():
        st.markdown("---")
        st.subheader("🎬 Video Renderizado")
        st.video(st.session_state.current_video)
        st.caption(f"📹 Ruta: `{st.session_state.current_video}`")

# ============================================================
# TAB 5: MEZCLADOR MANUAL
# ============================================================
with tabs[4]:
    st.header("🎨 Mezclador Manual")
    st.caption("Sube tu propio video y audio, y genera subtítulos karaoke automáticamente desde el texto del guion.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # File uploaders
        uploaded_videos = st.file_uploader(
            "📹 Sube tus clips de video o imágenes (Se unirán en orden)",
            type=['mp4', 'avi', 'mov', 'mkv', 'jpg', 'jpeg', 'png', 'webp'],
            accept_multiple_files=True,
            help="Sube uno o más videos/imágenes. Se concatenarán en el orden que los subas. Las imágenes se animarán automáticamente con efecto Ken Burns."
        )
        
        uploaded_audio = st.file_uploader(
            "🎵 Subir Audio",
            type=['mp3', 'wav', 'm4a'],
            help="Sube el archivo de audio con la narración"
        )
        
        # Checkbox para eliminar marca de agua
        remove_watermark = st.checkbox(
            "✂️ Eliminar Bordes/Marca de Agua (Zoom 15%)",
            value=False,
            help="Aplica un zoom del 15% y recorte central para eliminar marcas de agua y bordes. Útil para videos de stock con logos."
        )
        
        # Checkbox para silenciar audio original del video
        mute_original_video = st.checkbox(
            "🔇 Silenciar audio original del video (Recomendado)",
            value=True,
            help="Elimina el audio original del video de stock. Esto evita ruido de fondo y conflictos con tu narración y música."
        )
        
        # Text area para guion
        script_text_manual = st.text_area(
            "📝 Guion para Subtítulos (Texto)",
            placeholder="Pega aquí el texto completo del guion. Los subtítulos karaoke se generarán automáticamente desde el audio...",
            height=200,
            help="El texto del guion se usará para generar subtítulos karaoke. Si no proporcionas texto, se intentará transcribir desde el audio."
        )
        
        st.info("💡 **Nota:** Si no proporcionas texto, el sistema intentará transcribir el audio automáticamente usando Whisper.")
        
        render_manual_btn = st.button("🎬 RENDERIZAR MEZCLA", type="primary", use_container_width=True)
    
    with col2:
        st.info("💡 **Mezclador Manual**\n\nEste modo te permite:\n1. Subir tu propio video de fondo\n2. Subir tu propio audio\n3. Generar subtítulos karaoke automáticamente\n4. Renderizar el video final")
        
        if uploaded_videos:
            video_count = sum(1 for v in uploaded_videos if Path(v.name).suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv'])
            image_count = len(uploaded_videos) - video_count
            if video_count > 0 and image_count > 0:
                st.success(f"✅ {len(uploaded_videos)} archivo(s) cargado(s) ({video_count} video(s), {image_count} imagen(es))")
            elif video_count > 0:
                st.success(f"✅ {video_count} clip(s) de video cargado(s)")
            else:
                st.success(f"✅ {image_count} imagen(es) cargada(s) (se animarán automáticamente)")
            for idx, video in enumerate(uploaded_videos, 1):
                file_type = "📸" if Path(video.name).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp'] else "🎬"
                st.caption(f"   {idx}. {file_type} {video.name} ({(video.size / (1024*1024)):.2f} MB)")
        
        if uploaded_audio:
            st.success(f"✅ Audio cargado: {uploaded_audio.name}")
            st.caption(f"Tamaño: {uploaded_audio.size / (1024*1024):.2f} MB")
    
    # Función para procesar mezcla manual
    def process_manual_mix(video_files, audio_file, script_text: str = None, remove_watermark: bool = False, mute_original_video: bool = True):
        """
        Procesa la mezcla manual de múltiples clips de video/imágenes y audio con subtítulos karaoke.
        
        Args:
            video_files: Lista de archivos de video/imágenes subidos (se concatenarán en orden)
            audio_file: Archivo de audio subido
            script_text: Texto opcional para subtítulos estáticos
            remove_watermark: Si True, aplica zoom 15% y crop para eliminar marcas de agua
            mute_original_video: Si True, silencia el audio original del video de stock
        """
        from src.video_editor import VideoEditor, concatenate_videoclips, TARGET_WIDTH, TARGET_HEIGHT, ImageClip
        
        BASE_DIR = Path(".")
        temp_dir = BASE_DIR / "assets" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        video_clips = []
        audio_clip = None
        
        try:
            # --- PASO 1: Guardar y procesar múltiples videos ---
            logger.info(f"Procesando {len(video_files)} clip(s) de video...")
            
            editor = VideoEditor()
            
            # Obtener dimensiones objetivo desde session_state o usar valores por defecto
            target_w = st.session_state.get('target_width', TARGET_WIDTH)
            target_h = st.session_state.get('target_height', TARGET_HEIGHT)
            
            for idx, video_file in enumerate(video_files):
                # Detectar si es imagen o video por extensión
                file_ext = Path(video_file.name).suffix.lower()
                is_image = file_ext in ['.jpg', '.jpeg', '.png', '.webp']
                
                # Guardar archivo con extensión original
                if is_image:
                    file_path = temp_dir / f"manual_image_{idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
                else:
                    file_path = temp_dir / f"manual_video_{idx}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                
                with open(file_path, "wb") as f:
                    f.write(video_file.getbuffer())
                
                logger.info(f"Cargando clip {idx + 1}/{len(video_files)}: {video_file.name} ({'Imagen' if is_image else 'Video'})")
                
                # Procesar según tipo
                if is_image:
                    # Es imagen: crear clip animado con efecto Ken Burns
                    image_duration = 5.0  # Duración por defecto de 5 segundos por imagen
                    logger.info(f"📸 Creando clip animado desde imagen con Ken Burns ({image_duration}s)...")
                    clip = editor.create_dynamic_image_clip(
                        image_path=str(file_path),
                        duration=image_duration,
                        target_width=target_w,
                        target_height=target_h,
                        zoom_effect="in"  # Zoom in suave
                    )
                else:
                    # Es video: cargar normalmente
                    clip = VideoFileClip(str(file_path))
                    
                    # Silenciar audio original del video si está habilitado (para evitar ruido de stock)
                    if mute_original_video:
                        logger.info(f"🔇 Silenciando audio original del video para clip {idx + 1}...")
                        clip = clip.without_audio()
                    
                    # Redimensionar al formato objetivo
                    clip = editor._resize_to_format(clip, target_w, target_h)
                
                # Aplicar eliminación de marca de agua si está activo
                if remove_watermark:
                    logger.info(f"✂️ Aplicando zoom 15% para eliminar marca de agua en clip {idx + 1}...")
                    # Redimensionar al 115% (zoom in)
                    clip = clip.resize(1.15)
                    # Recortar al centro para mantener resolución
                    clip = clip.crop(
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                        width=target_w,
                        height=target_h
                    )
                
                # Asegurar que todos tengan el mismo tamaño exacto
                if clip.size[0] != target_w or clip.size[1] != target_h:
                    clip = clip.resize((target_w, target_h))
                
                # 🔧 VALIDACIÓN: Solo agregar clips válidos (evita error en get_frame)
                if clip is not None and hasattr(clip, 'get_frame') and hasattr(clip, 'duration') and clip.duration is not None and clip.duration > 0:
                    video_clips.append(clip)
                    logger.info(f"✅ Clip {idx + 1} procesado: {clip.duration:.2f}s, {clip.size} ({'Imagen animada' if is_image else 'Video'})")
                else:
                    logger.error(f"❌ Clip {idx + 1} inválido (None o sin get_frame), será omitido")
                    if clip is not None:
                        try:
                            clip.close()
                        except:
                            pass               
            
            if not video_clips:
                raise ValueError("No se pudieron cargar los clips de video")
            
            # --- PASO 2: Calcular puntos de corte para SFX (antes de concatenar) ---
            transition_cut_points = []
            if len(video_clips) > 1:
                cumulative_time = 0.0
                for idx, clip in enumerate(video_clips):
                    if idx < len(video_clips) - 1:  # No agregar corte después del último clip
                        cumulative_time += clip.duration
                        transition_cut_points.append(cumulative_time)
                logger.info(f"🎬 Puntos de corte detectados: {len(transition_cut_points)} transiciones")
            
             # --- PASO 2.5: Validar y concatenar todos los clips en orden ---
            # 🔧 CORREGIDO: Filtrar clips None o inválidos antes de concatenar
            valid_clips = []
            for clip_idx, clip in enumerate(video_clips):
                if clip is None:
                    logger.warning(f"⚠️ Clip {clip_idx + 1} es None, omitiendo...")
                    continue
                if not hasattr(clip, 'get_frame'):
                    logger.warning(f"⚠️ Clip {clip_idx + 1} no tiene get_frame, omitiendo...")
                    continue
                if not hasattr(clip, 'duration') or clip.duration is None or clip.duration <= 0:
                    logger.warning(f"⚠️ Clip {clip_idx + 1} tiene duración inválida ({getattr(clip, 'duration', 'N/A')}), omitiendo...")
                    continue
                valid_clips.append(clip)

            if not valid_clips:
                raise ValueError("❌ No hay clips válidos para concatenar. Todos los clips fueron None o inválidos.")

            logger.info(f"Concatenando {len(valid_clips)} clip(s) válidos (de {len(video_clips)} originales)...")
            concatenated_video = concatenate_videoclips(valid_clips, method="compose")

            
            # --- PASO 3: Guardar y cargar audio ---
            audio_path = temp_dir / f"manual_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            with open(audio_path, "wb") as f:
                f.write(audio_file.getbuffer())
            
            audio_clip = AudioFileClip(str(audio_path))
            audio_duration = audio_clip.duration
            
            # --- CORRECCIÓN DE VOLUMEN ---
            audio_clip = audio_clip.volumex(1.0)  # Volumen al 100%
            
            logger.info(f"Duración video concatenado: {total_video_duration:.2f}s, Duración audio: {audio_duration:.2f}s")
            
            # --- PASO 4: SINCRONIZACIÓN VIDEO vs AUDIO ---
            final_video = concatenated_video
            final_duration = total_video_duration
            
            if total_video_duration > audio_duration:
                # Video más largo: CORTAR el video para que termine con el audio
                logger.info(f"Cortando video de {total_video_duration:.2f}s a {audio_duration:.2f}s")
                final_video = concatenated_video.subclip(0, audio_duration)
                final_duration = audio_duration
            elif total_video_duration < audio_duration:
                # Video más corto: LOOPEAR la SECUENCIA COMPLETA hasta cubrir el audio
                loops_needed = int(audio_duration / total_video_duration) + 1
                logger.info(f"Video más corto. Loopeando secuencia completa {loops_needed} vez(ces)...")
                
                # Crear lista de la secuencia completa repetida
              # 🔧 Validar que concatenated_video sea válido antes de loopear
                if concatenated_video is None or not hasattr(concatenated_video, 'get_frame'):
                    raise ValueError("❌ No se puede loopear: el video concatenado es inválido")
                
                sequence_clips = [concatenated_video] * loops_needed
                looped_video = concatenate_videoclips(sequence_clips, method="compose")
                
                # Cortar al tamaño exacto del audio
                final_video = looped_video.subclip(0, audio_duration)
                final_duration = audio_duration
                logger.success(f"✅ Secuencia looped: {final_duration:.2f}s")
            
            # --- PASO 4.5: AGREGAR EFECTOS DE SONIDO (SFX) EN TRANSICIONES ---
            final_audio_with_sfx = audio_clip
            if transition_cut_points and len(transition_cut_points) > 0:
                try:
                    from moviepy.editor import CompositeAudioClip
                    
                    # Buscar archivo de SFX de transición
                    BASE_DIR = Path(".")
                    sfx_path = BASE_DIR / "assets" / "sfx" / "transition.mp3"
                    
                    if sfx_path.exists():
                        logger.info(f"🎵 Cargando SFX de transición desde: {sfx_path.name}")
                        transition_sfx = AudioFileClip(str(sfx_path))
                        sfx_duration = transition_sfx.duration
                        sfx_volume = 0.5  # Volumen al 50% para no romper los oídos
                        transition_sfx = transition_sfx.volumex(sfx_volume)
                        
                        # Crear clips de SFX en cada punto de corte
                        sfx_clips = []
                        target_duration = final_duration
                        
                        for cut_point in transition_cut_points:
                            # Ajustar punto de corte si el video fue cortado (pero no looped)
                            adjusted_cut_point = cut_point
                            
                            # Si el video fue cortado (no looped), los puntos de corte originales siguen siendo válidos
                            # Solo necesitamos verificar que no excedan la duración final
                            if adjusted_cut_point + sfx_duration <= target_duration:
                                sfx_at_cut = transition_sfx.set_start(adjusted_cut_point)
                                sfx_clips.append(sfx_at_cut)
                                logger.debug(f"✅ SFX agregado en transición {adjusted_cut_point:.2f}s")
                            else:
                                logger.debug(f"⚠️ Saltando SFX en {adjusted_cut_point:.2f}s (excedería duración del video)")
                        
                        if sfx_clips:
                            # Mezclar SFX con el audio principal
                            logger.info(f"🔊 Mezclando {len(sfx_clips)} efecto(s) de sonido de transición...")
                            audio_layers = [final_audio_with_sfx]
                            audio_layers.extend(sfx_clips)
                            final_audio_with_sfx = CompositeAudioClip(audio_layers)
                            logger.success(f"✅ {len(sfx_clips)} SFX de transición mezclado(s) exitosamente")
                        
                        # Cerrar el SFX original
                        transition_sfx.close()
                    else:
                        logger.info(f"💡 SFX de transición no encontrado en: {sfx_path}. Continuando sin efectos de sonido.")
                        logger.info(f"💡 Para agregar SFX, coloca 'transition.mp3' en: assets/sfx/")
                except Exception as e:
                    logger.warning(f"⚠️ Error agregando SFX de transición: {e}. Continuando sin efectos de sonido.")
                    import traceback
                    logger.debug(traceback.format_exc())
            
            # Combinar video con audio (con SFX si se agregaron)
            final_video = final_video.set_audio(final_audio_with_sfx)
            
            # --- PASO 5: SUBTÍTULOS CON FALLBACK (solo si está habilitado) ---
            # Obtener configuración de subtítulos desde session_state
            use_subtitles = st.session_state.get('use_subtitles', True)
            
            subtitle_clips = []
            
            if use_subtitles:
                logger.info("📝 Generando subtítulos (Burn-in activado)...")
                
                # Obtener dimensiones objetivo
                target_w = st.session_state.get('target_width', TARGET_WIDTH)
                target_h = st.session_state.get('target_height', TARGET_HEIGHT)
                
                # Intentar generar subtítulos karaoke desde el audio
                try:
                    subtitle_clips = editor.generate_karaoke_subtitles(
                        str(audio_path),
                        video_size=(target_w, target_h),
                        highlight_color='#00ff41'
                    )
                    if subtitle_clips:
                        logger.success(f"✅ Subtítulos karaoke generados: {len(subtitle_clips)} clips")
                except Exception as e:
                    logger.warning(f"⚠️ Error generando subtítulos karaoke: {e}")
                    subtitle_clips = []
                
                # FALLBACK: Si no hay subtítulos karaoke y hay texto del guion, crear subtítulo estático
                if not subtitle_clips and script_text and script_text.strip():
                    try:
                        logger.info("📝 Creando subtítulo estático desde el texto del guion...")
                        static_subtitle = editor.create_static_subtitle(
                            text=script_text.strip(),
                            duration=final_duration,
                            video_size=(target_w, target_h)
                        )
                        if static_subtitle:
                            subtitle_clips = [static_subtitle]
                            logger.success("✅ Subtítulo estático creado")
                    except Exception as e:
                        logger.warning(f"⚠️ Error creando subtítulo estático: {e}")
            else:
                logger.info("📝 Renderizando Clean Feed (Sin subtítulos - Burn-in desactivado)")
            
            # Combinar video con subtítulos (solo si hay subtítulos y están habilitados)
            layers = [final_video]
            if use_subtitles and subtitle_clips:
                # Filtrar clips None
                valid_subtitles = [clip for clip in subtitle_clips if clip is not None]
                if valid_subtitles:
                    layers.extend(valid_subtitles)
                    logger.info(f"✅ Agregando {len(valid_subtitles)} clips de subtítulos al video")
                else:
                    logger.warning("⚠️ No hay subtítulos válidos, renderizando sin subtítulos")
            
            # Crear CompositeVideoClip con los layers válidos
             # Crear CompositeVideoClip con los layers válidos
            # 🔧 CORREGIDO: Filtrar cualquier layer None o inválido antes de componer
            valid_layers = []
            for layer_idx, layer in enumerate(layers):
                if layer is None:
                    logger.warning(f"⚠️ Layer {layer_idx} es None, omitiendo...")
                    continue
                if not hasattr(layer, 'get_frame'):
                    logger.warning(f"⚠️ Layer {layer_idx} no tiene get_frame, omitiendo...")
                    continue
                # Validar duración solo si no es el video base (índice 0)
                if layer_idx > 0 and hasattr(layer, 'duration') and (layer.duration is None or layer.duration <= 0):
                    logger.warning(f"⚠️ Layer {layer_idx} (subtítulo) tiene duración inválida, omitiendo...")
                    continue
                valid_layers.append(layer)

            if not valid_layers:
                raise ValueError("❌ No hay layers válidos para componer el video final.")

            if len(valid_layers) > 1:
                logger.info(f"✅ Componiendo video con {len(valid_layers)} layers válidos")
                final_clip = CompositeVideoClip(valid_layers)
            else:
                final_clip = valid_layers[0]
            
            # Renderizar video final
            output_dir = BASE_DIR / "output"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"manual_mix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            
            # Forzar Super 1080p (1080x1920) para máxima calidad en redes sociales
            SUPER_1080P_WIDTH = 1080
            SUPER_1080P_HEIGHT = 1920
            
            # Asegurar que el video final esté en Super 1080p
            if final_clip.size[0] != SUPER_1080P_WIDTH or final_clip.size[1] != SUPER_1080P_HEIGHT:
                logger.info(f"Redimensionando a Super 1080p: {SUPER_1080P_WIDTH}x{SUPER_1080P_HEIGHT}...")
                # Redimensionar y recortar al centro para llenar el canvas sin bordes negros
                from src.video_editor import VideoEditor
                editor = VideoEditor()
                final_clip = editor._resize_to_format(final_clip, SUPER_1080P_WIDTH, SUPER_1080P_HEIGHT)
            
            # Configuración Super 1080p para máxima calidad
            video_bitrate = "15000k"  # 15 Mbps - Calidad de estudio
            audio_bitrate = "320k"  # Calidad de estudio para audio
            
            logger.info(f"Renderizando video final en Super 1080p: {SUPER_1080P_WIDTH}x{SUPER_1080P_HEIGHT} @ 60 FPS")
            logger.info(f"Bitrate: {video_bitrate} (video) / {audio_bitrate} (audio)")
            
            final_clip.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                fps=60,  # 60 FPS para máxima fluidez en móviles
                preset='slow',  # Mejor compresión y calidad
                bitrate=video_bitrate,
                audio_bitrate=audio_bitrate,
                threads=4,
                logger=None
            )
            
            # Limpiar recursos
            final_clip.close()
            final_video.close()
            concatenated_video.close()
            for clip in video_clips:
                try:
                    clip.close()
                except:
                    pass
            if audio_clip:
                audio_clip.close()
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error en mezcla manual: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            raise
    
    # Procesar renderizado manual
    if render_manual_btn:
        if not uploaded_videos or len(uploaded_videos) == 0:
            st.error("❌ ¡Necesitas subir al menos un clip de video!")
        elif not uploaded_audio:
            st.error("❌ ¡Necesitas subir un archivo de audio!")
        else:
            st.session_state.streamlit_logger.write(f"🎨 [MEZCLADOR MANUAL] Iniciando renderizado con {len(uploaded_videos)} clip(s)...")
            
            try:
                with st.spinner("⚙️ Procesando mezcla manual (esto puede tardar varios minutos)..."):
                    video_path = process_manual_mix(uploaded_videos, uploaded_audio, script_text_manual, remove_watermark, mute_original_video)
                
                st.session_state.current_video = video_path
                st.session_state.streamlit_logger.write(f"✅ Video mezclado: {video_path}")
                st.success("✅ ¡Video Mezclado con Éxito!")
                st.balloons()
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.session_state.streamlit_logger.write(f"❌ ERROR: {str(e)}")
                logger.error(f"Error en mezclador manual: {e}")
    
    # Mostrar video mezclado
    if st.session_state.current_video and Path(st.session_state.current_video).exists():
        st.markdown("---")
        st.subheader("🎬 Video Mezclado")
        st.video(st.session_state.current_video)
        st.caption(f"📹 Ruta: `{st.session_state.current_video}`")

# ============================================================
# TAB 6: GALERÍA / BIBLIOTECA
# ============================================================
with tabs[5]:
    st.header("📂 Galería / Biblioteca de Videos")
    st.caption("Gestiona tus videos generados localmente. Revisa, sube o elimina videos desde aquí.")
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Escanear videos en output/
    video_files = list(output_dir.glob("*.mp4"))
    video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)  # Más reciente primero
    
    if not video_files:
        st.info("📭 No hay videos en la galería. Genera tu primer video para verlo aquí.")
    else:
        st.success(f"✅ Encontrados {len(video_files)} video(s) en la biblioteca")
        
        # Filtros y búsqueda
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            search_term = st.text_input("🔍 Buscar por nombre", placeholder="Ej: autoviral_2024...")
        with col_filter2:
            show_uploaded_only = st.checkbox("Mostrar solo videos no subidos", value=False)
        
        # Filtrar videos
        filtered_videos = video_files
        if search_term:
            filtered_videos = [v for v in filtered_videos if search_term.lower() in v.name.lower()]
        
        # Cargar historial de analytics para verificar estado de subida
        upload_status_map = {}
        try:
            history = analytics_manager.get_history()
            for record in history:
                # Intentar mapear por timestamp o tema (aproximado)
                upload_status_map[record.get("topic", "")] = record.get("upload_status", "Solo Render")
        except:
            pass
        
        if not filtered_videos:
            st.warning("No se encontraron videos con los filtros aplicados.")
        else:
            # Mostrar videos en grid
            videos_per_row = 3
            for i in range(0, len(filtered_videos), videos_per_row):
                cols = st.columns(videos_per_row)
                for j, video_path in enumerate(filtered_videos[i:i+videos_per_row]):
                    with cols[j]:
                        # Buscar archivos asociados
                        video_stem = video_path.stem
                        metadata_path = output_dir / f"metadata_{video_stem.split('_')[-1] if '_' in video_stem else video_stem}.json"
                        thumbnail_path = output_dir / f"thumbnail_{video_stem}.jpg"
                        
                        # Intentar encontrar metadata por timestamp
                        if not metadata_path.exists():
                            # Buscar cualquier metadata que pueda corresponder
                            for meta_file in output_dir.glob("metadata_*.json"):
                                try:
                                    with open(meta_file, 'r', encoding='utf-8') as f:
                                        meta_data = json.load(f)
                                    # Verificar si el timestamp coincide aproximadamente
                                    if video_stem in meta_file.stem or abs(
                                        video_path.stat().st_mtime - meta_file.stat().st_mtime
                                    ) < 60:  # Dentro de 60 segundos
                                        metadata_path = meta_file
                                        break
                                except:
                                    pass
                        
                        # Cargar metadatos si existen
                        metadata = None
                        if metadata_path.exists():
                            try:
                                with open(metadata_path, 'r', encoding='utf-8') as f:
                                    metadata = json.load(f)
                            except:
                                pass
                        
                        # Mostrar miniatura o video
                        if thumbnail_path.exists():
                            st.image(str(thumbnail_path), use_column_width=True)
                        else:
                            # Mostrar primer frame del video como preview
                            try:
                                from moviepy.editor import VideoFileClip
                                clip = VideoFileClip(str(video_path))
                                
                                # VALIDACIÓN: Verificar que el clip no es None y tiene get_frame
                                if clip is None:
                                    raise ValueError("VideoFileClip retornó None")
                                
                                if not hasattr(clip, 'get_frame'):
                                    raise ValueError("Clip no tiene método get_frame")
                                
                                # Validar que tiene duración válida
                                if not hasattr(clip, 'duration') or clip.duration is None or clip.duration <= 0:
                                    raise ValueError("Clip no tiene duración válida")
                                
                                frame = clip.get_frame(0)
                                clip.close()
                                st.image(frame, use_column_width=True)
                            except Exception as e:
                                # Si falla la extracción del frame, mostrar el video directamente
                                st.video(str(video_path))
                        
                        # Información del video
                        file_size_mb = video_path.stat().st_size / (1024 * 1024)
                        file_date = datetime.fromtimestamp(video_path.stat().st_mtime)
                        
                        # Título y metadatos
                        if metadata:
                            title = metadata.get('title_viral') or metadata.get('title_seo', video_path.name)
                            st.markdown(f"**{title[:50]}...**" if len(title) > 50 else f"**{title}**")
                            st.caption(f"📅 {file_date.strftime('%Y-%m-%d %H:%M')} | 📦 {file_size_mb:.1f} MB")
                            
                            # Mostrar descripción si existe
                            desc = metadata.get('description', '')
                            if desc:
                                with st.expander("📝 Ver descripción"):
                                    st.caption(desc[:200] + "..." if len(desc) > 200 else desc)
                        else:
                            st.markdown(f"**{video_path.name}**")
                            st.caption(f"📅 {file_date.strftime('%Y-%m-%d %H:%M')} | 📦 {file_size_mb:.1f} MB")
                        
                        # Estado de subida (verificar en analytics)
                        upload_status = "Solo Render"
                        if metadata and metadata.get('title_viral'):
                            # Intentar buscar en historial
                            for record in history:
                                if record.get("topic", "").lower() in metadata.get('title_viral', '').lower():
                                    upload_status = record.get("upload_status", "Solo Render")
                                    break
                        
                        if upload_status == "Subido":
                            st.success("✅ Subido")
                        else:
                            st.info("📤 No subido")
                        
                        # Botones de acción
                        col_btn1, col_btn2 = st.columns(2)
                        
                        with col_btn1:
                            if st.button("🚀 YouTube", key=f"yt_{video_path.name}_{i}_{j}", use_container_width=True):
                                if UPLOADERS_AVAILABLE:
                                    try:
                                        with st.spinner("Subiendo a YouTube..."):
                                            youtube_uploader = YouTubeUploader()
                                            
                                            # Preparar título y descripción
                                            title = "Metratron Films Production"
                                            description = ""
                                            
                                            if metadata:
                                                title = metadata.get('title_viral') or metadata.get('title_seo', title)
                                                description = metadata.get('description', '')
                                                if metadata.get('hashtags'):
                                                    description = f"{description}\n\n{metadata['hashtags']}".strip()
                                            
                                            if not description:
                                                description = "Produced by Metratron Films"
                                            
                                            success, message, video_id = youtube_uploader.upload_video(
                                                file_path=str(video_path),
                                                title=title,
                                                description=description,
                                                privacy="private"
                                            )
                                            
                                            if success:
                                                st.success(f"✅ {message}")
                                                st.session_state.streamlit_logger.write(f"[GALERÍA] YouTube: {message}")
                                                # Registrar en analytics
                                                analytics_manager.log_generation(
                                                    st.session_state.get("active_profile", "Configuración Actual"),
                                                    title,
                                                    1.0,  # Duración estimada
                                                    "Subido"
                                                )
                                                st.rerun()
                                            else:
                                                st.error(f"❌ {message}")
                                                st.session_state.streamlit_logger.write(f"[GALERÍA] Error YouTube: {message}")
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                                        st.session_state.streamlit_logger.write(f"[GALERÍA] Error YouTube: {str(e)}")
                                else:
                                    st.warning("⚠️ Uploaders no disponibles")
                        
                        with col_btn2:
                            if st.button("🎵 TikTok", key=f"tt_{video_path.name}_{i}_{j}", use_container_width=True):
                                if UPLOADERS_AVAILABLE:
                                    try:
                                        with st.spinner("Subiendo a TikTok..."):
                                            tiktok_uploader = TikTokUploader()
                                            
                                            # Preparar descripción
                                            description_parts = []
                                            
                                            if metadata:
                                                title = metadata.get('title_viral', '')
                                                desc = metadata.get('description', '')
                                                hashtags = metadata.get('hashtags', '')
                                                
                                                if title:
                                                    description_parts.append(title)
                                                if desc:
                                                    description_parts.append(desc)
                                                if hashtags:
                                                    description_parts.append(hashtags)
                                            
                                            description = " ".join(description_parts).strip()
                                            if not description:
                                                description = "Metratron Films Production"
                                            
                                            success, message = tiktok_uploader.upload_video(
                                                file_path=str(video_path),
                                                description=description,
                                                cookies_path="tiktok_cookies.txt"
                                            )
                                            
                                            if success:
                                                st.success(f"✅ {message}")
                                                st.session_state.streamlit_logger.write(f"[GALERÍA] TikTok: {message}")
                                                # Registrar en analytics
                                                analytics_manager.log_generation(
                                                    st.session_state.get("active_profile", "Configuración Actual"),
                                                    description[:50],
                                                    1.0,
                                                    "Subido"
                                                )
                                                st.rerun()
                                            else:
                                                st.error(f"❌ {message}")
                                                st.session_state.streamlit_logger.write(f"[GALERÍA] Error TikTok: {message}")
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                                        st.session_state.streamlit_logger.write(f"[GALERÍA] Error TikTok: {str(e)}")
                                else:
                                    st.warning("⚠️ Uploaders no disponibles")
                        
                        # Botón de borrar
                        if st.button("🗑️ Borrar", key=f"del_{video_path.name}_{i}_{j}", use_container_width=True, type="secondary"):
                            try:
                                # Eliminar video
                                video_path.unlink()
                                
                                # Eliminar archivos asociados
                                if metadata_path.exists():
                                    metadata_path.unlink()
                                if thumbnail_path.exists():
                                    thumbnail_path.unlink()
                                
                                st.success("✅ Video eliminado")
                                st.session_state.streamlit_logger.write(f"[GALERÍA] Video eliminado: {video_path.name}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar: {str(e)}")
                                st.session_state.streamlit_logger.write(f"[GALERÍA] Error al eliminar: {str(e)}")
                        
                        st.markdown("---")

# ============================================================
# TAB 7: ANALYTICS
# ============================================================
with tabs[6]:
    st.header("📈 Analytics")
    history = analytics_manager.get_history()
    
    if not history:
        st.info("Aún no hay datos de generaciones. Crea tu primer video para ver métricas.")
    else:
        growth_data = analytics_manager.get_growth_data()
        total_videos = len(history)
        total_hours_saved = total_videos * 1.0  # fallback
        active_profiles = 1
        
        if isinstance(growth_data, dict) and growth_data.get("summary") is not None:
            summary_df = growth_data["summary"]
            try:
                total_hours_saved = float(summary_df["hours_saved"].sum())
                active_profiles = int(summary_df["profile"].nunique())
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Total Videos", f"{total_videos}")
                col_b.metric("Horas Ahorradas", f"{total_hours_saved:.1f} h")
                col_c.metric("Nichos Activos", f"{active_profiles}")
                
                st.subheader("Producción diaria por perfil")
                st.line_chart(growth_data["daily"])
                
                st.subheader("Historial reciente")
                recent_df = growth_data["raw"].sort_values("timestamp", ascending=False).head(20)
                st.dataframe(recent_df[["timestamp", "profile", "topic", "duration_minutes", "upload_status"]])
            except Exception as e:
                st.warning(f"No se pudieron calcular métricas avanzadas: {e}")
                st.table(history[-10:])
        else:
            st.metric("Total Videos", f"{total_videos}")
            st.metric("Horas Ahorradas (estimadas)", f"{total_hours_saved:.1f} h")
            st.metric("Nichos Activos", f"{active_profiles}")
            st.subheader("Historial")
            st.table(history[-10:])
# Footer
st.markdown("---")
st.caption("© 2025 Metratron Films - Internal Tools | MF-Studio v2.5 (Enterprise)")

