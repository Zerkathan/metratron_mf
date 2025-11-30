"""
Parche para video_editor.py: Función esperar_archivo y mejora de _get_word_timestamps

Copia estas funciones en tu src/video_editor.py y reemplaza el método _get_word_timestamps
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any


def esperar_archivo(ruta_archivo: str, intentos: int = 30, espera: float = 0.5) -> bool:
    """
    Espera a que un archivo exista y tenga contenido.
    Especialmente importante para archivos en OneDrive que pueden estar sincronizándose.
    
    Args:
        ruta_archivo: Ruta absoluta del archivo a esperar
        intentos: Cuántas veces revisará (30 veces * 0.5s = 15 segundos máx)
        espera: Segundos de espera entre intentos
    
    Returns:
        True si el archivo existe y tiene contenido, False en caso contrario
    """
    from loguru import logger
    
    logger.info(f"🔍 Buscando archivo: {ruta_archivo}")
    
    # Convertir a Path para normalización
    ruta_archivo_path = Path(ruta_archivo)
    
    for i in range(intentos):
        # 1. Verificar si existe
        if ruta_archivo_path.exists():
            try:
                # 2. Verificar si tiene tamaño (no está vacío)
                size = ruta_archivo_path.stat().st_size
                if size > 0:
                    logger.success(f"✅ Archivo encontrado y listo: {ruta_archivo} ({size:,} bytes)")
                    time.sleep(0.3)  # Pausa de seguridad para liberar el 'lock' de OneDrive
                    return True
                else:
                    logger.warning(f"⏳ El archivo existe pero está vacío (Intento {i+1}/{intentos})...")
            except (OSError, PermissionError) as e:
                # OneDrive puede estar bloqueando el archivo temporalmente
                logger.debug(f"⏳ Archivo bloqueado por OneDrive? (Intento {i+1}/{intentos}): {e}")
        else:
            logger.debug(f"⏳ Esperando creación del archivo (Intento {i+1}/{intentos})...")
        
        time.sleep(espera)
    
    logger.error(f"❌ ERROR CRÍTICO: El archivo nunca apareció en: {ruta_archivo}")
    return False


def _get_word_timestamps_FIXED(self, audio_file: str) -> List[Dict[str, Any]]:
    """
    Versión corregida de _get_word_timestamps que espera a que el archivo exista.
    
    Reemplaza el método _get_word_timestamps en VideoEditor con este código.
    """
    from loguru import logger
    
    try:
        # Obtener la ruta base del proyecto automáticamente
        BASE_DIR = Path(__file__).parent.parent.resolve()
        
        # Construir la ruta absoluta de forma segura
        audio_path = Path(audio_file)
        
        # Si es relativo, construir la ruta completa
        if not audio_path.is_absolute():
            audio_path = BASE_DIR / "assets" / "temp" / audio_path.name
        else:
            # Ya es absoluta, normalizar
            audio_path = audio_path.resolve()
        
        ruta_audio_abs = str(audio_path)
        
        logger.debug(f"Ruta absoluta generada: {ruta_audio_abs}")
        
        # ESPERAR A QUE EL ARCHIVO EXISTA Y TENGA CONTENIDO
        if not esperar_archivo(ruta_audio_abs, intentos=30, espera=0.5):
            logger.error(f"Archivo de audio no encontrado después de esperar: {ruta_audio_abs}")
            return []
        
        # Verificación final antes de procesar
        if not Path(ruta_audio_abs).exists():
            logger.error(f"Archivo desapareció después de esperar: {ruta_audio_abs}")
            return []
        
        # Whisper puede tener problemas con archivos bloqueados por OneDrive
        # Copiar el archivo a una ubicación temporal para asegurar acceso
        import shutil
        import tempfile
        
        temp_dir = BASE_DIR / "assets" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear una copia temporal del archivo para Whisper
        temp_audio_path = temp_dir / f"whisper_temp_{Path(ruta_audio_abs).name}"
        
        try:
            logger.debug(f"Copiando archivo para Whisper: {temp_audio_path}")
            
            # Copiar el archivo a la ubicación temporal
            shutil.copy2(ruta_audio_abs, temp_audio_path)
            
            # Esperar un momento adicional para asegurar que la copia esté lista
            time.sleep(0.2)
            
            whisper_path = str(temp_audio_path.resolve())
            
            logger.info(f"Transcribiendo audio con Whisper: {whisper_path}")
            
            # Transcribir con Whisper usando la copia temporal
            result = self.whisper_model.transcribe(
                whisper_path,
                word_timestamps=True,
                language="es"
            )
            
            logger.success(f"✅ Transcripción completada para: {Path(ruta_audio_abs).name}")
            
        finally:
            # Limpiar el archivo temporal después de la transcripción
            try:
                if temp_audio_path.exists():
                    time.sleep(0.5)  # Dar tiempo a Whisper para liberar el archivo
                    temp_audio_path.unlink()
                    logger.debug(f"Archivo temporal eliminado: {temp_audio_path}")
            except Exception as cleanup_error:
                logger.warning(f"No se pudo eliminar archivo temporal: {cleanup_error}")
        
        # Procesar las palabras y sus timestamps
        words = []
        if result and "segments" in result:
            for segment in result["segments"]:
                if "words" in segment:
                    for word_info in segment["words"]:
                        words.append({
                            "word": word_info["word"].strip(),
                            "start": word_info["start"],
                            "end": word_info["end"]
                        })
        
        logger.debug(f"Se extrajeron {len(words)} palabras con timestamps")
        return words
        
    except Exception as e:
        logger.error(f"Error en transcripción Whisper: {e}")
        logger.error(f"Ruta intentada: {ruta_audio_abs if 'ruta_audio_abs' in locals() else audio_file}")
        return []













