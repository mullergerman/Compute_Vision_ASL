"""Utilities for emitting metrics to Telegraf.

This module defines a :class:`TelegrafClient` that batches metrics and
periodically ships them to a Telegraf HTTP listener. Metrics are enqueued via
:func:`record_metric` so that the request thread is never blocked on network
I/O.

The Telegraf host, authentication token and flush interval are read from the
``TELEGRAF_HOST``, ``TELEGRAF_TOKEN`` and ``TELEGRAF_FLUSH_INTERVAL``
environment variables respectively. The client posts metrics to
``http://<TELEGRAF_HOST>:8088/ingest``.

Metrics are formatted using the InfluxDB line protocol by default. Setting the
``TELEGRAF_FORMAT`` environment variable to ``"json"`` switches the payload to
JSON.
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import threading
import time
from typing import Dict, Iterable, Optional, Tuple

import requests


Metric = Tuple[str, Dict[str, str], Dict[str, object], Optional[int]]


class TelegrafClient:
    """Client responsible for batching and shipping metrics to Telegraf.

    Parameters are read from the environment when not provided explicitly:

    - ``TELEGRAF_HOST``: Hostname of the Telegraf agent (default ``localhost``)
    - ``TELEGRAF_TOKEN``: Optional authentication token
    - ``TELEGRAF_FLUSH_INTERVAL``: Interval in seconds between flushes (default
      ``5``)
    - ``TELEGRAF_FORMAT``: ``"line"`` for Influx line protocol (default) or
      ``"json"`` for JSON payloads
    """

    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        flush_interval: Optional[float] = None,
        payload_format: Optional[str] = None,
    ) -> None:
        self.host = host or os.getenv("TELEGRAF_HOST", "localhost")
        self.token = token or os.getenv("TELEGRAF_TOKEN")
        self.flush_interval = float(
            flush_interval or os.getenv("TELEGRAF_FLUSH_INTERVAL", "5")
        )
        self.payload_format = (
            (payload_format or os.getenv("TELEGRAF_FORMAT", "line"))
            .strip()
            .lower()
        )

        self.url = f"http://{self.host}:8088/ingest"
        self._session = requests.Session()
        self._queue: "queue.Queue[Metric]" = queue.Queue()
        self._stop = threading.Event()

        # Start the background flushing thread.
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def record_metric(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None,
        fields: Optional[Dict[str, object]] = None,
        ts: Optional[int] = None,
    ) -> None:
        """Enqueue a metric for later flushing.

        ``fields`` must contain at least one key/value pair; otherwise the
        metric is ignored as it would be invalid Influx data.
        """

        if not fields:
            return
        metric: Metric = (name, tags or {}, fields, ts)
        self._queue.put(metric)

    def flush(self) -> None:
        """Flush queued metrics to Telegraf immediately."""
        metrics = self._drain_queue()
        if not metrics:
            return

        try:
            if self.payload_format == "json":
                data = self._metrics_to_json(metrics)
                headers = {"Content-Type": "application/json"}
            else:
                data = self._metrics_to_line(metrics)
                headers = {"Content-Type": "text/plain"}

            if self.token:
                headers["Authorization"] = f"Token {self.token}"

            for attempt in range(3):
                try:
                    self._session.post(
                        self.url, data=data, headers=headers, timeout=5
                    )
                    break
                except requests.RequestException:
                    if attempt == 2:
                        break
                    time.sleep(2 ** attempt)
        except Exception:
            # Metrics are best-effort only; drop on failure
            pass

    def close(self) -> None:
        """Stop the background thread and flush remaining metrics."""
        self._stop.set()
        self._thread.join(timeout=self.flush_interval)
        try:
            self.flush()
        finally:
            # Drain any leftover metrics to avoid growth on subsequent calls
            self._drain_queue()
            self._session.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _flush_loop(self) -> None:
        while not self._stop.wait(self.flush_interval):
            try:
                self.flush()
            except Exception:
                pass

    def _drain_queue(self) -> Iterable[Metric]:
        metrics = []
        while True:
            try:
                metrics.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return metrics

    # -- Formatting -----------------------------------------------------
    @staticmethod
    def _escape(value: str) -> str:
        return (
            str(value)
            .replace(" ", "\\ ")
            .replace(",", "\\,")
            .replace("=", "\\=")
        )

    def _metric_to_dict(self, metric: Metric) -> Dict[str, object]:
        name, tags, fields, ts = metric
        payload = {"measurement": name, "tags": tags, "fields": fields}
        if ts is not None:
            payload["timestamp"] = ts
        return payload

    def _metrics_to_json(self, metrics: Iterable[Metric]) -> bytes:
        payload = [self._metric_to_dict(m) for m in metrics]
        return json.dumps(payload).encode("utf-8")

    def _to_line_protocol(self, metric: Metric) -> str:
        name, tags, fields, ts = metric
        tag_str = ",".join(
            f"{self._escape(k)}={self._escape(v)}" for k, v in tags.items()
        )
        field_parts = []
        for k, v in fields.items():
            key = self._escape(k)
            if isinstance(v, str):
                field_parts.append(f'{key}="{v}"')
            elif isinstance(v, bool):
                field_parts.append(f"{key}={str(v).lower()}")
            else:
                field_parts.append(f"{key}={v}")
        field_str = ",".join(field_parts)
        measurement = self._escape(name)
        if tag_str:
            measurement = f"{measurement},{tag_str}"
        line = f"{measurement} {field_str}"
        if ts is not None:
            line = f"{line} {int(ts)}"
        return line

    def _metrics_to_line(self, metrics: Iterable[Metric]) -> bytes:
        lines = [self._to_line_protocol(m) for m in metrics]
        return "\n".join(lines).encode("utf-8")


# ----------------------------------------------------------------------
# Module-level helper
# ----------------------------------------------------------------------
_client = TelegrafClient()
atexit.register(_client.close)



def record_metric(
    name: str,
    tags: Optional[Dict[str, str]] = None,
    fields: Optional[Dict[str, object]] = None,
    ts: Optional[int] = None,
) -> None:
    """Record a single metric using the module-level :class:`TelegrafClient`."""

    _client.record_metric(name, tags, fields, ts)
