import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> logging.Logger:
    log_dir = Path(os.environ.get("ANALOG_DVR_LOG_DIR", "/opt/ively/analog-dvr-edge/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("analog_dvr_edge")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=5_000_000, backupCount=7)
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = setup_logging()
