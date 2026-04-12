"""
Web Search Service for Article Context Enrichment.

Searches the web for related news to provide additional context
before generating articles from transcripts (video/audio).
Supports Serper.dev and Tavily AI as search providers.
"""

import os
import re
import json
import requests
from collections import Counter
from typing import Optional

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("web_search")


def buscar_en_internet(query: str, num_results: int = 5) -> str:
    """
    Busca información actualizada en internet usando Serper.dev o Tavily AI.

    Args:
        query: Término de búsqueda
        num_results: Número máximo de resultados (1-10)

    Returns:
        Texto formateado con resultados o mensaje de error
    """
    if not query or not query.strip():
        logger.warning("[WEB_SEARCH] Query vacía recibida")
        return "Query de búsqueda vacía"

    query = query.strip()
    num_results = min(max(1, num_results), 10)

    # Detectar API key disponible
    serper_key = Settings.SERPER_API_KEY
    tavily_key = Settings.TAVILY_API_KEY

    if not serper_key and not tavily_key:
        logger.warning("[WEB_SEARCH] No se encontró SERPER_API_KEY ni TAVILY_API_KEY")
        return ""  # Devuelve vacío para no bloquear el pipeline

    key = serper_key or tavily_key
    provider = "Serper.dev" if serper_key else "Tavily AI"

    logger.info(f"[WEB_SEARCH] Buscando → Provider: {provider}, Query: \"{query}\", Results: {num_results}")

    # Configurar request según proveedor
    if serper_key:
        url = "https://google.serper.dev/search"
        payload = {
            "q": query,
            "num": num_results,
            "gl": "us",
            "hl": "en"
        }
        headers = {
            'X-API-KEY': key,
            'Content-Type': 'application/json'
        }
    else:  # Tavily
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": key,
            "query": query,
            "search_depth": "advanced",
            "max_results": num_results,
            "include_answer": True,
            "include_images": False,
            "include_raw_content": False
        }
        headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)

        if response.status_code != 200:
            logger.error(f"[WEB_SEARCH] Error HTTP {response.status_code}: {response.text[:200]}")
            return ""

        data = response.json()
        resultado = f"=== INFORMACIÓN ENCONTRADA ({provider}) ===\n\n"

        # Procesar resultados según proveedor
        if serper_key and "organic" in data:
            items = data["organic"][:num_results]
        elif "results" in data:
            items = data["results"][:num_results]
            if data.get("answer"):
                resultado += f"RESUMEN: {data['answer']}\n\n"
        else:
            items = []

        if not items:
            return ""

        for i, item in enumerate(items, 1):
            title = item.get("title", "Sin título").strip()
            if serper_key:
                snippet = item.get("snippet", "Sin descripción").strip()
                link = item.get("link", "")
            else:
                snippet = item.get("content", "Sin descripción").strip()
                link = item.get("url", "")

            resultado += f"{i}. {title}\n"
            resultado += f"   {snippet}\n"
            resultado += f"   → {link}\n\n"

        logger.info(f"[WEB_SEARCH] {len(items)} resultados obtenidos")
        return resultado.strip()

    except requests.exceptions.Timeout:
        logger.error("[WEB_SEARCH] Timeout en búsqueda")
        return ""
    except requests.exceptions.ConnectionError:
        logger.error("[WEB_SEARCH] Error de conexión")
        return ""
    except Exception as e:
        logger.error(f"[WEB_SEARCH] Error inesperado: {e}")
        return ""


def extraer_palabras_clave(texto: str, max_palabras: int = 5) -> list[str]:
    """
    Extrae las palabras más relevantes de un texto para usar como query.
    """
    stopwords = {
        "el", "la", "los", "las", "de", "en", "y", "que", "es", "son",
        "se", "un", "una", "unos", "unas", "con", "por", "para", "sin",
        "sobre", "bajo", "entre", "hacia", "desde", "esta", "este", "estos",
        "the", "and", "for", "are", "but", "not", "you", "all", "can",
        "her", "was", "one", "our", "out", "has", "have", "been", "from",
        "también", "puede", "tiene", "hace", "dice", "como", "cuando",
    }

    palabras = texto.lower().split()
    palabras_filtradas = [p for p in palabras if len(p) > 4 and p not in stopwords and p.isalpha()]

    contador = Counter(palabras_filtradas)
    return [palabra for palabra, _ in contador.most_common(max_palabras)]


def extraer_entidades(texto: str) -> list[str]:
    """
    Extrae nombres propios, lugares y organizaciones del texto.
    """
    entidades = []

    # Nombres propios (palabras que empiezan con mayúscula)
    nombres_propios = re.findall(r'\b[A-Z][a-z]{2,}\b', texto)
    articulos = {"El", "La", "Los", "Las", "Un", "Una", "De", "En", "Por", "Para"}
    nombres_filtrados = [n for n in nombres_propios if n not in articulos]
    entidades.extend(nombres_filtrados[:3])

    # Lugares y organizaciones conocidas
    lugares_orgs = [
        "Rusia", "Ucrania", "Estados Unidos", "EEUU", "China", "Europa", "OTAN", "ONU",
        "Washington", "Moscú", "Kiev", "Trump", "Biden", "Putin", "Zelensky", "UE",
        "Casa Blanca", "Kremlin", "Congreso", "Senado", "Gobierno", "Irán", "Israel",
        "Oriente Medio", "Hamas", "Gaza", "Cisjordania", "Pentágono", "Naciones Unidas",
    ]

    texto_lower = texto.lower()
    for lugar in lugares_orgs:
        if lugar.lower() in texto_lower and lugar not in entidades:
            entidades.append(lugar)

    return list(set(entidades))[:4]


def generar_query(transcripcion: str) -> str:
    """
    Genera una query de búsqueda optimizada a partir de una transcripción.
    Combina entidades nombradas + palabras clave.
    """
    contenido = transcripcion[:1500]  # Limitar para eficiencia

    # Extraer elementos
    entidades = extraer_entidades(contenido)
    keywords = extraer_palabras_clave(contenido, max_palabras=3)

    # Combinar para crear query
    elementos = entidades[:2] + keywords[:3]

    if len(elementos) < 2:
        # Fallback: usar palabras más largas
        palabras = re.findall(r'\b[a-záéíóúñ]{6,}\b', contenido.lower())
        elementos = list(set(palabras))[:3]

    if not elementos:
        return ""

    query = " ".join(elementos[:4])
    return query


def enriquecer_con_contexto(transcripcion: str, tema: str = "") -> Optional[str]:
    """
    Busca noticias relacionadas con la transcripción y devuelve contexto formateado.

    Args:
        transcripcion: Texto de la transcripción del video/audio
        tema: Tema o categoría del contenido

    Returns:
        Contexto web formateado como string, o None si no hay resultados
    """
    if not transcripcion or len(transcripcion) < 100:
        logger.debug("[WEB_SEARCH] Transcripción demasiado corta para enriquecer")
        return None

    # Generar query de búsqueda
    query = generar_query(transcripcion)
    if not query:
        return None

    # Añadir tema si está disponible
    if tema:
        query = f"{query} {tema}"

    logger.info(f"[WEB_SEARCH] Enriqueciendo artículo con búsqueda: '{query}'")

    # Ejecutar búsqueda
    resultados = buscar_en_internet(query, num_results=5)

    if resultados:
        logger.info(f"[WEB_SEARCH] Contexto obtenido: {len(resultados)} chars")
        return resultados
    else:
        logger.debug("[WEB_SEARCH] Sin resultados de búsqueda")
        return None
