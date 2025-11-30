"""
NewsHunter: Cazador de noticias en tiempo real usando DuckDuckGo Search.
Búsqueda gratuita sin API Key para generar contenido basado en actualidad.
"""

from typing import Optional
from loguru import logger

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logger.warning("⚠️ duckduckgo-search no está instalado. El modo de noticias no funcionará.")
    logger.info("💡 Instala con: pip install duckduckgo-search")


class NewsHunter:
    """
    Cazador de noticias en tiempo real para generar contenido basado en actualidad.
    """
    
    def __init__(self):
        """Inicializa el cazador de noticias."""
        self.ddgs = None
        if DDGS_AVAILABLE:
            try:
                self.ddgs = DDGS()
                logger.success("✅ NewsHunter inicializado correctamente")
            except Exception as e:
                logger.error(f"❌ Error inicializando DuckDuckGo Search: {e}")
                self.ddgs = None
        else:
            logger.warning("⚠️ NewsHunter no disponible: duckduckgo-search no está instalado")
    
    def get_trends(self, topic: str, max_results: int = 3) -> str:
        """
        Obtiene tendencias y noticias actuales sobre un tema (News Jacking).
        Usa DuckDuckGo Search para buscar noticias del último día.
        
        Args:
            topic: Tema de búsqueda (ej: "IA", "Bitcoin", "Tecnología")
            max_results: Número máximo de noticias a retornar (default: 3)
        
        Returns:
            String formateado con las noticias para que la IA lo lea:
            "Noticia 1: [Título] - [Resumen]\nNoticia 2:..."
        """
        if not self.ddgs:
            logger.error("❌ DuckDuckGo Search no está disponible")
            return ""
        
        try:
            logger.info(f"🔍 Buscando tendencias sobre: '{topic}' (últimas 24 horas)...")
            
            # Buscar noticias del último día usando DDGS().text()
            # El parámetro timelimit='d' es vital (significa "último día")
            results = list(self.ddgs.text(
                keywords=topic,
                region='wt-wt',  # Mundial
                safesearch='off',  # Sin filtro de seguridad para obtener más resultados
                timelimit='d'  # Último día - VITAL para News Jacking
            ))
            
            if not results:
                logger.warning(f"⚠️ No se encontraron noticias sobre '{topic}'")
                return ""
            
            logger.info(f"📰 Se encontraron {len(results)} resultados")
            
            # Formatear los resultados más relevantes en texto limpio para la IA
            formatted_news = []
            for idx, result in enumerate(results[:max_results], 1):
                try:
                    title = result.get('title', '').strip()
                    body = result.get('body', '').strip()
                    
                    if not title:
                        continue
                    
                    # Limpiar y truncar el cuerpo si es muy largo
                    if body:
                        # Eliminar saltos de línea y espacios múltiples
                        body = ' '.join(body.split())
                        # Limitar a 200 caracteres para mantener el prompt limpio
                        if len(body) > 200:
                            body = body[:200] + "..."
                    else:
                        body = "Sin resumen disponible"
                    
                    formatted_news.append(f"Noticia {idx}: {title} - {body}")
                    logger.debug(f"✅ Noticia {idx} procesada: {title[:60]}...")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando noticia {idx}: {e}")
                    continue
            
            if formatted_news:
                result_text = "\n".join(formatted_news)
                logger.success(f"✅ Se obtuvieron {len(formatted_news)} noticias sobre '{topic}'")
                return result_text
            else:
                logger.warning(f"⚠️ No se pudieron formatear las noticias encontradas")
                return ""
            
        except Exception as e:
            logger.error(f"❌ Error buscando tendencias: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return ""
    
    def get_news(self, topic: str, max_results: int = 3) -> str:
        """
        Alias para get_trends() para mantener compatibilidad.
        Obtiene noticias recientes sobre un tema específico.
        
        Args:
            topic: Tema de búsqueda (ej: "Inteligencia Artificial", "Bitcoin", "Real Madrid")
            max_results: Número máximo de noticias a retornar (default: 3)
        
        Returns:
            String formateado con las noticias: "Noticia 1: [Título] - [Resumen]\nNoticia 2:..."
        """
        return self.get_trends(topic, max_results)


