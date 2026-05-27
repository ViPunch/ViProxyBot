from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv

from src.config import AppConfig
from src.interface.telegram.bot import run_bot


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("event", "actor_id", "protocol", "action"):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def main() -> None:
    load_dotenv()

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)

    config = AppConfig.from_env()
    asyncio.run(run_bot(config))


if __name__ == "__main__":
    main()
