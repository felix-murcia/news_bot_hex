import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("video_bot")

from src.video.entrypoints.cli import (
    main_fetch,
    main_info,
    main_video_to_news,
    main_article_from_video,
    main_pipeline,
    main_full_pipeline,
    main_wordpress,
    main_bluesky,
    main_mastodon,
    main_facebook,
)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "fetch":
            main_fetch()
        elif command == "info":
            main_info()
        elif command == "process":
            main_video_to_news()
        elif command == "article":
            main_article_from_video()
        elif command == "pipeline":
            main_pipeline()
        elif command == "full":
            main_full_pipeline()
        elif command == "wordpress":
            main_wordpress()
        elif command == "bluesky":
            main_bluesky()
        elif command == "mastodon":
            main_mastodon()
        elif command == "facebook":
            main_facebook()
        else:
            print(
                "Usage: python -m src.video.entrypoints.cli [fetch|info|process|article|pipeline|full|wordpress|bluesky|mastodon|facebook] <args>"
            )
    else:
        print(
            "Usage: python -m src.video.entrypoints.cli [fetch|info|process|article|pipeline|full|wordpress|bluesky|mastodon|facebook] <args>"
        )
