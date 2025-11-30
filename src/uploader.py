"""
Módulo de Upload para YouTube y TikTok
Gestiona la subida automática de videos a plataformas sociales
"""

import os
import pickle
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from loguru import logger

# YouTube imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    logger.warning("⚠️ google-auth-oauthlib o google-api-python-client no instalados. YouTube upload deshabilitado.")

# TikTok imports
TIKTOK_AVAILABLE = False
try:
    # Intentar diferentes formas de importar según la versión
    try:
        from tiktok_uploader.upload import upload_video
    except ImportError:
        try:
            from tiktok_uploader import upload_video
        except ImportError:
            try:
                import tiktok_uploader
                upload_video = tiktok_uploader.upload_video
            except ImportError:
                raise ImportError("tiktok-uploader no disponible")
    TIKTOK_AVAILABLE = True
except ImportError:
    TIKTOK_AVAILABLE = False
    logger.warning("⚠️ tiktok-uploader no instalado. TikTok upload deshabilitado.")


# YouTube API scopes necesarios
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


class YouTubeUploader:
    """
    Clase para gestionar la subida de videos a YouTube usando OAuth2.
    
    Attributes:
        service: Servicio de YouTube API autenticado
        credentials: Credenciales OAuth2
    """
    
    def __init__(self, client_secret_path: str = "client_secret.json", token_path: str = "token.pickle"):
        """
        Inicializa el uploader de YouTube y maneja la autenticación OAuth2.
        
        Args:
            client_secret_path: Ruta al archivo client_secret.json de Google Cloud
            token_path: Ruta donde se guardará/cargará el token OAuth2
        
        Raises:
            FileNotFoundError: Si client_secret.json no existe
            ValueError: Si las credenciales son inválidas
        """
        if not YOUTUBE_AVAILABLE:
            raise ImportError("❌ Dependencias de YouTube no instaladas. Ejecuta: pip install google-auth-oauthlib google-api-python-client")
        
        self.client_secret_path = Path(client_secret_path)
        self.token_path = Path(token_path)
        self.service = None
        self.credentials = None
        
        # Verificar que existe client_secret.json
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"❌ No se encontró {client_secret_path}. "
                f"Asegúrate de colocar el archivo client_secret.json en la raíz del proyecto."
            )
        
        # Autenticación
        self._authenticate()
    
    def _authenticate(self):
        """
        Gestiona la autenticación OAuth2 con YouTube API.
        - Si existe token.pickle válido, lo usa
        - Si no existe o está expirado, abre el navegador para autenticación
        """
        creds = None
        
        # Intentar cargar token existente
        if self.token_path.exists():
            try:
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
                    logger.info(f"✅ Token cargado desde {self.token_path}")
            except Exception as e:
                logger.warning(f"⚠️ Error cargando token: {e}")
        
        # Si no hay credenciales válidas, autenticar
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("🔄 Token expirado, refrescando...")
                try:
                    creds.refresh(Request())
                    logger.success("✅ Token refrescado exitosamente")
                except Exception as e:
                    logger.error(f"❌ Error refrescando token: {e}")
                    creds = None
            
            if not creds:
                logger.info("🌐 Abriendo navegador para autenticación OAuth2...")
                logger.info("💡 Acepta los permisos en el navegador que se abrirá.")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.client_secret_path),
                        SCOPES
                    )
                    creds = flow.run_local_server(port=0, open_browser=True)
                    logger.success("✅ Autenticación OAuth2 completada")
                except Exception as e:
                    logger.error(f"❌ Error en autenticación OAuth2: {e}")
                    raise ValueError(f"Error en autenticación: {e}")
            
            # Guardar credenciales para la próxima vez
            try:
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
                logger.info(f"✅ Token guardado en {self.token_path}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo guardar el token: {e}")
        
        self.credentials = creds
        
        # Construir el servicio de YouTube
        try:
            self.service = build('youtube', 'v3', credentials=creds)
            logger.success("✅ Servicio de YouTube API inicializado correctamente")
        except Exception as e:
            logger.error(f"❌ Error construyendo servicio de YouTube: {e}")
            raise ValueError(f"Error inicializando servicio de YouTube: {e}")
    
    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str = "",
        privacy: str = "private",
        tags: Optional[list] = None,
        category_id: str = "22"  # People & Blogs por defecto
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Sube un video a YouTube.
        
        Args:
            file_path: Ruta al archivo de video a subir
            title: Título del video
            description: Descripción del video (opcional)
            privacy: Privacidad del video ("private", "unlisted", "public")
            tags: Lista de tags para el video (opcional)
            category_id: ID de categoría de YouTube (22 = People & Blogs)
        
        Returns:
            Tuple[bool, str, Optional[str]]: 
                - (True, "Video subido exitosamente", video_id) si tuvo éxito
                - (False, mensaje_de_error, None) si falló
        """
        if not self.service:
            return False, "❌ Servicio de YouTube no inicializado. Autenticación fallida.", None
        
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return False, f"❌ El archivo no existe: {file_path}", None
        
        try:
            logger.info(f"📤 Subiendo video a YouTube: {file_path_obj.name}")
            logger.info(f"   Título: {title}")
            logger.info(f"   Privacidad: {privacy}")
            
            # Preparar metadata del video
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': privacy,
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Crear objeto MediaFileUpload
            media = MediaFileUpload(
                str(file_path_obj.absolute()),
                chunksize=-1,
                resumable=True,
                mimetype='video/*'
            )
            
            # Insertar el video
            insert_request = self.service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Subir con retry automático
            response = self._resumable_upload(insert_request)
            
            if response:
                video_id = response.get('id')
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.success(f"✅ Video subido exitosamente a YouTube!")
                logger.info(f"   ID: {video_id}")
                logger.info(f"   URL: {video_url}")
                return True, f"✅ Video subido exitosamente. URL: {video_url}", video_id
            else:
                return False, "❌ Error desconocido al subir el video", None
                
        except HttpError as e:
            error_msg = f"❌ Error HTTP de YouTube API: {e.resp.status} - {e.content.decode()}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"❌ Error inesperado subiendo video: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.debug(f"Traceback:\n{traceback.format_exc()}")
            return False, error_msg, None
    
    def _resumable_upload(self, insert_request):
        """
        Maneja la subida resumible de archivos grandes.
        
        Args:
            insert_request: Request de inserción de YouTube API
        
        Returns:
            Response del API o None si falla
        """
        response = None
        error = None
        retry = 0
        max_retries = 10
        
        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        return response
                    else:
                        raise ValueError(f"La subida falló. Respuesta: {response}")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    error = f"Error {e.resp.status} retryable. Reintentando..."
                    logger.warning(error)
                    retry += 1
                    if retry >= max_retries:
                        raise ValueError(f"Max retries alcanzado. Último error: {error}")
                    time.sleep(2 ** retry)  # Backoff exponencial
                else:
                    raise
            except Exception as e:
                raise ValueError(f"Error inesperado: {str(e)}")
        
        return response


class TikTokUploader:
    """
    Clase para gestionar la subida de videos a TikTok usando tiktok-uploader.
    
    Nota: TikTok requiere cookies de sesión para autenticación.
    """
    
    def __init__(self):
        """
        Inicializa el uploader de TikTok.
        
        Raises:
            ImportError: Si tiktok-uploader no está instalado
        """
        if not TIKTOK_AVAILABLE:
            raise ImportError(
                "❌ tiktok-uploader no instalado. "
                "Ejecuta: pip install tiktok-uploader"
            )
        logger.info("✅ TikTokUploader inicializado")
    
    def upload_video(
        self,
        file_path: str,
        description: str = "",
        cookies_path: str = "tiktok_cookies.txt",
        schedule_time: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Sube un video a TikTok.
        
        Args:
            file_path: Ruta al archivo de video a subir
            description: Descripción del video (caption)
            cookies_path: Ruta al archivo de cookies de TikTok (Netscape format)
            schedule_time: Timestamp Unix para programar publicación (opcional)
        
        Returns:
            Tuple[bool, str]:
                - (True, "Video subido exitosamente") si tuvo éxito
                - (False, mensaje_de_error) si falló
        
        Nota:
            Para obtener las cookies:
            1. Inicia sesión en TikTok en tu navegador
            2. Usa una extensión como "EditThisCookie" o "Cookie-Editor"
            3. Exporta las cookies en formato Netscape
            4. Guárdalas en tiktok_cookies.txt
        """
        file_path_obj = Path(file_path)
        cookies_path_obj = Path(cookies_path)
        
        # Verificar que existe el archivo de video
        if not file_path_obj.exists():
            return False, f"❌ El archivo no existe: {file_path}"
        
        # Verificar que existen las cookies
        if not cookies_path_obj.exists():
            return False, (
                f"❌ Archivo de cookies no encontrado: {cookies_path}\n"
                f"💡 Para obtener las cookies:\n"
                f"   1. Inicia sesión en TikTok en tu navegador\n"
                f"   2. Exporta las cookies con una extensión (EditThisCookie, Cookie-Editor)\n"
                f"   3. Guárdalas en formato Netscape en: {cookies_path}"
            )
        
        try:
            logger.info(f"📤 Subiendo video a TikTok: {file_path_obj.name}")
            logger.info(f"   Descripción: {description[:50]}...")
            
            # Usar tiktok-uploader para subir
            # Nota: La librería puede tener diferentes APIs, ajustar según versión
            try:
                # Intentar llamada con todos los parámetros
                success = upload_video(
                    file_path=str(file_path_obj.absolute()),
                    description=description,
                    cookies_path=str(cookies_path_obj.absolute()),
                    schedule_time=schedule_time
                )
            except TypeError:
                # Si falla, intentar sin schedule_time
                try:
                    success = upload_video(
                        file_path=str(file_path_obj.absolute()),
                        description=description,
                        cookies_path=str(cookies_path_obj.absolute())
                    )
                except TypeError:
                    # Último intento: solo path y description
                    success = upload_video(
                        str(file_path_obj.absolute()),
                        description
                    )
            
            if success:
                logger.success(f"✅ Video subido exitosamente a TikTok!")
                return True, "✅ Video subido exitosamente a TikTok"
            else:
                return False, "❌ Error desconocido al subir el video a TikTok"
                
        except Exception as e:
            error_msg = f"❌ Error subiendo video a TikTok: {str(e)}"
            logger.error(error_msg)
            
            # Diagnóstico común
            if "cookies" in str(e).lower() or "auth" in str(e).lower():
                error_msg += (
                    "\n💡 Tip: Las cookies pueden haber expirado. "
                    "Exporta nuevas cookies desde tu navegador."
                )
            
            import traceback
            logger.debug(f"Traceback:\n{traceback.format_exc()}")
            return False, error_msg

