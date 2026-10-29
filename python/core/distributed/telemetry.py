from __future__ import annotations

import json
from contextlib import asynccontextmanager
from secrets import token_hex
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "request.body",
    "response.body",
    "reasoning_content",
}


def _redact(value: Any, key: str | None = None) -> Any:
    if key is not None and key.lower() in SENSITIVE_KEYS:
        return "[redacted]"
    if isinstance(value, dict):
        return {
            item_key: _redact(item, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def public_attributes(value: dict[str, Any]) -> dict[str, Any]:
    return _redact(value)


def _otel_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in attributes.items():
        if isinstance(value, (str, bool, int, float)):
            values[key] = value
        else:
            values[key] = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )
    return values


class DurableTracer:
    def __init__(self, repository, otel_tracer=None) -> None:
        self.repository = repository
        self.otel_tracer = otel_tracer

    @asynccontextmanager
    async def span(
        self,
        run_id: str,
        trace_id: str,
        name: str,
        *,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ):
        safe_attributes = public_attributes(attributes or {})
        span = await self.repository.start_span(
            run_id,
            trace_id,
            token_hex(8),
            parent_span_id,
            name,
            safe_attributes,
        )
        otel_context = None
        if self.otel_tracer is not None:
            try:
                otel_context = self.otel_tracer.start_as_current_span(
                    name,
                    attributes=_otel_attributes(safe_attributes),
                )
                otel_context.__enter__()
            except Exception:
                otel_context = None
        try:
            yield span
        except BaseException as exc:
            await self.repository.finish_span(
                span.span_id,
                "error",
                {"error.type": type(exc).__name__},
            )
            if otel_context is not None:
                try:
                    otel_context.__exit__(
                        type(exc),
                        exc,
                        exc.__traceback__,
                    )
                except Exception:
                    pass
            raise
        else:
            await self.repository.finish_span(span.span_id, "ok", {})
            if otel_context is not None:
                try:
                    otel_context.__exit__(None, None, None)
                except Exception:
                    pass


def build_optional_otel_tracer(endpoint: str):
    if not endpoint:
        return None, None

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        return provider.get_tracer("eduagent.distributed"), provider
    except Exception:
        return None, None
