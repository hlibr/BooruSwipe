"""BooruSwipe - Booru image preference learning application."""

import argparse
import logging
import os
import webbrowser
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from booruswipe.db.repository import Repository
from booruswipe.gelbooru.client import DanbooruClient, GelbooruClient
from booruswipe.llm.client import LLMClient
from booruswipe.api.deps import set_dependencies, set_verbose_mode
from booruswipe.api.routes import router, _session
from dotenv import load_dotenv

repo: Optional[Repository] = None
danbooru_client: Optional[DanbooruClient] = None
gelbooru_client: Optional[GelbooruClient] = None
llm_client: Optional[LLMClient] = None
llm_settings: dict[str, str] = {}
verbose: bool = False


class ColorizedFormatter(logging.Formatter):
    """Custom formatter with ANSI color coding for log categories."""
    
    COLORS = {
        "STARTUP": "\033[34m",
        "SWIPE": "\033[32m",
        "LLM": "\033[33m",
        "LLM_SUMMARY": "\033[34m",
        "IMAGE": "\033[35m",
        "ERROR": "\033[31m",
        "DEFAULT": "\033[37m",
    }
    
    def format(self, record):
        category = getattr(record, "category", "DEFAULT")
        color = self.COLORS.get(category, self.COLORS["DEFAULT"])
        reset = "\033[0m"
        record.msg = f"{color}[{category}] {record.msg}{reset}"
        return super().format(record)


def log_startup(msg: str):
    logging.info(msg, extra={"category": "STARTUP"})


def log_swipe(msg: str):
    logging.info(msg, extra={"category": "SWIPE"})


def log_llm(msg: str):
    logging.info(msg, extra={"category": "LLM"})


def log_image(msg: str):
    logging.info(msg, extra={"category": "IMAGE"})


def log_error(msg: str):
    logging.error(msg, extra={"category": "ERROR"})


async def ensure_double_liked_table_exists(repository):
    """Create double_liked_images table if it doesn't exist"""
    async with repository.async_sessionmaker() as session:
        from sqlalchemy import inspect
        
        def check_table(sync_session):
            conn = sync_session.connection()
            return inspect(conn).has_table("double_liked_images")
        
        table_exists = await session.run_sync(check_table)
        
        if not table_exists:
            from booruswipe.db.database import Base
            await session.run_sync(Base.metadata.create_all)
            log_startup("Created double_liked_images table")
        else:
            log_startup("double_liked_images table already exists")


def _get_settings_path() -> Path:
    """Get the path to the settings file."""
    env_path = os.getenv("BOORUSWIPE_CONFIG")
    if env_path:
        return Path(env_path).expanduser()

    cwd_path = Path.cwd() / "booru.conf"
    if cwd_path.exists():
        return cwd_path

    return Path(__file__).parent.parent.parent / "booru.conf"


def _load_llm_settings() -> dict[str, str]:
    """Load LLM settings from .env file."""
    settings_path = _get_settings_path()
    settings = {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "",
    }
    if settings_path.exists():
        with open(settings_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower()
                    if key in settings:
                        settings[key] = value.strip()
    return settings


def _load_danbooru_settings() -> dict[str, str]:
    """Load Danbooru API settings from .env file."""
    settings_path = _get_settings_path()
    settings = {
        "danbooru_api_key": "",
        "danbooru_user_id": "",
    }
    if settings_path.exists():
        with open(settings_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower()
                    if key in settings:
                        settings[key] = value.strip()
    return settings


def _load_gelbooru_settings() -> dict[str, str]:
    """Load Gelbooru API settings from .env file."""
    settings_path = _get_settings_path()
    settings = {
        "gelbooru_api_key": "",
        "gelbooru_user_id": "",
    }
    if settings_path.exists():
        with open(settings_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower()
                    if key in settings:
                        settings[key] = value.strip()
    return settings


def _save_llm_settings(settings: dict[str, str]) -> None:
    """Save LLM settings to .env file."""
    settings_path = _get_settings_path()
    with open(settings_path, "w") as f:
        f.write(f"api_key={settings.get('api_key', '')}\n")
        f.write(f"base_url={settings.get('base_url', '')}\n")
        f.write(f"model={settings.get('model', '')}\n")


@asynccontextmanager
async def lifespan(app):
    global repo, danbooru_client, gelbooru_client, llm_client, llm_settings, verbose
    LLM_MAX_TAGS = int(os.getenv("LLM_MAX_TAGS", "100"))
    BOORU_SOURCE = os.getenv("BOORU_SOURCE", "danbooru").lower()
    BOORU_TAGS_PER_SEARCH = int(os.getenv("BOORU_TAGS_PER_SEARCH", "2"))
    repo = Repository()
    await repo.init_db()
    
    migrated = await repo.migrate_existing_swipes()
    if migrated > 0:
        log_startup(f"Migration complete: {migrated} swipes copied to swiped_images")
    
    await ensure_double_liked_table_exists(repo)
    
    total_swipes = await repo.get_total_swipe_count()
    _session.swipe_count = total_swipes
    log_startup(f"Loaded {total_swipes} swipes from database")
    
    tag_counts = await repo.get_tag_counts()
    log_startup(f"Loaded {len(tag_counts)} unique tags from database")
    
    log_startup(f"Using booru source: {BOORU_SOURCE}")
    log_startup(f"Using up to {BOORU_TAGS_PER_SEARCH} tags per search")
    
    if BOORU_SOURCE == "gelbooru":
        gelbooru_settings = _load_gelbooru_settings()
        gelbooru_client = GelbooruClient(
            api_key=gelbooru_settings.get("gelbooru_api_key"),
            user_id=gelbooru_settings.get("gelbooru_user_id"),
        )
        await gelbooru_client.__aenter__()
        if gelbooru_settings.get("gelbooru_api_key") and gelbooru_settings.get("gelbooru_user_id"):
            log_startup("Gelbooru client initialized with API authentication")
        else:
            log_startup("Gelbooru client initialized (no API credentials)")
    else:
        danbooru_settings = _load_danbooru_settings()
        danbooru_client = DanbooruClient(
            api_key=danbooru_settings.get("danbooru_api_key"),
            user_id=danbooru_settings.get("danbooru_user_id"),
        )
        await danbooru_client.__aenter__()
        log_startup("Danbooru client initialized")
    
    llm_settings = _load_llm_settings()
    api_key = llm_settings.get("api_key")
    model = llm_settings.get("model")
    
    if api_key and model:
        try:
            llm_client = LLMClient(
                api_key=api_key,
                model=model,
                base_url=llm_settings.get("base_url", "https://api.openai.com/v1"),
                verbose=verbose,
            )
            log_startup(f"LLM configured with model: {model}")
            log_startup(f"LLM will analyze top {LLM_MAX_TAGS} tags")
        except Exception as e:
            llm_client = None
            log_error(f"LLM initialization failed: {e}")
            log_startup("⚠️ LLM features DISABLED due to initialization error")
    else:
        llm_client = None
        if api_key and not model:
            log_startup("⚠️ LLM DISABLED: API key set but no model specified")
            log_startup(f"LLM will analyze top {LLM_MAX_TAGS} tags (when enabled)")
        elif not api_key and model:
            log_startup("⚠️ LLM DISABLED: Model set but no API key specified")
            log_startup(f"LLM will analyze top {LLM_MAX_TAGS} tags (when enabled)")
        else:
            log_startup("LLM NOT configured (no settings found)")
    
    set_dependencies(
        repository=repo,
        danbooru_client=danbooru_client,
        gelbooru_client=gelbooru_client,
        llm_client=llm_client,
    )
    set_verbose_mode(verbose)
    
    yield
    if danbooru_client:
        await danbooru_client.__aexit__(None, None, None)
    if gelbooru_client:
        await gelbooru_client.__aexit__(None, None, None)
    await repo.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(router)


_STATIC_DIR = Path(__file__).parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")


def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="BooruSwipe - Danbooru image preference learning application")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument('--reset-db', action='store_true', 
                        help='Reset all data (swipes, tag counts, profile) and start fresh')
    args = parser.parse_args()

    if args.reset_db:
        confirm = input("⚠️  WARNING: This will DELETE ALL DATA. Are you sure? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return
        
        from booruswipe.db.database import DB_PATH
        import sqlite3
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Drop all tables (reverse order for foreign keys)
        tables = [
            "double_liked_images",
            "swiped_images",
            "preference_profiles",
            "tag_counts",
            "swipes"
        ]
        
        for table in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                print(f"✅ Dropped {table}")
            except sqlite3.OperationalError as e:
                print(f"⚠️  Error dropping {table}: {e}")
        
        conn.commit()
        conn.close()
        print("✅ Database reset successfully. Tables will be recreated on startup.")

    global verbose
    verbose = args.verbose

    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.setFormatter(ColorizedFormatter())
        log_startup("Starting BooruSwipe in verbose mode")
    else:
        logging.basicConfig(
            level=logging.ERROR,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.setFormatter(ColorizedFormatter())

    env_file = _get_settings_path()
    load_dotenv(dotenv_path=env_file)
    log_startup(f"Loaded config file: {env_file}")

    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000")
    
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
