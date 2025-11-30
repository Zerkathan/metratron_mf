# 🎬 Metratron Bot - Generador Automático de Videos Virales

Sistema profesional de generación automática de videos para redes sociales (TikTok, Instagram, YouTube Shorts) con IA.

## ✨ Características

- 🎨 **Generación Automática de Scripts**: Usa Google Gemini para crear guiones virales
- 🎙️ **Narración con IA**: Síntesis de voz usando Edge-TTS
- 🎬 **Edición Automática**: Procesamiento de video con MoviePy
- 📸 **Visuales Automáticos**: Búsqueda en Pexels, Pixabay, DALL-E 3 y RunwayML
- 🎵 **Música de Fondo**: Sistema automático de selección y mezcla de música
- 📝 **Subtítulos Dinámicos**: Generación automática con Whisper
- 🎯 **Múltiples Estilos**: Creador de curiosidades, noticias, motivación, etc.
- 📊 **Dashboard Streamlit**: Interfaz profesional para gestión
- 🚀 **Upload Automático**: Integración con YouTube, TikTok e Instagram

## 🛠️ Tecnologías

- **Python 3.9+**
- **Streamlit** - Dashboard web
- **MoviePy** - Edición de video
- **Edge-TTS** - Síntesis de voz
- **Whisper** - Transcripción de audio
- **Google Gemini API** - Generación de contenido
- **Pexels/Pixabay APIs** - Stock videos
- **DALL-E 3** - Generación de imágenes
- **RunwayML** - Generación de video con IA

## 📋 Requisitos Previos

- Python 3.9 o superior
- ImageMagick (para subtítulos)
- FFmpeg (incluido con MoviePy)
- API Keys:
  - Google Gemini API
  - Pexels API (opcional)
  - Pixabay API (opcional)
  - OpenAI API (para DALL-E, opcional)
  - RunwayML API (opcional)

## 🚀 Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/metratron_bot.git
   cd metratron_bot
   ```

2. **Crear entorno virtual:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   - Copiar `.env.example` a `.env`
   - Agregar tus API keys

5. **Iniciar el dashboard:**
   ```bash
   streamlit run dashboard.py
   ```

## 📁 Estructura del Proyecto

```
metratron_bot/
├── src/
│   ├── script_generator.py    # Generación de guiones con Gemini
│   ├── audio_engine.py         # Síntesis de voz
│   ├── video_editor.py         # Edición de video
│   ├── stock_manager.py        # Búsqueda de stock videos
│   ├── asset_manager.py        # Gestión de assets
│   ├── uploader.py             # Upload a redes sociales
│   └── ...
├── assets/
│   ├── music/                  # Música de fondo por género
│   ├── branding/               # Intros/outros
│   └── temp/                   # Archivos temporales
├── output/                     # Videos generados
├── profiles/                   # Perfiles de configuración
├── dashboard.py                # Interfaz Streamlit
└── main.py                     # Orquestador principal
```

## 🎯 Uso Básico

### Desde el Dashboard:

1. Abre `http://localhost:8501` en tu navegador
2. Ingresa el tema del video
3. Selecciona estilo y configuración
4. Click en "Generar Video"
5. El video se generará automáticamente

### Desde Python:

```python
from main import AutoViralBot

bot = AutoViralBot()
video_info = await bot.generate_video(
    topic="Curiosidades sobre el espacio",
    duration_minutes=1.0,
    style_prompt="CURIOSIDADES"
)
```

## 🔧 Configuración

### Estilos Disponibles

- **CURIOSIDADES**: Videos informativos estilo "Sabías que..."
- **NOTICIAS**: Formato noticiero viral
- **MOTIVACIÓN**: Contenido inspiracional
- **HORROR**: Contenido de suspenso/terror
- **LOFI**: Ambiente relajado

### Perfiles

Crea perfiles personalizados para diferentes canales desde el dashboard.

## 📝 Licencia

© 2025 Metratron Films - Internal Tools

## 🤝 Contribuciones

Este es un proyecto interno. Para sugerencias o reportes de bugs, contactar al equipo de desarrollo.

## ⚠️ Notas Importantes

- Los videos generados pueden ser grandes. Asegúrate de tener espacio en disco.
- El proceso puede tardar varios minutos dependiendo de la duración.
- Se recomienda tener conexión estable a internet para descargas de stock.

## 🔗 Enlaces Útiles

- [Documentación de MoviePy](https://zulko.github.io/moviepy/)
- [Edge-TTS Documentation](https://github.com/rany2/edge-tts)
- [Streamlit Documentation](https://docs.streamlit.io/)

---

**Versión:** 2.5 Enterprise  
**Última actualización:** 2025

