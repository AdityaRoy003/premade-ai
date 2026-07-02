import os
import logging

def setup_logging(log_file: str = "trading_bot.log", console_level: int = logging.INFO, file_level: int = logging.DEBUG):
    """
    Sets up a dual logging system:
    - Console logger for clean user-facing messages.
    - File logger for detailed API request/response logs.
    """
    logger = logging.getLogger("trading_bot")
    logger.setLevel(logging.DEBUG)  # Capture all levels, handle filtering in handlers

    # Prevent duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. File Handler
    try:
        # Save logs in the parent folder of the bot package (project root)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_path = os.path.join(project_root, log_file)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(filename)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Failed to initialize file logger: {e}")

    return logger

# Create a default logger instance
logger = logging.getLogger("trading_bot")
