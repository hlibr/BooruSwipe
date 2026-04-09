# BooruSwipe

A Tinder-like image browser for [Gelbooru](https://gelbooru.com) and [Danbooru](https://danbooru.donmai.us) with AI-powered next image selection.

Swipe right on images you like, left on ones you don't. BooruSwipe tracks tag-level feedback and uses an LLM to continuously refine its search queries — so the longer you use it, the more it learns what you're into.

> **New to boorus?** Gelbooru and Danbooru are large community image boards, primarily anime and illustration. They tag images extensively, which is what makes tag-based recommendation possible.



https://github.com/user-attachments/assets/3214239a-606b-4f72-a898-6bcedf7c2ff3



---

## How It Works

1. The first batch of images is random (configurable, default: 10)
2. As you swipe, BooruSwipe builds a picture of your tag preferences
3. After enough swipes, it asks an LLM to generate better search tags based on what you've liked and disliked
4. Those tags drive the next round of image fetching
5. If no LLM is configured, it falls back to your top liked tags directly

One important nuance: BooruSwipe improves *search queries*, not image ranking. It's adaptive search term generation — it won't score individual images within results, just get better at finding the right pool to pull from.

You can also submit stronger feedback with the `x2` buttons. Holding an `x2` button opens `x3` / `x4` / `x5` multipliers for even stronger like or dislike signals.

---

## Requirements

- Python 3.10+
- Credentials for one of:
  - **Gelbooru** — [get your API key and user ID here](https://gelbooru.com/index.php?page=account&s=options) (bottom of the page)
  - **Danbooru** — [get your API key and username here](https://danbooru.donmai.us/profile)
- An LLM (optional, but recommended):
  - Any OpenAI-compatible API
  - [Ollama](https://ollama.com)
  - [LM Studio](https://lmstudio.ai)
  - [llama.cpp](https://github.com/ggml-org/llama.cpp)

---

## Quick Start

```bash
git clone https://github.com/hlibr/BooruSwipe.git
cd BooruSwipe
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install .
cp booru.conf.example booru.conf
```

Edit `booru.conf`. Minimum config for each source:

**Gelbooru:**
```bash
BOORU_SOURCE=gelbooru
gelbooru_api_key=YOUR_GELBOORU_API_KEY
gelbooru_user_id=YOUR_GELBOORU_USER_ID

# LLM (optional)
api_key=your-api-key
base_url=https://api.openai.com/v1
model=gpt-4o-mini
```

**Danbooru:**
```bash
BOORU_SOURCE=danbooru
danbooru_api_key=YOUR_DANBOORU_API_KEY
danbooru_user_id=YOUR_DANBOORU_LOGIN

# LLM (optional)
api_key=your-api-key
base_url=https://api.openai.com/v1
model=gpt-4o-mini
```

Then run:

```bash
python -m booruswipe
```

Open [http://localhost:8000](http://localhost:8000). Give it at least 10 swipes before expecting recommendations to kick in.

For verbose logs:

```bash
python -m booruswipe --verbose
```

---

## Docker

```bash
cp booru.conf.example booru.conf
# edit booru.conf, then:
docker compose build
docker compose up
```
Open http://localhost:8000.

The compose setup mounts `./booru.conf` into the container, persists the SQLite database in a named volume, and runs with `--verbose`.

**If your LLM runs locally**, don't use `localhost` in `booru.conf` — inside Docker that refers to the container itself. Use `host.docker.internal` instead:

```bash
# LM Studio on host
base_url=http://host.docker.internal:1234/v1

# Ollama on host
base_url=http://host.docker.internal:11434/v1
```

If you only change `booru.conf`, a full rebuild isn't needed — just restart:

```bash
docker compose restart
```

Other useful commands:

```bash
docker compose logs -f
docker compose down
docker compose down -v   # also removes the database volume
```

---

## Configuration

All configuration lives in `booru.conf`.

### Booru source

```bash
BOORU_SOURCE=gelbooru  # or: danbooru
```

### LLM providers

| Provider | `api_key` | `base_url` | `model` |
|---|---|---|---|
| OpenAI | `sk-...` | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Ollama | `ollama` | `http://localhost:11434/v1` | `llama3.2` |
| LM Studio | `lm-studio` | `http://localhost:1234/v1` | `local-model` |

### All settings

| Setting | Required | Default | Description |
|---|---|---|---|
| `BOORU_SOURCE` | Yes | `gelbooru` | Which booru to use (`gelbooru` or `danbooru`) |
| `gelbooru_api_key` | If Gelbooru | — | Gelbooru API key |
| `gelbooru_user_id` | If Gelbooru | — | Gelbooru user ID |
| `danbooru_api_key` | If Danbooru | — | Danbooru API key |
| `danbooru_user_id` | If Danbooru | — | Danbooru login name |
| `api_key` | No | — | LLM provider API key |
| `base_url` | No | `https://api.openai.com/v1` | LLM provider base URL |
| `model` | No | — | Model name for chat completions |
| `LLM_MIN_SWIPES` | No | `10` | Swipes required before LLM kicks in |
| `LLM_MAX_TAGS` | No | `30` | Max cumulative tags sent to the LLM |
| `LLM_TAG_FILTER_MIN_COUNT` | No | `1` | Minimum tag score to include in LLM input |
| `LLM_USE_STRUCTURED_OUTPUT` | No | `true` | Validate LLM output against response schema |
| `LLM_RECENT_POSITIVE` | No | `10` | Recent positive tags sent to LLM |
| `LLM_RECENT_NEGATIVE` | No | `10` | Recent negative tags sent to LLM |
| `LLM_RECENT_FILTER_CUMULATIVE_LIKES` | No | `true` | Filter recent positives already in cumulative likes before sending to LLM |
| `BOORU_TAGS_PER_SEARCH` | No | `5` | Max tags used in the primary search query |
| `BOORU_TAGS_PER_SEARCH_FALLBACK` | No | `3` | Max tags used in the fallback search query |
| `RANDOM_IMAGE_CHANCE` | No | `5` | % chance to show a random image instead of a recommendation |
| `DOUBLE_LIKED_NEVER_IGNORE` | No | `false` | Exempt double-liked images from repeat filtering |
| `BOORU_SEARCH_LIMIT` | No | `100` | Images requested per search page |
| `BOORU_SEARCH_PAGES` | No | `5` | Pages to scan before giving up |
| `BOORU_SEARCH_SLEEP` | No | `0.15` | Delay between paginated requests (seconds) |

---

## Data

BooruSwipe stores everything locally in a SQLite database:

- **`swipes`** — each swipe event with booru source, tags, URLs, and weight
- **`tag_counts`** — long-term like/dislike counters per tag
- **`swiped_images`** — seen image IDs to reduce repeats
- **`double_liked_images`** — IDs exempted from repeat filtering
- **`preference_profiles`** — latest LLM-generated tag recommendations

---

## Development

```bash
pytest -q                          # run tests
python -m booruswipe --reset-db    # wipe the local database
```

---

## Limitations

- **Single-user:** session state lives in process memory, not per-user sessions
- **No candidate ranking:** recommendation improves search terms, not image ordering within results

## Possible improvements

- Score retrieved images instead of picking randomly from search results
- Track tag *combinations*, not just independent tags
- Smarter exploration beyond random chance
- Per-user session handling
- Live integration tests for Danbooru, Gelbooru, and LLM providers

---

## License

MIT
