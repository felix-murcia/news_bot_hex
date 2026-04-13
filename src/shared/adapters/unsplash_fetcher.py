import os
import requests
import random
import re
from dotenv import load_dotenv

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot")

load_dotenv(override=True)

UNSPLASH_ACCESS_KEY = Settings.UNSPLASH_ACCESS_KEY
if not UNSPLASH_ACCESS_KEY:
    logger.warning("[UNSPLASH] Missing UNSPLASH_ACCESS_KEY in .env")

UNSPLASH_API = Settings.UNSPLASH_API_URL

UNSPLASH_SYNONYMS = {
    "protesta": ["manifestación", "reclamo", "activismo"],
    "tecnología": ["innovación", "dispositivo", "futuro"],
    "guerra": ["conflicto", "militar", "soldado"],
    "economía": ["finanzas", "mercado", "dinero"],
    "clima": ["medio ambiente", "naturaleza", "tormenta"],
    "salud": ["hospital", "médico", "enfermedad"],
    "educación": ["escuela", "estudiante", "aula"],
    "política": ["gobierno", "elecciones", "parlamento"],
    "energía": ["electricidad", "solar", "infraestructura"],
    "crimen": ["policía", "justicia", "investigación"],
}


# ============================================================
# Nuevo sistema de generación de queries para imágenes
# ============================================================

STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "en", "y", "o",
    "que", "es", "son", "se", "con", "por", "para", "sin", "sobre", "bajo", "entre",
    "hacia", "desde", "esta", "este", "estos", "estas", "ese", "esa", "esos", "esas",
    "aquel", "aquella", "como", "cuando", "donde", "más", "pero", "si", "no", "ya",
    "también", "muy", "todo", "todos", "todas", "al", "lo", "le", "les", "su", "sus",
    "ser", "estar", "hay", "tener", "hacer", "decir", "poder", "deber", "querer",
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "shall", "it", "its", "this", "that", "these", "those", "not", "no",
}


def clean_title(title: str) -> str:
    """Limpia el título de palabras sensacionalistas y caracteres especiales."""
    title = re.sub(r"\b(LIVE|BREAKING|UPDATE|EXCLUSIVE|URGENT)\b[:\-–]*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[^\w\sáéíóúñü]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def extraer_entidades_imagen(texto: str, max_entidades: int = 4) -> list:
    """
    Extrae entidades relevantes para búsqueda de imágenes.
    Prioriza nombres propios, lugares y conceptos visuales.
    """
    entidades = []

    # 1. Nombres propios (palabras que empiezan con mayúscula, >2 letras)
    #    Excluir palabras vacías en inglés que suelen ir capitalizadas
    articulos = {
        "El", "La", "Los", "Las", "Un", "Una", "De", "En", "Por", "Para", "Con", "Sin",
        "The", "And", "For", "Of", "In", "To", "Is", "Are", "Was", "Were", "Be", "Been",
        "Have", "Has", "Had", "Do", "Does", "Did", "Will", "Would", "Could", "Should",
        "From", "With", "By", "At", "Or", "But", "Not", "You", "All", "Can", "Her",
        "Was", "One", "Our", "Out", "Has", "This", "That", "These", "Those", "It",
        "Hours", "Before", "News", "After", "What", "When", "Where", "Why", "How",
    }
    nombres_propios = re.findall(r'\b[A-Z][a-záéíóúñü]{2,}\b', texto)
    nombres_filtrados = [n for n in nombres_propios if n not in articulos]
    entidades.extend(nombres_filtrados[:3])

    # 2. Lugares y organizaciones conocidas (visualmente reconocibles)
    lugares_visuales = [
        "Rusia", "Ucrania", "Estados Unidos", "Washington", "Moscú", "Kiev",
        "China", "Pekín", "Europa", "Irán", "Teherán", "Israel", "Jerusalén",
        "Gaza", "Oriente Medio", "Casa Blanca", "Kremlin", "Pentágono",
        "OTAN", "ONU", "Naciones Unidas", "Congreso", "Parlamento",
    ]
    texto_lower = texto.lower()
    for lugar in lugares_visuales:
        if lugar.lower() in texto_lower and lugar not in entidades:
            entidades.append(lugar)

    # 3. Conceptos visuales específicos (eventos, objetos, lugares)
    conceptos_visuales = [
        "refinería", "fábrica", "edificio", "iglesia", "catedral", "mezquita",
        "manifestación", "protesta", "marcha", "conferencia", "cumbre", "reunión",
        "hospital", "escuela", "universidad", "estadio", "puerto", "aeropuerto",
        "misil", "cohetes", "tanque", "avión", "barco", "submarino",
        "presidente", "ministro", "papa", "pope", "líder", "general",
        "terremoto", "inundación", "incendio", "tormenta", "huracán",
    ]
    for concepto in conceptos_visuales:
        if concepto in texto_lower and concepto not in [e.lower() for e in entidades]:
            entidades.append(concepto.capitalize())
            if len(entidades) >= max_entidades:
                break

    return list(dict.fromkeys(entidades))[:max_entidades]


def extraer_concepto_visual_principal(texto: str):
    """
    Extrae el concepto visual principal del texto.
    Retorna una palabra que represente mejor la imagen buscada.
    """
    texto_lower = texto.lower()

    eventos_visuales = {
        "manifestación": "protest",
        "protesta": "protest",
        "marcha": "march",
        "reunión": "meeting",
        "cumbre": "summit",
        "conferencia": "conference",
        "ataque": "conflict",
        "guerra": "war",
        "conflicto": "conflict",
        "terremoto": "earthquake",
        "inundación": "flood",
        "incendio": "fire",
        "elección": "election",
        "elecciones": "election",
    }

    for palabra, concepto in eventos_visuales.items():
        if palabra in texto_lower:
            return concepto

    return None


def generar_query_imagen(title: str, content: str = "", theme: str = "") -> str:
    """
    Genera una query optimizada para búsqueda de imágenes.

    Estrategia:
    1. Extraer entidades (nombres propios, lugares, conceptos visuales)
    2. Identificar el concepto visual principal
    3. Combinar de forma coherente, evitando palabras vacías o abstractas
    4. Limitar a 3-4 elementos máximo para precisión
    """
    # Limpiar título
    clean = clean_title(title)

    # Combinar título y contenido para análisis (primeros 300 chars del contenido)
    texto_completo = f"{clean} {content[:300]}" if content else clean

    # Extraer entidades
    entidades = extraer_entidades_imagen(texto_completo, max_entidades=4)

    # Extraer concepto visual principal
    concepto_principal = extraer_concepto_visual_principal(texto_completo)

    # Construir query
    query_parts = []

    # 1. Añadir concepto visual si existe (prioridad máxima)
    if concepto_principal:
        query_parts.append(concepto_principal)

    # 2. Añadir entidades que sean visualmente descriptivas
    #    Filtrar palabras abstractas o verbos que no son buenos para imágenes
    palabras_no_visuales = {
        "accelerate", "demand", "claim", "state", "say", "tell", "report",
        "announce", "declare", "propose", "consider", "discuss", "analyze",
        "acelerar", "demandar", "afirmar", "decir", "informar", "anunciar",
        "declarar", "proponer", "considerar", "discutir", "analizar",
        "strong", "issues", "rebuke", "criticism", "decision", "action",
        "fuerte", "crítica", "decisión", "acción", "cuestión", "tema",
    }
    if entidades:
        entidades_visuales = [
            e for e in entidades[:3]
            if e.lower() not in palabras_no_visuales
        ]
        query_parts.extend(entidades_visuales)

    # Si no hay entidades ni concepto, usar palabras significativas del título
    if not query_parts:
        palabras = re.findall(r'\b[a-záéíóúñü]{4,}\b', clean.lower())
        palabras_filtradas = [p for p in palabras if p not in STOPWORDS]
        query_parts = palabras_filtradas[:3]

    # Si todavía está vacío, fallback al tema
    if not query_parts and theme:
        return theme.lower()

    # Unir y limitar longitud
    query = " ".join(query_parts[:4])
    return query[:100]


def enrich_image_query(title: str, theme: str = None, content: str = None) -> str:
    """
    Wrapper para mantener compatibilidad con código antiguo.
    Usa la nueva función generar_query_imagen.
    """
    return generar_query_imagen(title, content or "", theme or "")


def fallback_unsplash_query(query: str) -> str:
    keyword = query.lower().split()[0]
    fallback_terms = UNSPLASH_SYNONYMS.get(keyword, [])
    location_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", query)
    location = location_match.group(1) if location_match else ""
    if fallback_terms:
        alt_term = random.choice(fallback_terms)
        return f"{alt_term} {location}".strip()
    elif location:
        return location
    else:
        return "noticia"


def search_unsplash(query: str, used_ids: set) -> dict | None:
    if not UNSPLASH_ACCESS_KEY:
        return None

    def fetch(q):
        try:
            headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
            params = {"query": q, "per_page": 30, "orientation": "landscape"}
            resp = requests.get(
                UNSPLASH_API, headers=headers, params=params, timeout=15
            )
            if resp.status_code != 200:
                logger.warning(f"[UNSPLASH] API error: {resp.status_code}")
                return None
            data = resp.json().get("results", [])
            for img in data:
                img_id = img.get("id")
                if img_id and img_id not in used_ids:
                    urls = img.get("urls", {})
                    return {
                        "id": img_id,
                        "url": urls.get("raw"),
                        "full_url": urls.get("full"),
                        "regular_url": urls.get("regular"),
                        "small_url": urls.get("small"),
                        "thumb_url": urls.get("thumb"),
                        "description": img.get("description")
                        or img.get("alt_description", ""),
                        "user": img.get("user", {}).get("name", ""),
                    }
            return None
        except Exception as e:
            logger.warning(f"[UNSPLASH] Error: {e}")
            return None

    result = fetch(query)
    if result:
        return result
    alt_query = fallback_unsplash_query(query)
    return fetch(alt_query)


def get_used_ids() -> set:
    try:
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        coll = db["used_unsplash_ids"]
        return set(doc.get("id") for doc in coll.find({}, {"id": 1}))
    except:
        return set()


def add_used_id(img_id: str):
    try:
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        coll = db["used_unsplash_ids"]
        coll.update_one({"id": img_id}, {"$set": {"id": img_id}}, upsert=True)
    except:
        pass


class UnsplashFetcher:
    def __init__(self, mode: str = "news"):
        self.mode = mode

    def fetch_for_posts(self, posts: list) -> list:
        changed = 0
        used_ids = get_used_ids()
        fallback_url = Settings.WP_DEFAULT_IMAGE_URL

        for post in posts:
            if post.get("unsplash_image"):
                continue

            current_image = post.get("image_url", "")
            if current_image and current_image != fallback_url:
                continue

            title = post.get("title", "") or post.get("tweet", "")
            if not title:
                continue

            # Get theme if available for better query enrichment
            theme = post.get("tema") or post.get("theme") or post.get("category")
            content = post.get("content") or post.get("article") or ""

            # Enrich query for better image results
            query = enrich_image_query(title, theme, content)
            result = search_unsplash(query, used_ids)

            if result:
                img_id = result.get("id")
                regular_url = result.get("regular_url") or ""
                full_url = result.get("full_url") or ""
                user = result.get("user") or "Unsplash"
                description = result.get("description") or title

                post["unsplash_image"] = regular_url
                post["unsplash_image_url"] = full_url
                post["unsplash_id"] = img_id
                post["image_credit"] = user
                post["alt_text"] = description[:200]
                post["image_url"] = regular_url
                if img_id:
                    add_used_id(img_id)
                changed += 1
                logger.info(f"[UNSPLASH] ✅ {title[:40]}: {regular_url[:40]}")
            else:
                logger.warning(f"[UNSPLASH] No encontradas: {title[:40]}")

        logger.info(f"[UNSPLASH] ✅ {changed} imágenes encontradas")
        return posts

    def fetch_from_mongo(self) -> int:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))

            if not posts:
                logger.warning("[UNSPLASH] No hay posts para enriquecer")
                return 0

            self.fetch_for_posts(posts)

            for post in posts:
                post_id = post.get("_id")
                if post_id:
                    post.pop("_id", None)
                    coll.update_one({"_id": post_id}, {"$set": post})

            return len(posts)

        except Exception as e:
            logger.error(f"[UNSPLASH] Error: {e}")
            return 0


def run(mode: str = "news") -> int:
    logger.info(f"[UNSPLASH] Ejecutando (modo: {mode})")
    fetcher = UnsplashFetcher(mode=mode)
    return fetcher.fetch_from_mongo()


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "news"
    run(mode)
