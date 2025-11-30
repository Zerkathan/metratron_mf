"""
NewsHunter: Investigador de noticias en tiempo real usando DuckDuckGo.
Proporciona noticias recientes para generar contenido viral basado en actualidad.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
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
        """Inicializa el investigador de noticias."""
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
    
    def get_latest_news(
        self,
        topic: str = "Technology",
        region: str = "wt-wt",
        max_results: int = 3,
        time_range: str = "d"  # d = día, w = semana, m = mes
    ) -> List[Dict[str, str]]:
        """
        Obtiene las noticias más recientes sobre un tema específico.
        
        Args:
            topic: Tema de búsqueda (ej: "Artificial Intelligence", "Cryptocurrency", "Football")
            region: Región para la búsqueda (wt-wt = mundial, es-es = España, mx-mx = México)
            max_results: Número máximo de noticias a retornar (default: 3)
            time_range: Rango de tiempo ('d' = día, 'w' = semana, 'm' = mes)
        
        Returns:
            Lista de diccionarios con 'title', 'snippet', 'url' y 'date'
        """
        if not self.ddgs:
            logger.error("❌ DuckDuckGo Search no está disponible")
            return []
        
        try:
            logger.info(f"🔍 Buscando noticias recientes sobre: '{topic}' (región: {region})...")
            
            # Construir query de búsqueda con filtro de tiempo
            search_query = f"{topic} news"
            
            # Buscar noticias recientes
            results = list(self.ddgs.news(
                keywords=search_query,
                region=region,
                safesearch='moderate',
                timelimit=time_range,
                max_results=max_results * 2  # Buscar más para filtrar los mejores
            ))
            
            if not results:
                logger.warning(f"⚠️ No se encontraron noticias sobre '{topic}'")
                return []
            
            logger.info(f"📰 Se encontraron {len(results)} resultados de noticias")
            
            # Filtrar y formatear los resultados más impactantes
            formatted_news = []
            for idx, result in enumerate(results[:max_results]):
                try:
                    title = result.get('title', '').strip()
                    snippet = result.get('body', '').strip()
                    url = result.get('url', '')
                    date = result.get('date', '')
                    
                    if not title:
                        continue
                    
                    # Limpiar snippet (eliminar HTML básico si existe)
                    if snippet:
                        snippet = snippet.replace('\n', ' ').strip()
                        # Limitar longitud del snippet
                        if len(snippet) > 200:
                            snippet = snippet[:200] + "..."
                    
                    formatted_news.append({
                        'title': title,
                        'snippet': snippet or "Sin descripción disponible",
                        'url': url,
                        'date': date,
                        'rank': idx + 1
                    })
                    
                    logger.debug(f"✅ Noticia {idx + 1}: {title[:60]}...")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando noticia {idx + 1}: {e}")
                    continue
            
            if formatted_news:
                logger.success(f"✅ Se obtuvieron {len(formatted_news)} noticias impactantes sobre '{topic}'")
            else:
                logger.warning(f"⚠️ No se pudieron formatear las noticias encontradas")
            
            return formatted_news
            
        except Exception as e:
            logger.error(f"❌ Error buscando noticias: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def format_news_for_prompt(self, news_list: List[Dict[str, str]]) -> str:
        """
        Formatea las noticias en un texto legible para inyectar en el prompt del LLM.
        
        Args:
            news_list: Lista de noticias obtenidas de get_latest_news()
        
        Returns:
            String formateado con las noticias para el prompt
        """
        if not news_list:
            return ""
        
        formatted_text = "\n📰 NOTICIAS RECIENTES ENCONTRADAS:\n"
        formatted_text += "=" * 60 + "\n\n"
        
        for news in news_list:
            formatted_text += f"🔹 {news['title']}\n"
            if news.get('snippet'):
                formatted_text += f"   {news['snippet']}\n"
            if news.get('url'):
                formatted_text += f"   Fuente: {news['url']}\n"
            formatted_text += "\n"
        
        formatted_text += "=" * 60 + "\n"
        formatted_text += "\n💡 INSTRUCCIÓN: Usa estas noticias REALES para crear un guion viral informativo.\n"
        
        return formatted_text
    
    def get_trending_topics(self, category: str = "technology", max_topics: int = 5) -> List[str]:
        """
        Obtiene temas trending para sugerir al usuario.
        
        Args:
            category: Categoría de temas (technology, business, sports, etc.)
            max_topics: Número máximo de temas a retornar
        
        Returns:
            Lista de temas trending
        """
        # Por ahora, retornamos temas predefinidos basados en la categoría
        # En el futuro, esto podría usar la API de DuckDuckGo para obtener trending real
        
        trending_map = {
            "technology": [
                "Artificial Intelligence",
                "ChatGPT",
                "Cryptocurrency",
                "Electric Vehicles",
                "Space Technology"
            ],
            "business": [
                "Stock Market",
                "Cryptocurrency",
                "Startups",
                "Tech Companies",
                "Economic News"
            ],
            "sports": [
                "Football",
                "Basketball",
                "Soccer",
                "Tennis",
                "Olympics"
            ],
            "general": [
                "Breaking News",
                "World News",
                "Politics",
                "Science",
                "Health"
            ]
        }
        
        topics = trending_map.get(category.lower(), trending_map["general"])
        return topics[:max_topics]




