"""
Supabase service for database and authentication operations.
Handles all interactions with Supabase backend.
"""
from supabase import create_client, Client
from app.core.config import settings
import logging
from typing import Optional, Dict, Any, List
import jwt
from datetime import datetime

logger = logging.getLogger(__name__)

class SupabaseService:
    """
    Type-safe Supabase client wrapper.
    Manages database and authentication operations.
    """
    
    def __init__(self):
        """Initialize Supabase client"""
        try:
            self.client: Client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_ANON_KEY
            )
            logger.info("✅ Supabase client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase: {str(e)}")
            raise
    
    # ==================== Authentication ====================
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token from Supabase.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload or None if invalid
            
        Example:
            >>> payload = supabase_service.verify_token(token)
            >>> if payload:
            ...     user_id = payload['sub']  # User ID
        """
        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"]
            )
            logger.info(f"✅ Token verified for user: {payload.get('sub')}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("⏰ Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"❌ Invalid token: {str(e)}")
            return None
    
    def sign_up(self, email: str, password: str) -> Optional[Dict]:
        """
        Register a new user with Supabase.
        
        Args:
            email: User email
            password: User password (min 6 chars)
            
        Returns:
            User data or None if failed
        """
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password
            })
            logger.info(f"✅ User registered: {email}")
            return response.user.__dict__ if response.user else None
        except Exception as e:
            logger.error(f"❌ Sign up failed: {str(e)}")
            return None
    
    def sign_in(self, email: str, password: str) -> Optional[Dict]:
        """
        Sign in existing user.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Session data with access_token or None if failed
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            logger.info(f"✅ User signed in: {email}")
            return {
                "access_token": response.session.access_token,
                "user_id": response.user.id if response.user else None
            }
        except Exception as e:
            logger.error(f"❌ Sign in failed: {str(e)}")
            return None
    
    # ==================== Database Operations ====================
    
    def insert_case(self, case_data: Dict[str, Any]) -> Optional[Dict]:
        """
        Insert a legal case into database.
        
        Args:
            case_data: Case metadata dictionary
                {
                    "title": str,
                    "court": str,
                    "year": int,
                    "judge": str,
                    "summary": str,
                    "case_number": str
                }
        
        Returns:
            Inserted case data or None if failed
        """
        try:
            response = self.client.table("cases").insert(case_data).execute()
            logger.info(f"✅ Case inserted: {case_data.get('title')}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"❌ Error inserting case: {str(e)}")
            return None
    
    def get_case(self, case_id: str) -> Optional[Dict]:
        """
        Retrieve a case by ID.
        
        Args:
            case_id: Case UUID
            
        Returns:
            Case data or None if not found
        """
        try:
            response = self.client.table("cases").select("*").eq("id", case_id).execute()
            case = response.data[0] if response.data else None
            if case:
                logger.info(f"✅ Case retrieved: {case_id}")
            return case
        except Exception as e:
            logger.error(f"❌ Error retrieving case: {str(e)}")
            return None
    
    def search_cases(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search cases by title or summary.
        Note: Full-text search is in OpenSearch. This is basic DB search.
        
        Args:
            query: Search string
            limit: Max results
            
        Returns:
            List of matching cases
        """
        try:
            # Use full-text search if available, or filter by title
            response = self.client.table("cases").select("*").ilike(
                "title",
                f"%{query}%"
            ).limit(limit).execute()
            logger.info(f"✅ Found {len(response.data)} cases matching '{query}'")
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"❌ Error searching cases: {str(e)}")
            return []
    
    def log_search(self, user_id: str, query: str, results_count: int, search_time_ms: float) -> bool:
        """
        Log a search query for analytics.
        
        Args:
            user_id: User who performed search
            query: Search query string
            results_count: Number of results returned
            search_time_ms: Search execution time
            
        Returns:
            True if logged successfully
        """
        try:
            self.client.table("search_logs").insert({
                "user_id": user_id,
                "query": query,
                "results_count": results_count,
                "search_time_ms": search_time_ms,
                "timestamp": datetime.utcnow().isoformat()
            }).execute()
            logger.info(f"✅ Search logged: '{query}' ({results_count} results)")
            return True
        except Exception as e:
            logger.error(f"❌ Error logging search: {str(e)}")
            return False

# Global Supabase service instance
supabase_service = SupabaseService()
