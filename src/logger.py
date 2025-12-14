import os
from logging import config, getLevelName, getLogger

LOGGER_NAME = "api"
LOG_LEVEL = getLevelName(os.getenv("LOG_LEVEL", "INFO"))  # DEBUG, WARNING, ERROR

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s %(asctime)s - %(client_addr)s - "%(request_line)s" %(status_code)s',
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": True,
        },
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": True,
        },
    },
    "handlers": {
        "access": {"class": "logging.StreamHandler", "formatter": "access", "stream": "ext://sys.stdout"},
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        LOGGER_NAME: {"handlers": ["default"], "level": LOG_LEVEL, "propagate": False},
        "uvicorn": {"handlers": ["default"], "level": LOG_LEVEL, "propagate": True},
        "uvicorn.access": {"handlers": ["access"], "level": LOG_LEVEL, "propagate": False},
        "uvicorn.error": {"level": LOG_LEVEL, "propagate": False},
    },
}

# Apply the modified logging configuration
config.dictConfig(log_config)

# Get the "api" logger
logger = getLogger(LOGGER_NAME)
