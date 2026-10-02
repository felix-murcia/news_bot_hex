"""Siembra una base de datos con la ESTRUCTURA de `appdb` para el job de CI.

Por que existe esto (decision 5 de Felix, Fase 4):
    Los tests marcados `production` afirman contra un CLON de `appdb`
    (conftest.py). En CI el servicio Mongo arranca VACIO: sin sembrar `appdb`,
    `clone_production_database()` aborta porque no hay nada que clonar.

    Este script siembra `appdb` con la misma forma que la real (22 fuentes RSS,
    miles de articulos en `raw_news`, las colecciones obligatorias) para que el
    clon tenga datos con las CARACTERISTICAS que los tests comprueban. NO es una
    copia de produccion: es un fixture con el MISMO ESQUEMA y los MISMOS
    UMBRALES (`StartupValidator.MIN_ARTICLES`, `MIN_RSS_SOURCES`).

Uso:
    python scripts/seed_ci_production_db.py --db appdb --allow-production

Determinismo:
    Sin aleatoriedad ni marcas de tiempo reales: los campos se derivan del
    indice. Dos runs producen exactamente el mismo contenido, asi que un fallo en
    CI es reproducible.

Guardarrail:
    Escribir en `appdb` exige `--allow-production` explicito. Sin el, el script
    aborta: sembrar produccion por accidente seria peor que no sembrar nada.

Nota sobre el idioma:
    Los textos del fixture van en ASCII a proposito. Son marcadores de posicion
    para que los tests tengan volumen y esquema; el idioma no forma parte del
    contrato que estos tests comprueban, y evitar acentos mantiene el fichero
    libre de problemas de codificacion entre runners.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

# --- Configuracion del fixture (espeja appdb real) ---------------------------

# Fuentes RSS reales y de calidad. Deben incluir "BBC World", "New York Times",
# "Reuters" y "NPR": test_rss_sources_are_from_production_appdb afirma que
# alguno de esos cuatro esta presente, y test_rss_sources_are_production_quality
# exige al menos una fuente de las seis que lista.
RSS_SOURCES = [
    {"origin": "BBC_RSS", "source": "BBC Top Stories", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    {"origin": "BBC_RSS", "source": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"origin": "BBC_RSS", "source": "BBC Europe", "url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml"},
    {"origin": "BBC_RSS", "source": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"origin": "NYT_RSS", "source": "New York Times", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"origin": "NYT_RSS", "source": "New York Times Business", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"},
    {"origin": "REUTERS_RSS", "source": "Reuters", "url": "https://feeds.reuters.com/reuters/topNews"},
    {"origin": "REUTERS_RSS", "source": "Reuters World", "url": "https://feeds.reuters.com/reuters/worldNews"},
    {"origin": "NPR_RSS", "source": "NPR", "url": "https://feeds.npr.org/1001/rss.xml"},
    {"origin": "NPR_RSS", "source": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml"},
    {"origin": "AP_RSS", "source": "AP News", "url": "https://apnews.com/hub/ap-top-news/rss"},
    {"origin": "CNN_RSS", "source": "CNN World", "url": "http://rss.cnn.com/rss/edition_world.rss"},
    {"origin": "ALJAZEERA_RSS", "source": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"origin": "GUARDIAN_RSS", "source": "The Guardian", "url": "https://www.theguardian.com/world/rss"},
    {"origin": "DW_RSS", "source": "Deutsche Welle", "url": "https://rss.dw.com/rdf/rss-en-all"},
    {"origin": "FRANCE24_RSS", "source": "France 24", "url": "https://www.france24.com/en/rss"},
    {"origin": "RTVE_RSS", "source": "RTVE Noticias", "url": "https://api.rtve.es/rss/noticias.xml"},
    {"origin": "ELPAIS_RSS", "source": "El Pais Internacional", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},
    {"origin": "LEMONDE_RSS", "source": "Le Monde", "url": "https://www.lemonde.fr/rss/une.xml"},
    {"origin": "POLITICO_RSS", "source": "Politico", "url": "https://www.politico.com/rss/politicopicks.xml"},
    {"origin": "EURONEWS_RSS", "source": "Euronews", "url": "https://www.euronews.com/rss"},
    {"origin": "UN_RSS", "source": "UN News", "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml"},
]

# Plantillas de titulo. Marcadores de posicion con la forma que
# `Article.from_dict` espera (title, url, source, desc, publishedAt).
TOPIC_TEMPLATES = [
    "Crisis en la region: avanzan las negociaciones sobre la {_topic}",
    "Los gobiernos alcanzan un acuerdo sobre el plan europeo de {_topic}",
    "Analistas advierten del impacto de la reforma en el sector de la {_topic}",
    "La comunidad internacional responde al informe sobre {_topic}",
    "Nuevas medidas para frenar la crisis de {_topic}",
    "El informe sobre {_topic} divide a los expertos europeos",
    "Aumenta la presion sobre {_topic} tras el ultimo anuncio",
    "Agreement reached on {_topic} funding package",
]

TOPICS = [
    "geopolitica",
    "energia",
    "migracion",
    "defensa",
    "comercio",
    "clima",
]

# Colecciones que en appdb existen pero estan VACIAS. Deben materializarse
# explicitamente: sin ellas el clon tampoco las tiene y
# test_required_collections_exist falla.
EMPTY_COLLECTIONS = ("verified_news", "verified_all", "trending")

BATCH = 1000


def build_articles(count: int) -> list:
    """Genera `count` articulos deterministas con la forma de `raw_news`."""
    base = datetime(2026, 1, 1, 0, 0, 0)
    documents = []
    for index in range(count):
        source = RSS_SOURCES[index % len(RSS_SOURCES)]
        template = TOPIC_TEMPLATES[index % len(TOPIC_TEMPLATES)]
        topic = TOPICS[index % len(TOPICS)]
        documents.append(
            {
                "title": template.format(_topic=topic),
                "url": "https://example.org/{}/{index:05d}".format(
                    source["origin"].lower(), index=index
                ),
                "source": source["source"],
                "desc": (
                    "Noticia sintetica de CI (indice {index}). No procede de "
                    "{source}; existe solo para que los tests de datos reales "
                    "dispongan de volumen y esquema."
                ).format(index=index, source=source["source"]),
                "publishedAt": (base + timedelta(hours=index)).isoformat() + "Z",
                "origin": "RSS",
                "published": False,
                "filtered": True,
            }
        )
    return documents


def seed(db, count: int) -> None:
    """Siembra `db` con el esquema de appdb. Idempotente: dropea antes."""
    db.client.drop_database(db.name)

    db["sources_rss"].insert_one({"_id": "sources", "sources": RSS_SOURCES})

    articles = build_articles(count)
    for start in range(0, len(articles), BATCH):
        db["raw_news"].insert_many(articles[start : start + BATCH], ordered=False)

    for empty in EMPTY_COLLECTIONS:
        db.create_collection(empty)

    print(
        "[seed] '{db}': {sources} fuentes RSS, {articles:,} articulos, "
        "{collections} colecciones.".format(
            db=db.name,
            sources=len(RSS_SOURCES),
            articles=db["raw_news"].count_documents({}),
            collections=len(db.list_collection_names()),
        )
    )


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="Siembra el fixture de appdb para CI.")
    parser.add_argument("--db", default="appdb", help="Base de datos a sembrar.")
    parser.add_argument(
        "--count",
        type=int,
        default=1200,
        help="Articulos en raw_news (minimo 1000: StartupValidator.MIN_ARTICLES).",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Obligatorio para escribir en appdb.",
    )
    args = parser.parse_args(argv)

    if args.db == "appdb" and not args.allow_production:
        print(
            "ABORTADO: sembrar 'appdb' exige --allow-production.", file=sys.stderr
        )
        return 2

    from pymongo import MongoClient

    client = MongoClient(
        host=os.environ.get("MONGO_HOST", "127.0.0.1"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        username=os.environ.get("MONGO_USER") or None,
        password=os.environ.get("MONGO_PASSWORD") or None,
        authSource="admin",
        serverSelectionTimeoutMS=10000,
    )
    seed(client[args.db], args.count)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))