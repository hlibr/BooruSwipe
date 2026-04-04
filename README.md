# BooruSwipe

**Tinder-style image preference learner powered by LLM**

BooruSwipe is a cross-platform web application that helps you discover and learn your visual preferences using AI. Swipe through images from Danbooru or Gelbooru, and an LLM analyzes your choices to recommend similar content you'll love.

## Features

- 🎯 **Swipe Interface**: Tinder-style left/dislike, right/like interaction
- 🧠 **LLM-Powered Learning**: Your preferences are analyzed by AI to understand what you like
- 🔄 **Smart Recommendations**: 3-level fallback system (LLM → tag frequencies → random)
- 💾 **Persistent Storage**: All swipes and preferences saved in local SQLite database
- 🌐 **Cross-Platform**: Works on any device with a web browser
- 🔧 **Flexible LLM Support**: Works with OpenAI, Ollama, LM Studio, or any OpenAI-compatible API
- 🎨 **Dual Booru Support**: Switch between Danbooru or Gelbooru as your image source
- 🔒 **Privacy-First**: All data stored locally, no cloud dependencies
- ⚡ **Weighted Swipes**: Double-like/dislike buttons (x2) for stronger preference signals
- 🎯 **Exact Tag Control**: LLM returns exactly N tags (configurable via BOORU_TAGS_PER_SEARCH)
- ➖ **Negative Tag Support**: LLM can recommend excluding tags with `-tagname` syntax
- 🔄 **Progressive Fallback**: 0.5s delays between fallback levels for better performance
- ✅ **JSON Schema Validation**: Strict LLM output validation (LLM_USE_STRUCTURED_OUTPUT)
- ❤️ **Double-Like Feature**: Weight=2 swipes are never ignored in future selections
- 🎲 **Random Image Chance**: Configurable percentage chance for completely random images (RANDOM_IMAGE_CHANCE)
- ⚡ **Fast Fallback**: Half-tags random removal for faster image selection (2 API calls instead of 12+)

## Requirements

- Python 3.10 or higher
- An OpenAI-compatible LLM API (one of the following):
  - OpenAI API key ([https://platform.openai.com](https://platform.openai.com))
  - Ollama ([https://ollama.ai](https://ollama.ai)) - free, local
  - LM Studio ([https://lmstudio.ai](https://lmstudio.ai)) - free, local
- Booru API access (Danbooru or Gelbooru - optional, works without credentials)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd booruswipe
```

### 2. Install Dependencies

```bash
pip install -e .
```

This installs all required packages:

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `httpx` - Async HTTP client
- `openai` - LLM client
- `sqlalchemy` + `aiosqlite` - Database
- `python-dotenv` - Environment configuration

## Usage

### Starting the Server

```bash
python -m booruswipe
```

The server will start on `http://localhost:8000`

Add `-v` or `--verbose` flag for detailed logging:

```bash
python -m booruswipe --verbose
```

### Configuration

1. Copy the example config file:

```bash
cp booru.conf.example booru.conf
```

2. Edit `booru.conf` with your settings

#### Booru Source Configuration

**Choose your image source** - Danbooru or Gelbooru:

```bash
# Booru source: 'danbooru' or 'gelbooru'
BOORU_SOURCE=danbooru
```

**Danbooru** (optional - works without credentials):

```bash
danbooru_api_key=YOUR_DANBOORU_API_KEY
danbooru_user_id=YOUR_DANBOORU_LOGIN
```

Get your Danbooru API key from: [https://danbooru.donmai.us/user_feedbacks/new](https://danbooru.donmai.us/user_feedbacks/new)

**Gelbooru** (optional - works without credentials):

```bash
gelbooru_api_key=YOUR_GELBOORU_API_KEY
gelbooru_user_id=YOUR_GELBOORU_USER_ID
```

Get your Gelbooru API key from: [https://gelbooru.com/index.php?page=account&edit=api](https://gelbooru.com/index.php?page=account&edit=api)

#### LLM Configuration

Configure LLM settings for preference learning:

```bash
api_key=your-api-key-here
base_url=https://api.openai.com/v1
model=gpt-4o-mini
```

**Example Configurations:**

| Provider | api_key | base_url | model |
| --- | --- | --- | --- |
| OpenAI | sk-... | https://api.openai.com/v1 | gpt-4o-mini |
| Ollama | ollama | http://localhost:11434/v1 | llama3.2 |
| LM Studio | lm-studio | http://localhost:1234/v1 | local-model |

#### Advanced Configuration

**LLM Analysis Control:**

```bash
# Minimum swipes before LLM analysis triggers (default: 5)
LLM_MIN_SWIPES=5

# Max tags to send to LLM for analysis (default: 100)
LLM_MAX_TAGS=100

# Minimum tag count for filtering (default: 1)
LLM_TAG_FILTER_MIN_COUNT=1

# Enable strict JSON schema validation for LLM responses (default: true)
LLM_USE_STRUCTURED_OUTPUT=true
```

**Booru Search Behavior:**

```bash
# Number of tags to use per booru search (default: 2)
BOORU_TAGS_PER_SEARCH=2
```

### Testing LLM Connection

You can test your LLM connection via the API:

```bash
curl -X POST http://localhost:8000/api/settings/test \
  -H "Content-Type: application/json" \
  -d '{"api_key":"your-key","base_url":"https://api.openai.com/v1","model":"gpt-4o-mini","prompt":"Hello"}'
```

Or configure via the settings endpoint:

```bash
curl -X POST http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"api_key":"your-key","base_url":"https://api.openai.com/v1","model":"gpt-4o-mini"}'
```

### Using the Application

1. Open `http://localhost:8000` in your browser
2. Configure LLM settings if not already set (via API or `.env` file)
3. Start swiping! Images appear one at a time
4. Swipe **right** to like, **left** to dislike
5. Use **x2 buttons** for weighted swipes (like/dislike with weight=2)
6. After `LLM_MIN_SWIPES` (default: 5) swipes, the LLM analyzes your preferences
7. Get personalized recommendations based on your taste

## Project Structure

```
booruswipe/
├── src/booruswipe/
│   ├── __main__.py              # Application entry point, FastAPI app
│   ├── api/
│   │   ├── routes.py            # API endpoints (/api/image, /api/swipe, /api/stats)
│   │   └── deps.py              # Dependency injection setup
│   ├── db/
│   │   ├── models.py            # SQLAlchemy models (5 models)
│   │   ├── repository.py        # Data access layer (CRUD operations)
│   │   └── database.py          # Database configuration (SQLite)
│   ├── gelbooru/
│   │   ├── client.py            # DanbooruClient & GelbooruClient
│   │   └── models.py            # Image data models
│   ├── llm/
│   │   ├── client.py            # OpenAI-compatible LLM client
│   │   ├── preference_learner.py # LLM preference analysis with JSON schema
│   │   └── prompts.py           # System prompts for LLM
│   └── static/
│       ├── index.html           # Frontend HTML
│       ├── app.js               # Frontend JavaScript (swipe logic)
│       └── styles.css           # Frontend styles
├── tests/
│   ├── test_db.py               # Database tests
│   └── test_llm.py              # LLM integration tests
├── pyproject.toml               # Project configuration
└── README.md                    # This file
```

## Architecture

### High-Level Design

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Browser   │ ───► │  FastAPI App │ ◄──► │   SQLite    │
│  (Frontend) │      │  (Backend)   │      │  Database   │
└─────────────┘      └──────┬───────┘      └─────────────┘
                            │
                   ┌────────┴────────┐
                   ▼                 ▼
          ┌────────────┐    ┌────────────┐
          │  Danbooru  │    │  LLM API   │
          │   API      │    │ (Optional) │
          └────────────┘    └────────────┘
```

### Image Selection Flow (3-Level Fallback)

1. **Level 1: LLM Recommendations** - Uses learned preferences; tries all tags first, then removes half randomly if no results (2 API calls max)
2. **Level 2: Tag Frequencies** - Falls back to most-liked tags from swipe history (tries all tags once)
3. **Level 3: Random** - Random image from booru source

**Fast Fallback:** Level 1 uses random half-tag removal (2 API calls max vs 12+ with old one-by-one approach)

### Random Image Chance

Set `RANDOM_IMAGE_CHANCE` to inject variety into your feed:

```bash
# 10% chance of completely random image (default)
RANDOM_IMAGE_CHANCE=10

# 20% chance for more variety
RANDOM_IMAGE_CHANCE=20

# Never random (only recommendations)
RANDOM_IMAGE_CHANCE=0

# Always random (bypass all recommendations)
RANDOM_IMAGE_CHANCE=100
```

Random images are selected **before** the fallback logic runs, bypassing LLM and tag frequency recommendations entirely.

### LLM Analysis Trigger

- Triggers after `LLM_MIN_SWIPES` (default: 5) swipes
- Analyzes tag frequency data (liked vs disliked)
- Sends top `LLM_MAX_TAGS` (default: 100) tags to LLM
- LLM returns JSON with:
  - `liked_tags`: Tags user prefers
  - `disliked_tags`: Tags user avoids
  - `recommended_search_tags`: EXACTLY `BOORU_TAGS_PER_SEARCH` tags (supports negative tags like `-tagname`)
  - `preferences_summary`: Natural language summary
- Profile saved to database and used for future recommendations
- **JSON Schema Validation**: Controlled by `LLM_USE_STRUCTURED_OUTPUT` (default: true)

### Data Models

- **Swipe**: Records each swipe (image_id, tags, liked/disliked, timestamp, booru source)
- **TagCount**: Tracks like/dislike counts per tag with net count calculation
- **SwipedImage**: Prevents repeat images (tracks seen IDs, last 1000)
- **PreferenceProfile**: Stores LLM-learned preferences (liked/disliked tags, recommendations)
- **DoubleLikedImage**: Tracks double-liked images (weight=2) that are never ignored

## Data Storage

- **Config file** (`booru.conf`) - In project root, contains LLM and Booru API settings
- **Database** (`~/.booruswipe/booruswipe.db`) - SQLite database with:
  - Swipe history (image ID, tags, liked/disliked, booru source, timestamp)
  - Tag counts (like/dislike counts per tag with net count)
  - Swiped image IDs (last 1000 to prevent repeats)
  - Double-liked image IDs (never ignored in future selections)
  - Learned preferences (LLM-analyzed profile)

## API Endpoints

All endpoints are prefixed with `/api`.

### Image Endpoints

#### `GET /api/image`

Get the next image to display. Uses 3-level fallback (LLM → tags → random).

**Response:**

```json
{
  "id": 123456,
  "url": "https://danbooru.donmai.us/posts/123456",
  "tags": ["tag1", "tag2"],
  "sample_url": "https://...",
  "width": 1920,
  "height": 1080
}
```

#### `GET /api/image/{image_id}`

Proxy image through backend (bypasses hotlink protection for Gelbooru).

**Response:** Raw image bytes

### Swipe Endpoint

#### `POST /api/swipe`

Record a swipe and optionally get next image.

**Request:**

```json
{
  "image_id": 123456,
  "direction": "right",
  "weight": 1
}
```

**Parameters:**

- `image_id`: ID of the image
- `direction`: "left" (dislike) or "right" (like)
- `weight`: Swipe weight (1 = normal, 2 = double-like/dislike). Weight=2 marks image as "never ignore"

**Response:**

```json
{
  "success": true,
  "next_image": { ... }
}
```

### Settings Endpoints

#### `GET /api/settings`

Get current LLM settings.

**Response:**

```json
{
  "api_key": "***",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o-mini"
}
```

#### `POST /api/settings`

Save LLM settings to `booru.conf`.

**Request:**

```json
{
  "api_key": "your-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o-mini"
}
```

#### `POST /api/settings/test`

Test LLM connection with provided settings.

**Request:**

```json
{
  "api_key": "your-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "prompt": "Hello"
}
```

**Response:**

```json
{
  "success": true,
  "message": "Connection successful",
  "response": "Hello! How can I help you?"
}
```

### Stats Endpoint

#### `GET /api/stats`

Get swipe statistics.

**Response:**

```json
{
  "total_swipes": 42,
  "likes": 28,
  "dislikes": 14,
  "session_swipes": 15
}
```

### Health Check

#### `GET /health`

Health check endpoint.

**Response:**

```json
{
  "status": "ok"
}
```

## Troubleshooting

### "No module named 'booruswipe'"

Run `pip install -e .` from the project root.

### LLM connection fails

- Check your API key is correct in `booru.conf`
- For Ollama/LM Studio, ensure the server is running
- Test with:
  - Ollama: `curl http://localhost:11434/api/tags`
  - LM Studio: `curl http://localhost:1234/v1/models`
- Check logs for error messages (run with `--verbose` flag)

### Port 8000 already in use

Modify `src/booruswipe/__main__.py` to use a different port:

```python
uvicorn.run(app, host="0.0.0.0", port=8001)  # Use different port
```

### Database errors

Reset the database (all swipe history will be lost):

```bash
rm ~/.booruswipe/booruswipe.db
```

Or use the reset flag:

```bash
python -m booruswipe --reset-db
```

### No images loading

- Check your internet connection
- Booru API may be temporarily unavailable
- Try refreshing the page
- Check if `BOORU_SOURCE` is set correctly in `.env`
- For Gelbooru: hotlink protection may block images - they're proxied through backend

### LLM not analyzing preferences

- Ensure `LLM_MIN_SWIPES` threshold is met (default: 5)
- Check that API key and model are configured
- Look for LLM logs in verbose mode
- Test LLM connection via `/api/settings/test`

### Images keep repeating

- The app tracks last 1000 swiped images to prevent repeats
- If you've swiped >1000 images, some may reappear
- Solution: Expand your tag variety or use more specific recommendations

### Rate limiting from Booru API

- Danbooru: Register for API key to increase rate limits
- Gelbooru: Use API credentials for higher limits
- Reduce request frequency or add caching layer

## Development

### Running Tests

```bash
pytest
```

Run specific test files:

```bash
pytest tests/test_db.py
pytest tests/test_llm.py
```

### Code Style

This project follows standard Python conventions:

- **Type hints** used throughout
- **Async/await** for all I/O operations
- **Dependency injection** for testability
- **Pydantic models** for request/response validation

### Adding New Features

**New Booru source:**

1. Create client in `src/booruswipe/newbooru/client.py`
2. Follow `DanbooruClient`/`GelbooruClient` pattern
3. Add to dependency injection in `__main__.py`

**New API endpoint:**

1. Add route to `src/booruswipe/api/routes.py`
2. Use existing dependencies via `Depends()`
3. Follow Pydantic model pattern for validation

### Debugging

Enable verbose logging:

```bash
python -m booruswipe --verbose
```

Log categories (colorized):

- `[STARTUP]` - Application initialization
- `[SWIPE]` - Swipe events
- `[LLM]` - LLM API calls and analysis
- `[IMAGE]` - Image selection and fetching
- `[ERROR]` - Errors

### Environment Variables Reference

Complete list of all configuration options:

| Variable | Description | Default | Example |
| --- | --- | --- | --- |
| BOORU_SOURCE | Booru source (danbooru or gelbooru) | danbooru | gelbooru |
| danbooru_api_key | Danbooru API key | (none) | abc123... |
| danbooru_user_id | Danbooru login name | (none) | your_username |
| gelbooru_api_key | Gelbooru API key | (none) | abc123... |
| gelbooru_user_id | Gelbooru user ID | (none) | 12345 |
| api_key | LLM API key | (none) | sk-... |
| base_url | LLM API base URL | https://api.openai.com/v1 | http://localhost:11434/v1 |
| model | LLM model name | (none) | gpt-4o-mini |
| LLM_MIN_SWIPES | Swipes before LLM analysis | 5 | 10 |
| LLM_MAX_TAGS | Max tags sent to LLM | 100 | 50 |
| LLM_TAG_FILTER_MIN_COUNT | Min tag count for filtering | 1 | 2 |
| BOORU_TAGS_PER_SEARCH | Tags per booru search | 2 | 3 |
| LLM_USE_STRUCTURED_OUTPUT | Enable strict JSON schema validation | true | false |
| RANDOM_IMAGE_CHANCE | Percentage chance of random image | 10 | 20 |
| DOUBLE_LIKED_NEVER_IGNORE | Double-liked images never ignored | true | false |

### Command Reference

```bash
# Start server
python -m booruswipe

# Start with verbose logging
python -m booruswipe --verbose

# Reset database (confirm prompt)
python -m booruswipe --reset-db

# Install in development mode
pip install -e .

# Run tests
pytest
```

## License

MIT License - feel free to use, modify, and distribute.

## Acknowledgments

- **Danbooru** - Image board API ([https://danbooru.donmai.us](https://danbooru.donmai.us))
- **Gelbooru** - Image board API ([https://gelbooru.com](https://gelbooru.com))
- **FastAPI** - Modern Python web framework
- **OpenAI** - LLM API (or compatible alternatives like Ollama, LM Studio)

**Built with ❤️ using FastAPI and LLMs**
