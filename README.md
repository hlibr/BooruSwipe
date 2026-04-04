# BooruSwipe

BooruSwipe is a local swipe-based recommender for Gelbooru and Danbooru with a Tinder-like interface.

You swipe left/right on images, the app records tag-level feedback, and an LLM periodically turns that feedback into better search tags.





https://github.com/user-attachments/assets/6f5cbd00-4947-441a-8e57-eb50b4bd152e





## What It Does

- Serves images from Gelbooru or Danbooru in a Tinder-like interface
- Records likes, dislikes, and weighted swipes
- First images are random (the amount is configurable, default: 10), then it uses an LLM to generate search tags that get used for next image selection
- If no LLM is connected, simply uses the top liked tags to query the next image

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

Minimum example for Gelbooru:

```bash
BOORU_SOURCE=gelbooru
gelbooru_api_key=YOUR_GELBOORU_API_KEY
gelbooru_user_id=YOUR_GELBOORU_USER_ID
api_key=your-api-key
base_url=https://api.openai.com/v1
model=gpt-4o-mini
```

Minimum example for Danbooru:

```bash
BOORU_SOURCE=danbooru
danbooru_api_key=YOUR_DANBOORU_API_KEY
danbooru_user_id=YOUR_DANBOORU_LOGIN
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

First create the config file:

```bash
cp booru.conf.example booru.conf
```

Edit `booru.conf` before starting the container.

Then build and run:

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
BOORU_SOURCE=gelbooru
```

Supported values:

- `danbooru`
- `gelbooru`

### Gelbooru

Gelbooru credentials are required.

```bash
gelbooru_api_key=YOUR_GELBOORU_API_KEY
gelbooru_user_id=YOUR_GELBOORU_USER_ID
```

### Danbooru

Danbooru credentials are required. `danbooru_user_id` should contain your Danbooru login name, despite the legacy variable name.

```bash
danbooru_api_key=YOUR_DANBOORU_API_KEY
danbooru_user_id=YOUR_DANBOORU_LOGIN
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

Current defaults:

```bash
LLM_MIN_SWIPES=10
LLM_MAX_TAGS=30
LLM_TAG_FILTER_MIN_COUNT=1
LLM_USE_STRUCTURED_OUTPUT=true
LLM_RECENT_POSITIVE=10
LLM_RECENT_NEGATIVE=10
BOORU_TAGS_PER_SEARCH=5
BOORU_TAGS_PER_SEARCH_FALLBACK=3
RANDOM_IMAGE_CHANCE=5
DOUBLE_LIKED_NEVER_IGNORE=false
BOORU_SEARCH_LIMIT=100
BOORU_SEARCH_PAGES=5
BOORU_SEARCH_SLEEP=0.15
```

All supported settings:

| Setting | Required | Default | Meaning |
| --- | --- | --- | --- |
| `api_key` | No | none | API key for the LLM provider |
| `base_url` | Yes | `https://api.openai.com/v1` | Base URL for the LLM provider |
| `model` | Yes | none | Model name used for chat completions |
| `BOORU_SOURCE` | Yes | `gelbooru` | Which booru backend to use |
| `danbooru_api_key` | If `BOORU_SOURCE=danbooru` | none | Danbooru API key |
| `danbooru_user_id` | If `BOORU_SOURCE=danbooru` | none | Danbooru login name |
| `gelbooru_api_key` | If `BOORU_SOURCE=gelbooru` | none | Gelbooru API key |
| `gelbooru_user_id` | If `BOORU_SOURCE=gelbooru` | none | Gelbooru user ID |
| `LLM_MIN_SWIPES` | No | `10` | Swipes required before LLM analysis starts |
| `LLM_MAX_TAGS` | No | `30` | Max number of cumulative tags sent to the LLM |
| `LLM_TAG_FILTER_MIN_COUNT` | No | `1` | Minimum absolute tag score to include in LLM input |
| `LLM_USE_STRUCTURED_OUTPUT` | No | `true` | Whether to validate LLM output against the response schema |
| `LLM_RECENT_POSITIVE` | No | `10` | Number of top recent positive tags sent to the LLM |
| `LLM_RECENT_NEGATIVE` | No | `10` | Number of top recent negative tags sent to the LLM |
| `BOORU_TAGS_PER_SEARCH` | No | `5` | Max tags used in the primary booru search |
| `BOORU_TAGS_PER_SEARCH_FALLBACK` | No | `3` | Max number of top liked tags used in the fallback search query |
| `RANDOM_IMAGE_CHANCE` | No | `5` | Percent chance to skip recommendation logic and show a random image |
| `DOUBLE_LIKED_NEVER_IGNORE` | No | `false` | Whether double-liked images are exempt from repeat filtering |
| `BOORU_SEARCH_LIMIT` | No | `100` | Images requested per booru search page |
| `BOORU_SEARCH_PAGES` | No | `5` | Number of pages to scan before giving up |
| `BOORU_SEARCH_SLEEP` | No | `0.15` | Delay between paginated booru requests in seconds |

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
