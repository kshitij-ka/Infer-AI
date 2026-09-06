from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_LATENCY = Histogram(
    "chat_request_latency_ms",
    "Latency of /chat requests in milliseconds",
)
TOKEN_USAGE = Counter(
    "chat_token_usage_total",
    "Total LLM tokens consumed by /chat requests",
    ["type"],
)
CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total /chat requests by outcome status",
    ["status"],
)


def record_chat_metrics(
    latency_ms: float, prompt_tokens: int, completion_tokens: int, status: str
) -> None:
    REQUEST_LATENCY.observe(latency_ms)
    TOKEN_USAGE.labels(type="prompt").inc(prompt_tokens)
    TOKEN_USAGE.labels(type="completion").inc(completion_tokens)
    CHAT_REQUESTS.labels(status=status).inc()


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
