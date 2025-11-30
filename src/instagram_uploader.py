import json
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from instagrapi import Client
    from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired, PleaseWaitFewMinutes
    INSTAGRAPI_AVAILABLE = True
except ImportError as exc:  # pragma: no cover - solo para entorno sin dependencia
    Client = None  # type: ignore
    ChallengeRequired = TwoFactorRequired = PleaseWaitFewMinutes = Exception  # type: ignore
    INSTAGRAPI_AVAILABLE = False
    INSTAGRAPI_ERROR = exc


class InstagramUploader:
    """
    Maneja la autenticación y subida de Reels con instagrapi.
    Guarda la sesión en disco para evitar bloqueos por logins repetitivos.
    """

    def __init__(self, username: str, password: str, session_path: str = "ig_session.json"):
        if not INSTAGRAPI_AVAILABLE:
            raise ImportError(
                "instagrapi no está instalado. Ejecuta 'pip install instagrapi pillow' para habilitar cargas a Instagram."
            ) from INSTAGRAPI_ERROR
        self.username = username
        self.password = password
        self.session_path = Path(session_path)
        self.client = Client()
        self.logged_in = False

    def clear_session(self):
        if self.session_path.exists():
            self.session_path.unlink()
            logger.info("Sesión local de Instagram eliminada.")

    def _load_session(self) -> bool:
        if not self.session_path.exists():
            return False
        try:
            settings = json.loads(self.session_path.read_text(encoding="utf-8"))
            self.client.set_settings(settings)
            self.client.login(self.username, self.password)
            self.logged_in = True
            logger.success("Sesión de Instagram restaurada desde archivo.")
            return True
        except Exception as exc:
            logger.warning(f"No se pudo restaurar la sesión de Instagram: {exc}. Se intentará login limpio.")
            self.clear_session()
            return False

    def login(self, verification_code: Optional[str] = None):
        if self.logged_in:
            return

        if self._load_session():
            return

        try:
            logger.info("Iniciando sesión en Instagram...")
            if verification_code:
                self.client.login(self.username, self.password, verification_code=verification_code)
            else:
                self.client.login(self.username, self.password)
            self.session_path.write_text(json.dumps(self.client.get_settings()), encoding="utf-8")
            self.logged_in = True
            logger.success("Login en Instagram exitoso.")
        except TwoFactorRequired as exc:
            raise RuntimeError(
                "Instagram requiere código 2FA. Genera el código en tu app y vuelve a intentar."
            ) from exc
        except ChallengeRequired as exc:
            raise RuntimeError(
                "Instagram solicitó verificación adicional (checkpoint). Autoriza el acceso desde la app y vuelve a intentar."
            ) from exc
        except PleaseWaitFewMinutes as exc:
            raise RuntimeError("Instagram está limitando los logins. Espera unos minutos antes de reintentar.") from exc
        except Exception as exc:
            raise RuntimeError(f"No se pudo iniciar sesión en Instagram: {exc}") from exc

    def upload_reel(self, video_path: str, caption: str, cover_path: Optional[str] = None):
        if not self.logged_in:
            self.login()

        try:
            logger.info("Subiendo Reel a Instagram...")
            kwargs = {}
            if cover_path:
                kwargs["thumbnail"] = Path(cover_path)
            media = self.client.clip_upload(Path(video_path), caption, **kwargs)
            logger.success("Reel publicado correctamente.")
            return media
        except Exception as exc:
            raise RuntimeError(f"Error subiendo Reel a Instagram: {exc}") from exc

