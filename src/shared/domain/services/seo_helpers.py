from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SeoHelpers:
    slugify: Callable[..., str]
    extract_focus_keyphrase: Callable[..., str]
    generate_meta_description: Callable[..., str]
    truncate_seo_title: Callable[..., str]
    clean_title: Callable[..., str]
    generate_excerpt: Callable[..., str]
