from __future__ import annotations

import logging
import sys
from logging.config import dictConfig

from IMH.IMH_no_api.IMH_no_api.core.request_id import get_request_id


class RequestIdFilter(logging.Filter):
    """현재 컨텍스트의 request_id를 로그 레코드에 주입하는 필터."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


def setup_logging() -> None:
    """IMH 모듈을 위한 중앙 집중식 로깅 설정."""
    
    LOG_FORMAT = (
        "[%(asctime)s] [%(levelname)s] [%(request_id)s] "
        "%(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": RequestIdFilter,
            },
        },
        "formatters": {
            "standard": {
                "format": LOG_FORMAT,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "filters": ["request_id"],
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "IMH": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            # uvicorn 로그도 커스텀 핸들러를 사용하게 할 수 있지만, 
            # 일단 IMH 로그에 집중함.
        },
    }

    dictConfig(logging_config)
