import re
from typing import Optional

from config.settings import Settings

DEFAULT_SOCIAL_NETWORKS = ("x", "twitter", "bluesky", "mastodon")


def get_social_post_limit(limit: Optional[int] = None) -> int:
    """Devuelve el límite de caracteres para publicaciones sociales.

    Si no se pasa un límite explícito, usa el más restrictivo de las
    plataformas X/Twitter, Bluesky y Mastodon para asegurar compatibilidad.
    """
    if limit is not None:
        return limit

    values = [
        Settings.POST_LIMITS.get(network)
        for network in DEFAULT_SOCIAL_NETWORKS
        if Settings.POST_LIMITS.get(network) is not None
    ]
    return min(values) if values else 280


def inline_hashtags(text: str) -> str:
    """Move trailing hashtags inline onto matching keywords in the text.

    Only processes hashtags that appear AFTER the last sentence-ending
    punctuation (trailing block).  If hashtags are already inline
    (mixed into sentences), the text is returned unchanged.
    """
    text = (text or "").strip()
    if not text:
        return text

    match = re.search(r"[.!?](?=\s*#\w+)", text)
    if not match:
        return text

    split_pos = match.start() + 1
    body = text[:split_pos].strip()
    tail = text[split_pos:].strip()

    trailing = re.findall(r"#\w+", tail)
    if not trailing:
        return text

    non_hashtag_tail = re.sub(r"#\w+", "", tail).strip()
    if non_hashtag_tail:
        return text

    remaining = []
    for tag in trailing:
        word = tag[1:]
        pattern = re.compile(
            rf"(?<![#\w]){re.escape(word)}(?!\w)",
            re.IGNORECASE,
        )
        new_body, count = pattern.subn(f"#{word}", body, count=1)
        if count:
            body = new_body
        else:
            remaining.append(tag)

    if remaining:
        return f"{body} {' '.join(remaining)}"
    return body


def _strip_inline_hashtags_rtl(text: str, limit: int) -> str:
    """Remove '#' from inline hashtags right-to-left until text fits the limit."""
    if len(text) <= limit:
        return text

    positions = [(m.start(), m.group()) for m in re.finditer(r"#(?=\w)", text)]
    for pos, _ in reversed(positions):
        text = text[:pos] + text[pos + 1:]
        if len(text) <= limit:
            return text
    return text


def _has_trailing_hashtags(text: str) -> bool:
    """Check if text ends with a block of hashtags (not inline)."""
    return bool(re.search(r"\s+#\w+(\s+#\w+)*\s*$", text))


def _has_any_hashtags(text: str) -> bool:
    return bool(re.search(r"#\w+", text))


def truncate_social_post(text: str, limit: Optional[int] = None) -> str:
    """Trunca un texto social respetando hashtags y el límite más estricto.

    Handles both inline hashtags (preferred) and trailing hashtags (legacy).
    If trailing hashtags are found, moves them inline first.
    If still over the limit, removes '#' from inline hashtags right-to-left,
    then falls back to text truncation.
    """
    tweet = inline_hashtags(text)
    tweet = (tweet or "").strip()
    limit = get_social_post_limit(limit)
    if len(tweet) <= limit:
        return tweet

    if _has_trailing_hashtags(tweet) or not _has_any_hashtags(tweet):
        return _truncate_with_trailing_hashtags(tweet, limit)

    trimmed = _strip_inline_hashtags_rtl(tweet, limit)
    if len(trimmed) <= limit:
        return trimmed

    truncated = trimmed[:limit].rsplit(" ", 1)[0]
    if not truncated:
        truncated = trimmed[:limit]
    return truncated.rstrip()


def _truncate_with_trailing_hashtags(tweet: str, limit: int) -> str:
    """Truncate text that has trailing hashtags, preserving at least one."""
    hashtags = re.findall(r"#\w+", tweet)
    plain_text = re.sub(r"#\w+", "", tweet)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()

    if hashtags:
        trimmed_hashtags = hashtags.copy()

        while len(trimmed_hashtags) > 1:
            candidate = f"{plain_text} {' '.join(trimmed_hashtags)}".strip()
            if len(candidate) <= limit:
                return candidate
            trimmed_hashtags.pop()

        first_hashtag = trimmed_hashtags[0]
        candidate = f"{plain_text} {first_hashtag}".strip()
        if len(candidate) <= limit:
            return candidate

        available_space = limit - len(first_hashtag) - 1
        if available_space > 10:
            content_part = plain_text[:available_space].rsplit(" ", 1)[0]
            if not content_part:
                content_part = plain_text[:available_space]
            return f"{content_part} {first_hashtag}".strip()

        return first_hashtag[:limit]

    if limit > 3:
        available = limit - 3
        truncated = plain_text[:available].rsplit(" ", 1)[0]
        if not truncated:
            truncated = plain_text[:available]
        return truncated.rstrip() + "..."
    return plain_text[:limit]
