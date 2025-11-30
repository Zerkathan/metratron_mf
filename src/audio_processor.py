"""
AudioEngineer: utilidades de post-procesamiento para voces TTS.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from pydub import AudioSegment
except ImportError:  # pragma: no cover - dependencia opcional
    AudioSegment = None  # type: ignore


class AudioEngineer:
    """Procesa archivos de audio generados por TTS para mejorar su calidad."""

    def __init__(self):
        self.available = AudioSegment is not None
        if not self.available:
            logger.warning("⚠️ pydub no está instalado. AudioEngineer quedará deshabilitado.")

    def _load_segment(self, audio_path: str) -> Optional[AudioSegment]:
        if not self.available:
            return None
        try:
            return AudioSegment.from_file(audio_path)
        except Exception as exc:  # pragma: no cover - dependencias externas
            logger.error(f"❌ No se pudo cargar audio '{audio_path}': {exc}")
            return None

    @staticmethod
    def _export_segment(segment: AudioSegment, original_path: str) -> str:
        output_path = Path(original_path)
        fmt = output_path.suffix.lstrip(".") or "mp3"
        segment.export(str(output_path), format=fmt)
        return str(output_path)

    @staticmethod
    def _detect_leading_silence(sound: AudioSegment, silence_thresh: float, chunk_size: int) -> int:
        trim_ms = 0
        chunk_size = max(1, chunk_size)
        duration = len(sound)
        while trim_ms < duration:
            chunk = sound[trim_ms:trim_ms + chunk_size]
            if chunk.dBFS > silence_thresh:
                break
            trim_ms += chunk_size
        return trim_ms

    def remove_silence(self, audio_path: str, silence_thresh: float = -40.0, chunk_size: int = 10) -> str:
        """
        Recorta silencios solo al inicio y al final del clip.
        """
        segment = self._load_segment(audio_path)
        if segment is None:
            return audio_path

        duration = len(segment)
        start_trim = self._detect_leading_silence(segment, silence_thresh, chunk_size)
        end_trim = self._detect_leading_silence(segment.reverse(), silence_thresh, chunk_size)
        trimmed_duration = duration - start_trim - end_trim

        if trimmed_duration <= 0:
            logger.warning("⚠️ El recorte resultó en audio vacío. Se mantiene el original.")
            return audio_path

        trimmed_audio = segment[start_trim:duration - end_trim]
        logger.debug(f"✂️ Silencios recortados: inicio {start_trim}ms, final {end_trim}ms.")
        return self._export_segment(trimmed_audio, audio_path)

    def speed_up(self, audio_path: str, speed_factor: float = 1.15) -> str:
        """
        Acelera la voz manteniendo el tono original.
        """
        if speed_factor <= 0:
            logger.warning("⚠️ speed_factor inválido. Se omite speed_up.")
            return audio_path

        segment = self._load_segment(audio_path)
        if segment is None:
            return audio_path

        try:
            sped = segment._spawn(
                segment.raw_data,
                overrides={"frame_rate": int(segment.frame_rate * speed_factor)}
            )
            sped = sped.set_frame_rate(segment.frame_rate)
        except Exception as exc:
            logger.error(f"❌ Error al acelerar audio '{audio_path}': {exc}")
            return audio_path

        logger.debug(f"⚡ Audio acelerado {speed_factor:.2f}x.")
        return self._export_segment(sped, audio_path)

    def normalize_volume(self, audio_path: str, target_dBFS: float = -3.0) -> str:
        """
        Ajusta el volumen global para que la voz suene consistente.
        """
        segment = self._load_segment(audio_path)
        if segment is None:
            return audio_path

        current_dBFS = segment.dBFS
        if math.isinf(current_dBFS):
            logger.warning("⚠️ El audio es completamente silencioso. Se omite normalización.")
            return audio_path

        change_in_dBFS = target_dBFS - current_dBFS
        normalized = segment.apply_gain(change_in_dBFS)
        logger.debug(f"🔊 Normalizando audio: {current_dBFS:.2f}dBFS → {target_dBFS:.2f}dBFS.")
        return self._export_segment(normalized, audio_path)





