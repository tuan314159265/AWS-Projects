"""Custom CloudWatch metrics for NewsRAG monitoring."""
import time
import threading
from typing import Dict
import boto3
from utils.logger import get_logger
from utils.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

_client = None
_metrics_queue: Dict[str, float] = {}
_queue_lock = threading.Lock()
_flush_interval = 30  # seconds


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("cloudwatch", region_name="ap-southeast-2")
    return _client


def put_search_metric(duration_ms: float, query_length: int, hit_count: int):
    """Queue a search metric for batch submission."""
    ts = int(time.time())
    with _queue_lock:
        _metrics_queue.setdefault("SearchDuration", []).append({
            "MetricName": "SearchDuration",
            "Value": duration_ms,
            "Unit": "Milliseconds",
            "Timestamp": ts,
            "Dimensions": [{"Name": "Service", "Value": "NewsRAG"}]
        })
        _metrics_queue.setdefault("SearchQueryLength", []).append({
            "MetricName": "SearchQueryLength",
            "Value": query_length,
            "Unit": "Count",
            "Timestamp": ts,
            "Dimensions": [{"Name": "Service", "Value": "NewsRAG"}]
        })
        _metrics_queue.setdefault("SearchHitCount", []).append({
            "MetricName": "SearchHitCount",
            "Value": hit_count,
            "Unit": "Count",
            "Timestamp": ts,
            "Dimensions": [{"Name": "Service", "Value": "NewsRAG"}]
        })


def _flush_metrics():
    """Send queued metrics to CloudWatch."""
    global _metrics_queue
    with _queue_lock:
        queue = _metrics_queue
        _metrics_queue = {}

    if not queue:
        return

    try:
        client = _get_client()
        metric_data = []
        for values in queue.values():
            metric_data.extend(values)
            if len(metric_data) >= 20:
                client.put_metric_data(Namespace="NewsRAG", MetricData=metric_data)
                metric_data = []

        if metric_data:
            client.put_metric_data(Namespace="NewsRAG", MetricData=metric_data)

        logger.debug(f"Flushed {sum(len(v) for v in queue.values())} metrics to CloudWatch")
    except Exception as e:
        logger.error(f"Failed to flush metrics: {e}")


def start_metrics_flusher():
    """Start background thread that flushes metrics periodically."""
    def _loop():
        while True:
            time.sleep(_flush_interval)
            _flush_metrics()

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    logger.info("CloudWatch metrics flusher started")
