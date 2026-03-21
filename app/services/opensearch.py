"""
OpenSearch service for fast boolean search on legal cases.
Handles indexing and searching of case data.
"""
from opensearchpy import OpenSearch, exceptions
from typing import List, Dict, Optional, Tuple
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)

class OpenSearchService:
    """
    Type-safe OpenSearch service.
    Handles all full-text and boolean searching.
    """
    
    def __init__(self):
        """Initialize OpenSearch client"""
        try:
            self.client = OpenSearch(
                hosts=[{
                    "host": settings.OPENSEARCH_HOST,
                    "port": settings.OPENSEARCH_PORT,
                    "scheme": settings.OPENSEARCH_SCHEME
                }],
                timeout=settings.OPENSEARCH_TIMEOUT,
                verify_certs=False  # For development
            )
            self.index_name = settings.OPENSEARCH_INDEX
            logger.info("✅ OpenSearch client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenSearch: {str(e)}")
            raise
    
    def health_check(self) -> bool:
        """
        Check if OpenSearch cluster is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            info = self.client.info()
            version = info.get('version', {}).get('number', 'unknown')
            logger.info(f"✅ OpenSearch health check passed: v{version}")
            return True
        except Exception as e:
            logger.error(f"❌ OpenSearch health check failed: {str(e)}")
            return False
    
    def create_index(self) -> bool:
        """
        Create OpenSearch index with proper mappings for legal cases.
        
        Returns:
            True if successful or already exists
        """
        try:
            if self.client.indices.exists(index=self.index_name):
                logger.info(f"ℹ️  Index '{self.index_name}' already exists")
                return True
            
            body = {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "analysis": {
                        "analyzer": {
                            "case_analyzer": {
                                "type": "standard",
                                "stopwords": "_english_"
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "case_id": {"type": "keyword"},
                        "title": {
                            "type": "text",
                            "analyzer": "case_analyzer",
                            "fields": {"keyword": {"type": "keyword"}}
                        },
                        "court": {"type": "text"},
                        "year": {"type": "integer"},
                        "judge": {"type": "text"},
                        "summary": {
                            "type": "text",
                            "analyzer": "case_analyzer"
                        },
                        "case_number": {"type": "keyword"},
                        "created_at": {"type": "date"}
                    }
                }
            }
            
            self.client.indices.create(index=self.index_name, body=body)
            logger.info(f"✅ Index '{self.index_name}' created successfully")
            return True
        except exceptions.RequestError as e:
            if e.error == "resource_already_exists_exception":
                logger.info(f"ℹ️  Index '{self.index_name}' already exists")
                return True
            logger.error(f"❌ Error creating index: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {str(e)}")
            return False
    
    def index_case(self, case_id: str, case_data: Dict) -> bool:
        """
        Index a legal case in OpenSearch.
        
        Args:
            case_id: Unique case identifier
            case_data: Case metadata dictionary
            
        Returns:
            True if successful
        """
        try:
            response = self.client.index(
                index=self.index_name,
                id=case_id,
                body=case_data
            )
            logger.info(f"✅ Case indexed: {case_id} ({response['result']})")
            return True
        except Exception as e:
            logger.error(f"❌ Error indexing case {case_id}: {str(e)}")
            return False
    
    def search(self, query: str, limit: int = 10) -> Tuple[List[Dict], float]:
        """
        Search legal cases using boolean query.
        
        Args:
            query: Search query string
            limit: Maximum results to return
            
        Returns:
            Tuple of (results list, search_time_ms)
            
        Example:
            >>> results, search_time = opensearch_service.search("constitutional rights")
            >>> print(f"Found {len(results)} cases in {search_time}ms")
        """
        start_time = time.time()
        
        try:
            # Multi-field search with fuzzy matching for typos
            body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^3", "summary^2", "judge", "court"],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                },
                "size": limit,
                "_source": [
                    "case_id", "title", "court", "year", 
                    "judge", "summary", "case_number"
                ]
            }
            
            response = self.client.search(index=self.index_name, body=body)
            search_time_ms = (time.time() - start_time) * 1000
            
            # Extract results with relevance scores
            hits = response.get("hits", {}).get("hits", [])
            results = [
                {
                    **hit["_source"],
                    "relevance_score": hit["_score"]
                }
                for hit in hits
            ]
            
            logger.info(f"✅ Search returned {len(results)} results in {search_time_ms:.2f}ms")
            return results, search_time_ms
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ Error searching: {str(e)}")
            return [], search_time_ms

# Global OpenSearch service instance
opensearch_service = OpenSearchService()
