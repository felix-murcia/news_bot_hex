#!/usr/bin/env python3
"""Initialize RSS sources collection in MongoDB.

This script populates the sources_rss collection with Spanish language
news feeds that provide articles via RSS.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.adapters.mongo_db import get_database
from config.logging_config import get_logger

logger = get_logger("initialize_rss_sources")

# Spanish language news RSS sources
RSS_SOURCES = [
    {
        "source": "BBC Mundo",
        "url": "https://feeds.bbc.co.uk/mundo/index.xml",
        "origin": "BBC",
    },
    {
        "source": "Reuters España",
        "url": "https://www.reutersagency.com/feed/?taxonomy=best-topics&output=rss",
        "origin": "Reuters",
    },
    {
        "source": "El País",
        "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
        "origin": "El País",
    },
    {
        "source": "El Mundo",
        "url": "https://www.elmundo.es/feed.html",
        "origin": "El Mundo",
    },
    {
        "source": "El Español",
        "url": "https://www.elespanol.com/rss/",
        "origin": "El Español",
    },
    {
        "source": "La Vanguardia",
        "url": "https://feeds.lavanguardia.com/rss/portada.xml",
        "origin": "La Vanguardia",
    },
    {
        "source": "ABC España",
        "url": "https://www.abc.es/rss/2.0/abcespana.xml",
        "origin": "ABC",
    },
    {
        "source": "Europa Press",
        "url": "https://www.europapress.es/rss/rss.aspx",
        "origin": "Europa Press",
    },
    {
        "source": "RTVE",
        "url": "https://www.rtve.es/alacarta/videos/rssalbum/1032.xml",
        "origin": "RTVE",
    },
    {
        "source": "Infobae España",
        "url": "https://www.infobae.com/feed/",
        "origin": "Infobae",
    },
]


def initialize_rss_sources():
    """Initialize RSS sources collection."""
    db = get_database()
    collection = db["sources_rss"]

    # Delete existing document if it exists
    collection.delete_many({})

    # Create document with sources
    sources_document = {
        "_id": "sources",
        "sources": RSS_SOURCES,
    }

    result = collection.insert_one(sources_document)
    logger.info(f"Initialized RSS sources collection with {len(RSS_SOURCES)} sources")
    logger.info(f"Inserted document with ID: {result.inserted_id}")

    # Verify
    doc = collection.find_one({"_id": "sources"})
    if doc and doc.get("sources"):
        logger.info(f"Verification: Found {len(doc['sources'])} RSS sources in database")
        for source in doc['sources']:
            logger.info(f"  ✓ {source.get('source')}: {source.get('url')}")
    else:
        logger.error("Verification failed: RSS sources not found in database")
        return False

    return True


if __name__ == "__main__":
    try:
        success = initialize_rss_sources()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Error initializing RSS sources: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
