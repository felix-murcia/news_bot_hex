# News Bot Hex

AI-powered news pipeline that fetches RSS feeds, verifies news, generates articles, and publishes to WordPress and social media (X, Bluesky, Mastodon, Facebook).

## Architecture

Hexagonal architecture with three independent pipelines sharing common infrastructure:

```
src/
├── news/          # News RSS fetch → verify → generate article
├── audio/         # Audio URL → transcribe → generate article
├── video/         # Video URL → transcribe → generate article
└── shared/        # Common adapters, use cases, and utilities
```

Each pipeline follows the same flow:
1. **Fetch** content (RSS articles, audio, or video)
2. **Transcribe/Extract** text
3. **Generate** article with AI (Gemini, local models, or mock)
4. **Enrich** with images (Unsplash, Google Images, extraction)
5. **Publish** to WordPress
6. **Share** to social media

## Quick Start

### Prerequisites

- Python 3.12+
- MongoDB (configured in `.env`)
- FFmpeg (audio/video processing)
- NVIDIA GPU (optional, for local LLM)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run the server

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### 4. Use Docker (alternative)

```bash
docker compose up -d
```

## API Endpoints

### News Pipeline (`/news`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/news/pipeline` | Full automated pipeline: RSS fetch → verify → generate → publish |
| `POST` | `/news/rss` | Fetch and store articles from RSS feeds |
| `POST` | `/news/verify` | Full verification: score, categorize, filter fake news |
| `POST` | `/news/soft` | Soft verification (lightweight validation) |
| `POST` | `/news/article` | Generate article from news content |
| `POST` | `/news/content` | Process content with AI |
| `POST` | `/news/process_url` | Process a single news URL |

### Audio Pipeline (`/audio`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/audio/pipeline` | Full pipeline: download → transcribe → generate → publish |

### Video Pipeline (`/video`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/video/pipeline` | Full pipeline: download → transcribe → generate → publish |

### Health

```bash
curl http://localhost:8000/health
```

## Scheduled Execution

Run the news pipeline automatically every hour using systemd timer:

```bash
./scripts/install_timer.sh
```

This installs a systemd user timer that executes `curl -X POST http://localhost:8000/news/pipeline` every hour, 7 days a week.

**Useful commands:**

```bash
# Check timer status
systemctl --user status news-bot-pipeline.timer

# Run pipeline manually now
systemctl --user start news-bot-pipeline.service

# View execution logs
journalctl --user -u news-bot-pipeline.service --since today

# Stop the timer
systemctl --user stop news-bot-pipeline.timer
```

## Configuration

### AI Providers

Set `AI_PROVIDER` in `.env`:
- `gemini` — Google Gemini (default)
- `openrouter` — OpenRouter (multiple models)
- `mock` — Local fallback (no API keys needed)

### Image Enrichment

Images are fetched from multiple sources in priority order:
1. Unsplash (free, high quality)
2. Google Images
3. Extracted from source website (og:image, twitter:image)
4. Default NBES logo (fallback)

### Publishing Targets

Configure each platform in `.env`:

| Platform | Required Keys |
|----------|--------------|
| WordPress | `WP_USER`, `WP_PASSWORD`, `WP_HOSTING_API_BASE` |
| X (Twitter) | `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` |
| Bluesky | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` |
| Mastodon | `MASTODON_ACCESS_TOKEN`, `MASTODON_INSTANCE_URL` |
| Facebook | `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN` |

## Project Structure

```
news_bot_hex/
├── config/              # Settings, prompts, logging
├── src/
│   ├── news/            # News pipeline
│   │   ├── domain/      # Entities, ports, rules
│   │   ├── application/ # Use cases
│   │   ├── infrastructure/ # Adapters (MongoDB, RSS, scoring)
│   │   └── entrypoints/ # API routes
│   ├── audio/           # Audio pipeline (same structure)
│   ├── video/           # Video pipeline (same structure)
│   └── shared/          # Shared adapters and use cases
│       ├── adapters/    # AI, WordPress, social, images, translator
│       ├── application/ # Shared use cases (ArticleFromTranscript)
│       ├── domain/      # Shared entities
│       └── utils/       # Helpers (tweet truncation, spell check, post-editor)
├── scripts/
│   ├── run_pipeline.sh      # Pipeline execution script
│   ├── install_timer.sh     # systemd timer installer
│   └── train_news_validator.py
├── tests/               # Pytest test suite
├── server.py            # FastAPI entry point
├── docker-compose.yml
├── Dockerfile
└── .env                 # Environment variables (not committed)
```

## Testing

```bash
pytest tests/ -v
```

## Features

- **RSS aggregation** — Fetches from multiple news sources
- **Fake news detection** — Heuristic scoring + ML model
- **Article generation** — AI-powered with structured HTML output
- **SEO optimization** — Slug generation, focus keywords, meta descriptions
- **Image enrichment** — Multi-source with fallback
- **Multi-platform publishing** — WordPress, X, Bluesky, Mastodon, Facebook
- **Transcript processing** — Audio (YouTube, Spotify, podcasts) and video (YouTube, Facebook, Twitter)
- **Content post-editor** — Automatic correction of spelling and style
- **Caching** — Content cache with configurable TTL
- **MongoDB persistence** — Articles, sources, scoring config, published URLs
