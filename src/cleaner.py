import os
import shutil
import time
from pathlib import Path
from typing import Optional

from loguru import logger


class DiskCleaner:
    """
    Utilidad para mantener limpias las carpetas temporales y de salida.
    """

    def __init__(self, temp_dir: str = "assets/temp", output_dir: str = "output", archive_dir: str = "archive"):
        self.temp_path = Path(temp_dir)
        self.output_path = Path(output_dir)
        self.archive_path = Path(archive_dir)
        self.archive_path.mkdir(parents=True, exist_ok=True)

    def clean_temp_folder(self, max_age_minutes: int = 30) -> float:
        """
        Elimina archivos antiguos en assets/temp y devuelve los MB liberados.
        """
        if not self.temp_path.exists():
            return 0.0

        cutoff = time.time() - (max_age_minutes * 60)
        bytes_freed = 0

        for root, _, files in os.walk(self.temp_path):
            for name in files:
                file_path = Path(root) / name
                if file_path.suffix.lower() not in {".mp4", ".mp3", ".wav", ".png", ".json"}:
                    continue
                try:
                    stat = file_path.stat()
                    if stat.st_mtime > cutoff:
                        continue
                    size = stat.st_size
                    try:
                        file_path.unlink()
                        bytes_freed += size
                    except (PermissionError, OSError) as exc:
                        logger.debug(f"No se pudo eliminar {file_path}: {exc}")
                except FileNotFoundError:
                    continue

        return round(bytes_freed / (1024 * 1024), 2)

    def archive_outputs(self, days_to_keep: int = 7):
        """
        Mueve videos antiguos a la carpeta archive para liberar la carpeta principal.
        """
        if not self.output_path.exists():
            return

        cutoff = time.time() - (days_to_keep * 86400)

        for file in self.output_path.glob("*.mp4"):
            try:
                if file.stat().st_mtime < cutoff:
                    destination = self.archive_path / file.name
                    shutil.move(str(file), destination)
                    logger.info(f"Archivo archivado: {file.name}")
            except (PermissionError, OSError) as exc:
                logger.warning(f"No se pudo archivar {file}: {exc}")








