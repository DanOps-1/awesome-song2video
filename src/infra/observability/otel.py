"""OpenTelemetry 与结构化日志初始化。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import structlog

from src.infra.config.settings import get_settings


def configure_tracing(service_name: str = "lyrics-video-sync") -> None:
    settings = get_settings()
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def configure_logging() -> None:
    """配置结构化日志，支持同时输出到控制台和文件。

    日志输出:
    - 控制台: 彩色格式化输出（便于人类阅读）
    - 文件: JSON 格式（便于程序分析）

    注意：此函数可以被多次调用（例如在不同模块导入时），但会自动处理重复配置。
    """
    # 创建 logs 目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 配置文件 handler
    from logging.handlers import RotatingFileHandler

    # 主日志文件（JSON 格式）
    json_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    json_handler.setLevel(logging.INFO)

    # 错误日志文件（单独记录 WARNING 及以上）
    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)

    # 配置 structlog
    # 判断是否在终端运行（控制台彩色输出 vs 文件 JSON 输出）
    is_tty = sys.stdout.isatty()

    # 共享的 processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # 控制台 renderer（彩色 vs JSON）
    console_renderer: Any
    if is_tty:
        # 终端环境：使用彩色输出
        console_renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # 非终端环境：使用 JSON
        console_renderer = structlog.processors.JSONRenderer(ensure_ascii=False)

    structlog.configure(
        processors=shared_processors  # type: ignore[arg-type]
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置 stdlib logging
    formatter = structlog.stdlib.ProcessorFormatter(
        # 文件使用 JSON，控制台使用配置的 renderer
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            console_renderer,
        ],
    )

    # 设置文件 handler 的 formatter
    json_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)

    # 配置 root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除已有的 handlers
    root_logger.handlers.clear()

    # 添加控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 添加文件 handlers
    root_logger.addHandler(json_handler)
    root_logger.addHandler(error_handler)

    # 记录启动日志
    logger = structlog.get_logger(__name__)
    logger.info(
        "logging_configured",
        log_dir=str(log_dir.absolute()),
        json_log="app.log",
        error_log="error.log",
        console_mode="color" if is_tty else "json",
    )
