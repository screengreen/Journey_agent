import json
from typing import List, Optional
from pathlib import Path
from src.models.event import Event
from src.vdb.config import WEAVIATE_URL, COLLECTION_NAME

try:
    import weaviate
except ImportError:
    weaviate = None
    
from urllib.parse import urlparse


def get_weaviate_client() -> weaviate.WeaviateClient:
    """Создает клиент Weaviate."""
    parsed = urlparse(WEAVIATE_URL)
    http_port = parsed.port or (443 if parsed.scheme == "https" else 8080)
    http_secure = parsed.scheme == "https"
    hostname = parsed.hostname or "localhost"

    if hostname in ("localhost", "127.0.0.1") and http_port == 8080 and not http_secure:
        return weaviate.connect_to_local()
    else:
        return weaviate.connect_to_custom(
            http_host=hostname,
            http_port=http_port,
            http_secure=http_secure,
            grpc_host=hostname,
            grpc_port=50051,
            grpc_secure=http_secure,
        )