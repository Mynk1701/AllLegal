import meilisearch
from typing import List, Dict, Optional, Tuple
from app.core.config import settings
import logging
import time

logger = logging.getLogger(__name__)

class MeilisearchService:
    """
    Type-safe Meilisearch service for indexing and searching cases.
    Meilisearch is simpler and faster than OpenSearch for this use case.
    """
    
    def __init__(self):
        """Initialize Meilisearch client"""
        try:
            self.client = meilisearch.Client(
                f"http://{settings.MEILISEARCH_HOST}:{settings.MEILISEARCH_PORT}",
                api_key=settings.MEILISEARCH_MASTER_KEY
            )
            self.index_name = settings.MEILISEARCH_INDEX
            logger.info("✅ Meilisearch client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Meilisearch: {str(e)}")
            raise
    
    def health_check(self) -> bool:
        """
        Check if Meilisearch is available and healthy
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            health = self.client.health()
            logger.info(f"✅ Meilisearch health check passed: {health}")
            return True
        except Exception as e:
            logger.error(f"❌ Meilisearch health check failed: {str(e)}")
            return False
    
    def create_index(self) -> bool:
        """
        Create Meilisearch index with settings for legal cases
        
        Returns:
            True if successful or index already exists
        """
        try:
            # Check if index exists
            try:
                self.client.get_index(self.index_name)
                logger.info(f"✅ Index '{self.index_name}' already exists")
                return True
            except meilisearch.errors.MeilisearchApiError:
                # Index doesn't exist, create it
                pass
            
            # Create index with settings
            index = self.client.create_index(
                uid=self.index_name,
                options={
                    "primaryKey": "case_id"
                }
            )
            
            # Configure searchable attributes
            index.update_searchable_attributes([
                "title",
                "summary",
                "judge",
                "court",
                "case_number"
            ])
            
            # Configure filterable attributes
            index.update_filterable_attributes([
                "year",
                "court",
                "judge"
            ])
            
            # Configure sortable attributes
            index.update_sortable_attributes([
                "year",
                "relevance_score"
            ])
            
            logger.info(f"✅ Index '{self.index_name}' created successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating index: {str(e)}")
            return False
    
    def index_case(self, case_id: str, case_data: Dict) -> bool:
        """
        Index a case in Meilisearch
        
        Args:
            case_id: Unique case identifier
            case_data: Case metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            index = self.client.index(self.index_name)
            case_data['case_id'] = case_id  # Ensure case_id is included
            response = index.add_documents([case_data])
            logger.info(f"✅ Indexed case {case_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error indexing case {case_id}: {str(e)}")
            return False
    
    def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Dict], float]:
        """
        Search cases using Meilisearch
        
        Features:
        - Typo tolerance (automatically enabled)
        - Fuzzy matching
        - Ranking by relevance
        - Fast sub-100ms search
        
        Args:
            query: Search query string
            limit: Maximum results to return
            offset: Pagination offset
            
        Returns:
            Tuple of (results list, search_time_ms)
        """
        start_time = time.time()
        
        try:
            index = self.client.index(self.index_name)
            
            # Search with Meilisearch options
            results = index.search(
                q=query,
                opt_params={
                    "limit": limit,
                    "offset": offset,
                    "matchingStrategy": "all"  # Match all words
                }
            )
            
            search_time_ms = (time.time() - start_time) * 1000
            
            # Extract hits
            hits = results.get("hits", [])
            logger.info(
                f"✅ Search for '{query}' returned {len(hits)} results "
                f"in {search_time_ms:.2f}ms"
            )
            
            return hits, search_time_ms
            
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ Error searching: {str(e)}")
            return [], search_time_ms
    
    def advanced_search(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: int = 10
    ) -> Tuple[List[Dict], float]:
        """
        Advanced search with filters
        
        Args:
            query: Search query string
            filters: Filter conditions (e.g., {"year": 2015})
            limit: Maximum results
            
        Returns:
            Tuple of (results list, search_time_ms)
        """
        start_time = time.time()
        
        try:
            index = self.client.index(self.index_name)
            
            # Build filter string if provided
            filter_str = None
            if filters:
                filter_parts = []
                for key, value in filters.items():
                    if isinstance(value, str):
                        filter_parts.append(f'{key} = "{value}"')
                    else:
                        filter_parts.append(f'{key} = {value}')
                filter_str = " AND ".join(filter_parts)
            
            # Search with filters
            results = index.search(
                q=query,
                opt_params={
                    "limit": limit,
                    "filter": filter_str
                }
            )
            
            search_time_ms = (time.time() - start_time) * 1000
            hits = results.get("hits", [])
            
            logger.info(
                f"✅ Advanced search for '{query}' with filters returned "
                f"{len(hits)} results in {search_time_ms:.2f}ms"
            )
            
            return hits, search_time_ms
            
        except Exception as e:
            search_time_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ Error in advanced search: {str(e)}")
            return [], search_time_ms
    
    def delete_index(self) -> bool:
        """
        Delete the index (useful for testing)
        
        Returns:
            True if successful
        """
        try:
            self.client.delete_index(self.index_name)
            logger.info(f"✅ Index '{self.index_name}' deleted successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting index: {str(e)}")
            return False

# Global service instance
meilisearch_service = MeilisearchService()