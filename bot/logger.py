# logger.py
import logging
import sys
import os

def setup_logger(name="tg-bot"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    # Terminalga yozish uchun
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # Faylga yozish uchun (log papkasi bor bo‘lishi kerak!)
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(log_dir, "bot.log"), encoding="utf-8")
    file_handler.setFormatter(formatter)

    # Faqat bir marta qo‘shish
    if not logger.hasHandlers():
        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)

    return logger

logger = setup_logger()
