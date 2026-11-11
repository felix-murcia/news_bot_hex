"""Social media publisher facade.

Publishes articles to Bluesky, Mastodon and Facebook (real implementations).
X and LinkedIn are simulated.
"""

from config.logging_config import get_logger

logger = get_logger("news_bot.social")

from typing import List, Dict, Any


class SocialMediaPublisher:
    """Publish an article to social platforms.

    Real: Bluesky, Mastodon, Facebook
    Simulated: X, LinkedIn
    """

    def __init__(
        self,
        enable_bluesky: bool = True,
        enable_mastodon: bool = True,
        enable_facebook: bool = True,
    ):
        self._bluesky = None
        self._mastodon = None
        self._facebook = None
        if enable_bluesky:
            try:
                from src.shared.adapters.bluesky_publisher import BlueskyPublisher
                self._bluesky = BlueskyPublisher()
            except Exception as e:
                logger.warning(f"Bluesky init failed: {e}")
        if enable_mastodon:
            try:
                from src.shared.adapters.mastodon_publisher import MastodonPublisher
                self._mastodon = MastodonPublisher()
            except Exception as e:
                logger.warning(f"Mastodon init failed: {e}")
        if enable_facebook:
            try:
                from src.shared.adapters.facebook_publisher import FacebookPublisher
                self._facebook = FacebookPublisher()
            except Exception as e:
                logger.warning(f"Facebook init failed: {e}")

    def publish(self, post: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Publish the post to all configured platforms."""
        tweet = post.get("tweet", "")
        wp_url = post.get("wp_url", "")
        url = post.get("url", "")
        final_url = wp_url or url
        image_url = post.get("image_url", "")
        results: List[Dict[str, Any]] = []

        # Simulated platforms
        for platform in ("X", "LinkedIn"):
            results.append({
                "platform": platform,
                "status": "success",
                "url": f"https://example.com/{platform.lower()}/post/12345",
            })

        # Facebook (real)
        if self._facebook:
            try:
                res = self._facebook.publish_posts(articles=[post])
                results.append({"platform": "Facebook", "status": "success", "detail": res})
            except Exception as e:
                results.append({"platform": "Facebook", "status": "error", "error": str(e)})

        # Bluesky (real)
        if self._bluesky:
            try:
                bluesky_post = {
                    "tweet": tweet, "wp_url": final_url,
                    "url": url, "image_url": image_url, "hashtags": [],
                }
                res = self._bluesky.publish_posts([bluesky_post])
                results.append({"platform": "Bluesky", "status": "success", "detail": res})
            except Exception as e:
                results.append({"platform": "Bluesky", "status": "error", "error": str(e)})

        # Mastodon (real)
        if self._mastodon:
            try:
                mastodon_post = {
                    "tweet": tweet, "wp_url": final_url,
                    "url": url, "image_url": image_url, "hashtags": [],
                }
                res = self._mastodon.publish_posts([mastodon_post])
                results.append({"platform": "Mastodon", "status": "success", "detail": res})
            except Exception as e:
                results.append({"platform": "Mastodon", "status": "error", "error": str(e)})

        return results

    def publish_all(self) -> List[Dict[str, Any]]:
        """Publish all pending posts from DB to all configured platforms (batch)."""
        results: List[Dict[str, Any]] = []

        if self._facebook:
            try:
                res = self._facebook.publish_posts()
                results.append({"platform": "Facebook", "status": "success", "detail": res})
            except Exception as e:
                logger.error(f"Facebook publish_all error: {e}")
                results.append({"platform": "Facebook", "status": "error", "error": str(e)})
                raise RuntimeError(f"Social publisher crítico falló (Facebook): {e}")

        if self._bluesky:
            try:
                res = self._bluesky.publish_posts()
                results.append({"platform": "Bluesky", "status": "success", "detail": res})
            except Exception as e:
                logger.error(f"Bluesky publish_all error: {e}")
                results.append({"platform": "Bluesky", "status": "error", "error": str(e)})
                raise RuntimeError(f"Social publisher crítico falló (Bluesky): {e}")

        if self._mastodon:
            try:
                res = self._mastodon.publish_posts()
                results.append({"platform": "Mastodon", "status": "success", "detail": res})
            except Exception as e:
                logger.error(f"Mastodon publish_all error: {e}")
                results.append({"platform": "Mastodon", "status": "error", "error": str(e)})
                raise RuntimeError(f"Social publisher crítico falló (Mastodon): {e}")

        return results
