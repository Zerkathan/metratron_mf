"""
Utilidades para generar previews rápidos de voz utilizando Edge-TTS.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    import edge_tts
except ImportError:  # pragma: no cover - edge_tts es requisito principal
    edge_tts = None


async def _synthesize_preview(text: str, voice: str, output_file: Path) -> None:
    """Ejecuta la síntesis de forma asíncrona."""
    communicator = edge_tts.Communicate(text, voice)
    await communicator.save(str(output_file))


def generate_voice_preview(
    text: str,
    voice: str,
    output_dir: str = "assets/temp/previews",
    filename: Optional[str] = None,
) -> Optional[str]:
    """
    Genera un clip corto de audio para previsualizar la voz seleccionada.
    Retorna la ruta del archivo generado o None si falla.
    """
    if not text or not text.strip():
        logger.warning("⚠️ Texto vacío para preview de voz.")
        return None

    if not voice or voice == "NO_VOICE":
        logger.warning("⚠️ No hay voz seleccionada para preview.")
        return None

    if edge_tts is None:
        logger.error("❌ edge_tts no está instalado. No se puede generar preview.")
        return None

    output_base = Path(output_dir)
    output_base.mkdir(parents=True, exist_ok=True)

    preview_name = filename or f"voice_preview_{uuid.uuid4().hex}.mp3"
    preview_file = output_base / preview_name
    if filename and preview_file.exists():
        try:
            preview_file.unlink()
        except OSError:
            pass
    clean_text = text.strip()

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_synthesize_preview(clean_text, voice, preview_file))
    except Exception as exc:  # pragma: no cover - dependencias externas
        logger.error(f"❌ Error generando preview de voz: {exc}")
        if preview_file.exists():
            try:
                preview_file.unlink()
            except OSError:
                pass
        return None
    finally:
        loop.close()

    if preview_file.exists() and preview_file.stat().st_size > 0:
        return str(preview_file)

    if preview_file.exists():
        try:
            preview_file.unlink()
        except OSError:
            pass

    logger.error("❌ La preview de voz no se generó correctamente.")
    return None


