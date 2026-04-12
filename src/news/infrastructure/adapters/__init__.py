from src.news.infrastructure.adapters.mongo_repositories import (
    MongoRSSSourceRepository,
    MongoArticleRepository,
    MongoVerifiedNewsRepository,
    MongoPublishedUrlsRepository,
    MongoKeywordsRepository,
    MongoScoringConfigRepository,
    BASE_DIR,
    DATA_DIR,
)
from src.news.infrastructure.adapters.rss_fetcher import FeedparserRSSFetcher
from src.news.infrastructure.adapters.content_extractor import JinaContentExtractor
from src.news.infrastructure.adapters.scoring import (
    compute_score,
    categorizar_noticia,
    check_breaking_keywords,
    is_valid_score,
    sort_verified_news,
    parse_iso_date,
    resumir_noticia,
)
from src.news.infrastructure.adapters.date_utils import (
    parse_date_flexible,
    is_today_or_yesterday,
    get_article_date,
)

# Infrastructure adapter (ML layer)
from src.news.infrastructure.adapters.news_validator_adapter import (
    ClassicNewsValidatorAdapter,
)
