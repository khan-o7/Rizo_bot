"""Centralized configuration loaded from .env"""
import logging, os, pathlib
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
_ENV_PATH = pathlib.Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

if not _ENV_PATH.exists():
    logger.warning(f"⚠️  .env fayl topilmadi: {_ENV_PATH}")
else:
    logger.info(f"✅ .env yuklandi: {_ENV_PATH}")


@dataclass
class Config:
    BOT_TOKEN       : str           = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    ADMIN_IDS       : List[int]     = field(default_factory=list)
    COURIER_GROUP_ID: Optional[int] = field(default=None)      # Kuryer Telegram guruhi ID
    DB_URL          : str           = field(default_factory=lambda: os.getenv("DB_URL", "sqlite+aiosqlite:///./food_bot.db"))
    CONVERSATION_TIMEOUT: int = 900

    def __post_init__(self) -> None:
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN .env faylida yo'q!")

        raw = os.getenv("ADMIN_IDS", "").strip()
        parsed = []
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                parsed.append(int(part))
            elif part:
                logger.warning(f"ADMIN_IDS da noto'g'ri qiymat: '{part}'")
        self.ADMIN_IDS = parsed

        raw_group = os.getenv("COURIER_GROUP_ID", "").strip()
        if raw_group.lstrip("-").isdigit():
            self.COURIER_GROUP_ID = int(raw_group)
            logger.info(f"✅ Kuryer guruhi: {self.COURIER_GROUP_ID}")
        else:
            logger.warning("⚠️  COURIER_GROUP_ID .env da yo'q — kuryer guruhi o'chirilgan.")

        if not self.ADMIN_IDS:
            logger.warning("⚠️  ADMIN_IDS bo'sh! .env ni tekshiring.")
        else:
            logger.info(f"✅ Adminlar: {self.ADMIN_IDS}")

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.ADMIN_IDS

    def has_courier_group(self) -> bool:
        return self.COURIER_GROUP_ID is not None


config = Config()
