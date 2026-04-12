import sys
from src.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger("news_bot")

from src.news.entrypoints.cli import (
    main_rss,
    main_verify,
    main_full_verify,
    main_verifier,
    main_soft,
    main_article,
    main_provider,
    main_content,
    main_news_to_news,
    main_bluesky,
    main_facebook,
    main_mastodon,
    main_wordpress,
    main_pipeline,
)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "rss":
            main_rss()
        elif command == "verify":
            main_verify()
        elif command == "full":
            main_full_verify()
        elif command == "verifier":
            main_verifier()
        elif command == "soft":
            main_soft()
        elif command == "article":
            main_article()
        elif command == "provider":
            main_provider()
        elif command == "content":
            main_content()
        elif command == "news_to_news":
            main_news_to_news()
        elif command == "bluesky":
            main_bluesky()
        elif command == "facebook":
            main_facebook()
        elif command == "mastodon":
            main_mastodon()
        elif command == "wordpress":
            main_wordpress()
        elif command == "pipeline":
            main_pipeline()
        else:
            print(
                "Usage: python -m src.news.entrypoints.cli [rss|verify|full|verifier|soft|article|provider|content|news_to_news|bluesky|facebook|mastodon|wordpress|pipeline]"
            )
    else:
        main_rss()
