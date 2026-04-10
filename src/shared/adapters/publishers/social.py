"""Simple social media publisher used by the video pipeline.

The real project may have concrete implementations for X/Twitter, LinkedIn and
Facebook. For the purpose of this task we provide a lightweight wrapper that
accepts an article dict (as produced by ``ArticleFromVideoUseCase``) and a list
of tweet strings. It returns a list of dicts describing the simulated publish
results.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger("news_bot")


class SocialMediaPublisher:
    """Publish an article and optional tweets to social platforms.

    This wrapper now incluye X, LinkedIn, Facebook y, opcionalmente,
    Bluesky y Mastodon. Los publicadores específicos se crean bajo demanda
    para evitar dependencias innecesarias cuando no se usan.
    """

    def __init__(self, enable_bluesky: bool = True, enable_mastodon: bool = True):
        # Los publicadores se importan aquí para evitar ciclos de importación.
        self._bluesky = None
        self._mastodon = None
        if enable_bluesky:
            try:
                from src.shared.adapters.bluesky_publisher import BlueskyPublisher

                self._bluesky = BlueskyPublisher()
            except Exception as e:
                logger.warning(f"[SOCIAL] No se pudo inicializar BlueskyPublisher: {e}")
        if enable_mastodon:
            try:
                from src.shared.adapters.mastodon_publisher import MastodonPublisher

                self._mastodon = MastodonPublisher()
            except Exception as e:
                logger.warning(
                    f"[SOCIAL] No se pudo inicializar MastodonPublisher: {e}"
                )

    def publish(self, post: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Publica el post en todas las plataformas configuradas."""
        tweet = post.get("tweet", "")
        wp_url = post.get("wp_url", "")
        url = post.get("url", "")
        final_url = wp_url or url
        image_url = post.get("image_url", "")

        results = []

        platforms = ["X", "LinkedIn", "Facebook"]
        for platform in platforms:
            try:
                logger.info(f"[SOCIAL] Publicando en {platform}")
                results.append(
                    {
                        "platform": platform,
                        "status": "success",
                        "url": f"https://example.com/{platform.lower()}/post/12345",
                    }
                )
            except Exception as e:
                logger.error(f"[SOCIAL] Error publicando en {platform}: {e}")
                results.append(
                    {"platform": platform, "status": "error", "error": str(e)}
                )

        if getattr(self, "_bluesky", None):
            try:
                logger.info("[SOCIAL] Publicando en Bluesky")
                bluesky_post = {
                    "tweet": tweet,
                    "wp_url": final_url,
                    "url": url,
                    "image_url": image_url,
                    "hashtags": [],
                }
                bluesky_res = self._bluesky.publish_posts([bluesky_post])
                results.append(
                    {"platform": "Bluesky", "status": "success", "detail": bluesky_res}
                )
            except Exception as e:
                logger.error(f"[SOCIAL] Error en Bluesky: {e}")
                results.append(
                    {"platform": "Bluesky", "status": "error", "error": str(e)}
                )

        if getattr(self, "_mastodon", None):
            try:
                logger.info("[SOCIAL] Publicando en Mastodon")
                mastodon_post = {
                    "tweet": tweet,
                    "wp_url": final_url,
                    "url": url,
                    "image_url": image_url,
                    "hashtags": [],
                }
                mastodon_res = self._mastodon.publish_posts([mastodon_post])
                results.append(
                    {
                        "platform": "Mastodon",
                        "status": "success",
                        "detail": mastodon_res,
                    }
                )
            except Exception as e:
                logger.error(f"[SOCIAL] Error en Mastodon: {e}")
                results.append(
                    {"platform": "Mastodon", "status": "error", "error": str(e)}
                )

        logger.info(f"[SOCIAL] Tweet publicado: {tweet[:50]}...")
        return results
