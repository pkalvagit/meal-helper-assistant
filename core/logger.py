"""
Logging configuration for meal-helper-assistant.
Logs to both console and file with readable timestamps.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "meal-helper", log_dir: str = "logs") -> logging.Logger:
    """
    Setup logger with console and file handlers.

    Args:
        name: Logger name
        log_dir: Directory to store log files

    Returns:
        Configured logger
    """
    # Create logs directory
    log_path = Path(__file__).parent.parent / log_dir
    log_path.mkdir(exist_ok=True)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s | %(message)s',
        datefmt='%H:%M:%S'
    )

    # Console handler (INFO and above, simple format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # File handler (DEBUG and above, detailed format)
    # Create a new log file for each day
    log_file = log_path / f"chat_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    return logger


def log_chat_start(logger: logging.Logger, user_profile: str):
    """Log the start of a chat session."""
    logger.info("=" * 80)
    logger.info(f"NEW CHAT SESSION - Profile: {user_profile}")
    logger.info("=" * 80)


def log_user_message(logger: logging.Logger, message: str):
    """Log user message."""
    logger.info(f"USER: {message}")


def log_agent_response(logger: logging.Logger, response: str):
    """Log agent response."""
    logger.info(f"AGENT: {response[:200]}{'...' if len(response) > 200 else ''}")


def log_tool_call(logger: logging.Logger, tool_name: str, args: dict):
    """Log tool call."""
    logger.debug(f"TOOL CALL: {tool_name}")
    logger.debug(f"  Args: {args}")


def log_tool_result(logger: logging.Logger, tool_name: str, success: bool, result_summary: str = ""):
    """Log tool result."""
    status = "SUCCESS" if success else "FAILED"
    logger.debug(f"TOOL RESULT: {tool_name} - {status}")
    if result_summary:
        logger.debug(f"  Summary: {result_summary}")


def log_error(logger: logging.Logger, error: Exception, context: str = ""):
    """Log error with context."""
    logger.error(f"ERROR: {context}")
    logger.error(f"  Type: {type(error).__name__}")
    logger.error(f"  Message: {str(error)}")
    logger.exception(error)


def log_pipeline_step(logger: logging.Logger, step: str, status: str, details: str = ""):
    """Log pipeline step (menu extraction, etc)."""
    logger.info(f"[Pipeline] {step}: {status}")
    if details:
        logger.debug(f"  Details: {details}")
