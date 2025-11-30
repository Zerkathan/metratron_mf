import json
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


class ProfileManager:
    """
    Gestiona perfiles de configuración para múltiples canales/nichos.
    Cada perfil se almacena como un JSON dentro de la carpeta `profiles/`.
    """

    def __init__(self, profiles_dir: str = "profiles"):
        self.profiles_path = Path(profiles_dir)
        self.profiles_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"ProfileManager inicializado en {self.profiles_path.resolve()}")

    def _profile_file(self, name: str) -> Path:
        safe_name = name.lower().replace(" ", "_")
        return self.profiles_path / f"{safe_name}.json"

    def list_profiles(self) -> List[str]:
        profiles: List[str] = []
        for profile_file in self.profiles_path.glob("*.json"):
            profiles.append(profile_file.stem.replace("_", " ").title())
        profiles.sort()
        return profiles

    def load_profile(self, name: str) -> Optional[Dict]:
        profile_file = self._profile_file(name)
        if not profile_file.exists():
            logger.warning(f"Perfil no encontrado: {profile_file}")
            return None
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Perfil cargado: {name}")
            return data
        except json.JSONDecodeError as exc:
            logger.error(f"Perfil corrupto ({name}): {exc}")
            return None

    def save_profile(self, name: str, data: Dict):
        profile_file = self._profile_file(name)
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.success(f"Perfil guardado: {name} → {profile_file}")

    def delete_profile(self, name: str) -> bool:
        profile_file = self._profile_file(name)
        if profile_file.exists():
            profile_file.unlink()
            logger.info(f"Perfil eliminado: {name}")
            return True
        return False








