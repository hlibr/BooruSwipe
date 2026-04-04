# BooruSwipe

BooruSwipe is a local swipe-based recommender for Gelbooru and Danbooru with a Tinder-like interface.

You swipe left/right on images, the app records tag-level feedback, and an LLM periodically turns that feedback into better search tags. The current system is a practical adaptive tag recommender, not a full ranking model.

## What It Does

- Serves images from Gelbooru or Danbooru in a Tinder-like interface
- Records likes, dislikes, and weighted swipes
- Tracks long-term tag preference and recent tag trend
- Uses an LLM to generate recommended search tags
- Falls back to tag-history search and then random images when needed
- Stores all data locally in SQLite

## Requirements

- Python 3.10+
- Booru credentials for one of:
  - Danbooru
  - Gelbooru
- One of:
  - OpenAI-compatible LLM API
  - Ollama
  - LM Studio

## Quick Start

```bash
git clone <repository-url>
cd booruswipe
pip install -e .
cp booru.conf.example booru.conf
```

Edit `booru.conf` and set:

- `BOORU_SOURCE`
- booru credentials for the selected source
- `api_key`
- `base_url`
- `model`

Minimum example for Danbooru:

```bash
BOORU_SOURCE=danbooru
danbooru_api_key=YOUR_DANBOORU_API_KEY
danbooru_user_id=YOUR_DANBOORU_LOGIN
api_key=your-api-key
base_url=https://api.openai.com/v1
model=gpt-4o-mini
```

Minimum example for Gelbooru:

```bash
BOORU_SOURCE=gelbooru
gelbooru_api_key=YOUR_GELBOORU_API_KEY
gelbooru_user_id=YOUR_GELBOORU_USER_ID
api_key=your-api-key
base_url=https://api.openai.com/v1
model=gpt-4o-mini
```

Then start the app:

```bash
python -m booruswipe
```

Open [http://localhost:8000](http://localhost:8000) and swipe a few times before expecting the recommendations to adapt.

Run with verbose logs:

```bash
python -m booruswipe --verbose
```

## Docker

Docker is supported as an alternative local setup path.

Build and run:

```bash
docker compose build
docker compose up
```

The compose setup:

- mounts `./booru.conf` into the container at `/app/booru.conf`
- persists the SQLite database in a named Docker volume
- runs the app with `--verbose`

Open [http://localhost:8000](http://localhost:8000).

Important: if your LLM runs on the host machine, do not use `localhost` in `booru.conf` when running through Docker.

Inside the container:

- `localhost` means the container itself
- host services should be reached via `host.docker.internal`

Examples:

```bash
# LM Studio running on host
base_url=http://host.docker.internal:1234/v1

# Ollama running on host
base_url=http://host.docker.internal:11434/v1
```

If you change only `booru.conf`, rebuild is not needed. Restart is enough:

```bash
docker compose restart
```

Useful commands:

```bash
docker compose logs -f
docker compose down
docker compose down -v
```

## Configuration

Configuration lives in `booru.conf`.

### Booru Source

```bash
BOORU_SOURCE=danbooru
```

Supported values:

- `danbooru`
- `gelbooru`

### Danbooru

Danbooru credentials are required. `danbooru_user_id` should contain your Danbooru login name, despite the legacy variable name.

```bash
danbooru_api_key=YOUR_DANBOORU_API_KEY
danbooru_user_id=YOUR_DANBOORU_LOGIN
```

Danbooru API docs: [https://danbooru.donmai.us/wiki_pages/help:api](https://danbooru.donmai.us/wiki_pages/help:api)

### Gelbooru

Gelbooru credentials are required.

```bash
gelbooru_api_key=YOUR_GELBOORU_API_KEY
gelbooru_user_id=YOUR_GELBOORU_USER_ID
```

### LLM

```bash
api_key=your-api-key
base_url=https://api.openai.com/v1
model=gpt-4o-mini
```

Example providers:

| Provider | api_key | base_url | model |
| --- | --- | --- | --- |
| OpenAI | `sk-...` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Ollama | `ollama` | `http://localhost:11434/v1` | `llama3.2` |
| LM Studio | `lm-studio` | `http://localhost:1234/v1` | `local-model` |

### Tuning

Useful settings:

```bash
LLM_MIN_SWIPES=5
LLM_MAX_TAGS=100
LLM_TAG_FILTER_MIN_COUNT=1
BOORU_TAGS_PER_SEARCH=2
LLM_USE_STRUCTURED_OUTPUT=true
RANDOM_IMAGE_CHANCE=10
DOUBLE_LIKED_NEVER_IGNORE=true
```

## API Overview

Main endpoints:

- `GET /api/image`
- `POST /api/swipe`
- `GET /api/stats`
- `GET /api/settings`
- `POST /api/settings`
- `POST /api/settings/test`
- `GET /health`

Notes:

- For Gelbooru, image display goes through backend proxying to avoid hotlink issues.
- For Danbooru, the frontend gets the direct image URL.
- Swipes store both `post_url` and original `file_url`.

## Data Model

The local SQLite database stores:

- `swipes`: each swipe event, booru source, tags, post URL, file URL, weight
- `tag_counts`: long-term like/dislike counters per tag
- `swiped_images`: IDs used to reduce repeats
- `double_liked_images`: IDs exempted from repeat filtering
- `preference_profiles`: latest saved LLM output

## Development

Run tests:

```bash
pytest -q
```

Reset the database:

```bash
python -m booruswipe --reset-db
```

## How Recommendation Works

The selection loop is currently:

1. Pull cumulative tag counts from swipe history
2. Pull recent tag scores from the latest swipes
3. Ask the LLM for recommended search tags
4. Search the booru with those tags
5. If that fails, fall back to top liked tags
6. If that fails, fall back to random

Important detail: the app improves search queries, but it does not yet rank candidate images after retrieval. It is closer to "adaptive search term generation" than "best-image scoring."

## Current limitations:

- Single-user oriented: request/session state is kept in process memory
- Recommendation quality is heuristic and tag-based

## Possible Next Improvements

- Score retrieved candidates instead of picking randomly from search results
- Track tag pairs / tag combinations, not only independent tag counts
- Add smarter exploration instead of relying mostly on random chance
- Replace global in-memory session state with per-user session handling
- Add live integration tests for Danbooru, Gelbooru, and LLM providers

## License

MIT
