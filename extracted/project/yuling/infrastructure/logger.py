"""结构化日志配置。"""

import logging
import sys

import structlog


def get_logger(name: str) -> structlog.BoundLogger:
    """获取结构化日志记录器。

    Args:
        name: 日志记录器名称。

    Returns:
        structlog.BoundLogger: 配置好的结构化日志记录器。
    """
    return structlog.get_logger(name)


def configure_logging(json_format: bool = True, log_level: str = "INFO") -> None:
    """配置结构化日志。

    Args:
        json_format: 是否使用JSON格式输出。
        log_level: 日志级别。
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ExtraAdder(),
    ]

    if json_format:
        formatter = structlog.dev.ConsoleRenderer(colors=False)
    else:
        formatter = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=formatter,
            foreign_pre_chain=shared_processors,
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
