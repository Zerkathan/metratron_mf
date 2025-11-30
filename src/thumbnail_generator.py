from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from moviepy.editor import VideoFileClip
from loguru import logger

DEFAULT_FONT_PATHS = [
    "assets/fonts/Impact.ttf",
    "assets/fonts/impact.ttf",
    "C:/Windows/Fonts/Impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


class ThumbnailMaker:
    """
    Generador de miniaturas con estilo viral (texto grande y contraste alto).
    """

    def __init__(self, thumbnails_dir: str = "output"):
        self.output_dir = Path(thumbnails_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_font(self, size: int = 80) -> ImageFont.FreeTypeFont:
        for font_path in DEFAULT_FONT_PATHS:
            path = Path(font_path)
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def extract_frame(self, video_path: str, time_percent: float = 0.5) -> Optional[Image.Image]:
        clip = None
        try:
            clip = VideoFileClip(video_path)
            
            # VALIDACIÓN: Verificar que el clip no es None
            if clip is None:
                logger.error(f"❌ VideoFileClip retornó None para: {video_path}")
                return None
            
            # VALIDACIÓN: Verificar que tiene los atributos necesarios
            if not hasattr(clip, 'duration') or not hasattr(clip, 'get_frame'):
                logger.error(f"❌ El clip no tiene los atributos necesarios: {video_path}")
                if clip:
                    try:
                        clip.close()
                    except:
                        pass
                return None
            
            duration = clip.duration or 1
            timestamp = max(0, min(duration, duration * time_percent))
            
            # VALIDACIÓN: Verificar que el clip sigue siendo válido antes de get_frame
            if clip is None:
                logger.error(f"❌ Clip es None antes de get_frame para: {video_path}")
                return None
            
            frame = clip.get_frame(timestamp)
            return Image.fromarray(frame)
        except Exception as exc:
            logger.error(f"No se pudo extraer frame para thumbnail: {exc}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
        finally:
            if clip:
                try:
                    clip.close()
                except:
                    pass

    def add_text_overlay(self, image: Image.Image, text: str) -> Image.Image:
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(1.2)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.1)

        draw = ImageDraw.Draw(image)
        width, height = image.size
        font = self._load_font(size=max(60, width // 12))

        message = text.upper()[:80] if text else "WATCH THIS"
        text_width, text_height = draw.textsize(message, font=font)

        x = (width - text_width) / 2
        y = height * 0.15

        for offset in range(4):
            draw.text((x - offset, y - offset), message, font=font, fill="black")
            draw.text((x + offset, y - offset), message, font=font, fill="black")
            draw.text((x - offset, y + offset), message, font=font, fill="black")
            draw.text((x + offset, y + offset), message, font=font, fill="black")

        draw.text((x, y), message, font=font, fill="#ffeb3b")
        return image

    def generate_thumbnail(self, video_path: str, hook_text: str, output_path: str) -> Optional[str]:
        frame = self.extract_frame(video_path)
        if frame is None:
            return None
        try:
            frame = self.add_text_overlay(frame, hook_text)
            frame.save(output_path, format="JPEG", quality=90)
            logger.info(f"Thumbnail generado: {output_path}")
            return output_path
        except Exception as exc:
            logger.error(f"No se pudo generar thumbnail: {exc}")
            return None








