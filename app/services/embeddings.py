"""
Query embeddings via Voyage AI.

MUST match the index-time model: stage_04_embed.py embedded chunks with
`voyage-law-2` + input_type="document". voyage-law-2 is an *asymmetric* encoder,
so queries use the counterpart input_type="query".

A small in-process LRU caches query vectors by text, so filter-only edits of a
saved search (same query string) reuse the vector with no Voyage call.
(Production: swap for Redis — see REDIS_URL in config — to share across workers.)
"""
import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self._client = None  # lazy: only constructed on first real query

    @property
    def client(self):
        if self._client is None:
            import voyageai  # lazy import so the app boots without the dep present
            self._client = voyageai.Client(api_key=settings.VOYAGE_API_KEY or None)
        return self._client

    @lru_cache(maxsize=512)
    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (input_type='query'). Cached by exact text."""
        result = self.client.embed(
            [text], model=settings.VOYAGE_MODEL, input_type="query"
        )
        return result.embeddings[0]


embedding_service = EmbeddingService()
