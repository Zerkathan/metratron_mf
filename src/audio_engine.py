"""
AudioEngine: Genera narraciones de audio usando Edge-TTS.
"""

import os
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
import edge_tts
from loguru import logger


class AudioEngine:
    """Motor de generación de audio usando Edge-TTS."""
    
    def __init__(self, voice: str = "es-MX-DaliaNeural", rate: str = "+0%"):
        """
        Inicializa el motor de audio.
        
        Args:
            voice: Voz de Edge-TTS a usar
            rate: Velocidad de habla (ej: "+0%", "+10%", "-5%")
        """
        self.voice = voice
        self.rate = rate
        logger.info(f"AudioEngine inicializado con voz: {voice}")
    
    async def generate_audio(self, text: str, voice: str, output_filename: str) -> Optional[str]:
        """
        Genera un archivo de audio individual con la voz especificada.
        
        Args:
            text: Texto a convertir a audio
            voice: Voz de Edge-TTS a usar (ej: "es-MX-JorgeNeural")
            output_filename: Ruta completa del archivo de salida
        
        Returns:
            Ruta del archivo generado o None si falla
        """
        logger.info(f"🎙️ Generando audio: {Path(output_filename).name}")
        logger.info(f"🗣️ Voz: {voice}")
        
        # Validación de texto
        if not text or len(text.strip()) == 0:
            logger.error("❌ Error: El texto está vacío.")
            return None
        
        # Mostrar preview del texto
        text_preview = text[:50] + "..." if len(text) > 50 else text
        logger.info(f"📝 Texto ({len(text)} caracteres): {text_preview}")
        
        # Asegurar que la carpeta existe
        output_file = Path(output_filename)
        output_dir = output_file.parent
        
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"📁 Carpeta creada: {output_dir}")
            except Exception as e:
                logger.error(f"❌ Error creando carpeta {output_dir}: {e}")
                return None
        
        # Normalizar ruta absoluta
        output_path_abs = str(output_file.resolve())
        
        # Generación con Edge-TTS usando la voz especificada
        try:
            logger.debug(f"⚙️ Iniciando síntesis con Edge-TTS...")
            communicate = edge_tts.Communicate(text, voice, rate=self.rate)
            await communicate.save(output_path_abs)
            
            # Verificar que el archivo se creó
            if os.path.exists(output_path_abs) and os.path.getsize(output_path_abs) > 0:
                file_size = os.path.getsize(output_path_abs)
                logger.success(f"✅ Audio guardado: {output_file.name} ({file_size} bytes)")
                return output_path_abs
            else:
                logger.error(f"❌ El archivo se creó pero está vacío: {output_path_abs}")
                try:
                    if os.path.exists(output_path_abs):
                        os.remove(output_path_abs)
                except:
                    pass
                return None
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"💥 Error generando audio: {error_msg}")
            
            # Diagnóstico específico
            if "400" in error_msg or "voice" in error_msg.lower() or "invalid" in error_msg.lower():
                logger.error(f"⚠️ La voz '{voice}' parece inválida.")
                logger.error(f"💡 Formato esperado: 'es-MX-JorgeNeural', 'es-MX-DaliaNeural', etc.")
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                logger.error(f"⚠️ Error de conexión con Edge-TTS. Verifica tu conexión a internet.")
            elif "permission" in error_msg.lower() or "access" in error_msg.lower():
                logger.error(f"⚠️ Error de permisos al escribir en: {output_path_abs}")
            
            return None
    
    async def _generate_single_clip(self, text: str, output_path: str, scene_idx: int) -> Optional[str]:
        """
        Genera un clip de audio individual con manejo de errores robusto.
        
        Args:
            text: Texto a convertir a audio
            output_path: Ruta de salida del archivo
            scene_idx: Índice de la escena
        
        Returns:
            Ruta del archivo generado o None si falla
        """
        logger.info(f"🎙️ Intentando generar audio para escena {scene_idx + 1}: {output_path}")
        logger.info(f"🗣️ Voz seleccionada: {self.voice}")
        
        # 1. Validación de texto
        if not text or len(text.strip()) == 0:
            logger.error(f"❌ Error: El texto para la escena {scene_idx + 1} está vacío.")
            return None
        
        # Mostrar preview del texto
        text_preview = text[:50] + "..." if len(text) > 50 else text
        logger.info(f"📝 Texto a convertir ({len(text)} caracteres): {text_preview}")
        
        # 2. Asegurar que la carpeta existe y usar ruta absoluta
        output_file = Path(output_path)
        output_dir = output_file.parent
        
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"📁 Carpeta creada: {output_dir}")
            except Exception as e:
                logger.error(f"❌ Error creando carpeta {output_dir}: {e}")
                return None
        
        # Normalizar ruta absoluta
        output_path_abs = str(output_file.resolve())
        logger.debug(f"📂 Ruta absoluta: {output_path_abs}")
        
        # 3. Generación con Edge-TTS
        try:
            logger.info(f"⚙️ Iniciando síntesis de voz con Edge-TTS...")
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
            await communicate.save(output_path_abs)
            
            # 4. Verificar que el archivo se creó y pesa algo
            if os.path.exists(output_path_abs) and os.path.getsize(output_path_abs) > 0:
                file_size = os.path.getsize(output_path_abs)
                logger.success(f"✅ Audio guardado correctamente: {output_file.name} ({file_size} bytes)")
                return output_path_abs
            else:
                logger.error(f"❌ El archivo se creó pero está vacío (0 bytes). Ruta: {output_path_abs}")
                # Intentar eliminar archivo vacío
                try:
                    if os.path.exists(output_path_abs):
                        os.remove(output_path_abs)
                except:
                    pass
                return None
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"💥 EXCEPCIÓN CRÍTICA EN TTS para escena {scene_idx + 1}: {error_msg}")
            
            # Diagnóstico específico
            if "400" in error_msg or "voice" in error_msg.lower() or "invalid" in error_msg.lower():
                logger.error(f"⚠️ La voz '{self.voice}' parece inválida. Revisa el nombre exacto.")
                logger.error(f"💡 Formato esperado: 'es-MX-JorgeNeural', 'es-MX-DaliaNeural', etc.")
                logger.error(f"💡 Ejecuta 'edge-tts --list-voices' para ver voces disponibles")
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                logger.error(f"⚠️ Error de conexión con Edge-TTS. Verifica tu conexión a internet.")
            elif "permission" in error_msg.lower() or "access" in error_msg.lower():
                logger.error(f"⚠️ Error de permisos al escribir en: {output_path_abs}")
                logger.error(f"💡 Verifica permisos de escritura en la carpeta.")
            else:
                logger.error(f"⚠️ Error desconocido: {error_msg}")
            
            # Log completo del error para debugging
            import traceback
            logger.debug(f"Traceback completo:\n{traceback.format_exc()}")
            
            return None
    
    async def generate_narration(self, scenes: List[Dict], output_dir: str = "assets/temp") -> List[str]:
        """
        Genera narraciones de audio para todas las escenas con logging detallado.
        
        Args:
            scenes: Lista de diccionarios de escenas con 'text'
            output_dir: Directorio de salida
        
        Returns:
            Lista de rutas de archivos de audio generados (None para fallos)
        """
        logger.info("=" * 60)
        logger.info(f"🎙️ Iniciando generación de narración con voz: {self.voice}")
        logger.info(f"⚙️ Velocidad: {self.rate}")
        logger.info(f"📂 Directorio de salida: {output_dir}")
        logger.info(f"📝 Total de escenas: {len(scenes)}")
        logger.info("=" * 60)
        
        # Asegurar que el directorio existe (con ruta absoluta)
        output_path = Path(output_dir).resolve()
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Directorio verificado: {output_path}")
        except Exception as e:
            logger.error(f"❌ Error creando directorio {output_path}: {e}")
            return []
        
        # Validar escenas y preparar tareas
        tasks = []
        scenes_with_text = 0
        for idx, scene in enumerate(scenes):
            text = scene.get("text", "").strip()
            if not text:
                logger.warning(f"⚠️ Escena {idx + 1} no tiene texto, saltando...")
                continue
            
            scenes_with_text += 1
            audio_file = output_path / f"audio_{idx}.mp3"
            task = self._generate_single_clip(text, str(audio_file), idx)
            tasks.append((idx, task, audio_file))
        
        if not tasks:
            logger.error("❌ No hay escenas con texto para generar audio.")
            return []
        
        logger.info(f"🎯 Escenas con texto válido: {scenes_with_text}/{len(scenes)}")
        logger.info(f"⚙️ Iniciando generación paralela de {len(tasks)} archivos de audio...")
        
        # Ejecutar todas las tareas en paralelo
        results = await asyncio.gather(*[task for _, task, _ in tasks], return_exceptions=True)
        
        # Procesar resultados con estadísticas detalladas
        audio_files = []
        successful = 0
        failed = 0
        
        for (idx, _, audio_file), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"❌ Excepción generando audio para escena {idx + 1}: {result}")
                failed += 1
                audio_files.append(None)
            elif result:
                # Verificar que el archivo existe y tiene contenido
                if Path(result).exists() and Path(result).stat().st_size > 0:
                    successful += 1
                    # Obtener duración del audio
                    try:
                        from moviepy.editor import AudioFileClip
                        clip = AudioFileClip(result)
                        duration = clip.duration
                        clip.close()
                        logger.success(f"✅ Escena {idx + 1}: Audio generado ({duration:.2f}s) - {Path(result).name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Escena {idx + 1}: Audio generado pero no se pudo leer duración: {e}")
                        logger.success(f"✅ Escena {idx + 1}: Audio generado - {Path(result).name}")
                    audio_files.append(result)
                else:
                    logger.error(f"❌ Escena {idx + 1}: Archivo generado pero está vacío o no existe: {result}")
                    failed += 1
                    audio_files.append(None)
            else:
                logger.error(f"❌ Escena {idx + 1}: No se generó audio (retornó None)")
                failed += 1
                audio_files.append(None)
        
        # Estadísticas finales
        logger.info("=" * 60)
        logger.info(f"📊 RESUMEN DE GENERACIÓN DE AUDIO:")
        logger.info(f"   ✅ Exitosos: {successful}/{len(tasks)}")
        logger.info(f"   ❌ Fallidos: {failed}/{len(tasks)}")
        logger.info("=" * 60)
        
        if successful == 0:
            logger.error("❌ CRÍTICO: No se generó ningún archivo de audio.")
            logger.error("💡 Posibles causas:")
            logger.error("   - La voz especificada no es válida")
            logger.error("   - Problemas de conexión con Edge-TTS")
            logger.error("   - Permisos de escritura en el directorio")
            logger.error("   - Todos los textos estaban vacíos")
        elif failed > 0:
            logger.warning(f"⚠️ Algunos archivos de audio fallaron ({failed}/{len(tasks)}). El video puede tener escenas sin audio.")
        
        # Calcular duración total de audios exitosos
        total_duration = 0.0
        valid_files = [f for f in audio_files if f and Path(f).exists()]
        for audio_file in valid_files:
            try:
                from moviepy.editor import AudioFileClip
                clip = AudioFileClip(audio_file)
                total_duration += clip.duration
                clip.close()
            except Exception as e:
                logger.debug(f"No se pudo leer duración de {audio_file}: {e}")
        
        if total_duration > 0:
            logger.success(f"⏱️ Duración total de audio generado: {total_duration:.2f}s ({total_duration/60:.2f} min)")
        
        return audio_files


def generate_narration_sync(scenes: List[Dict], voice: str = "es-MX-DaliaNeural", 
                           output_dir: str = "assets/temp") -> List[str]:
    """
    Versión síncrona de generate_narration para uso en código síncrono.
    
    Args:
        scenes: Lista de escenas con texto
        voice: Voz a usar
        output_dir: Directorio de salida
    
    Returns:
        Lista de rutas de archivos de audio
    """
    engine = AudioEngine(voice=voice)
    return asyncio.run(engine.generate_narration(scenes, output_dir))

