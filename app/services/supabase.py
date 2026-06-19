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
        """Initialize Supabase clients (anon for auth, service-role for data + storage)."""
        try:
            self.client: Client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_ANON_KEY
            )
            # Service-role client: reads `cases`/`chunk_bboxes` and mints signed PDF
            # URLs, bypassing RLS. Falls back to anon if the key isn't set.
            self.admin: Client = (
                create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
                if settings.SUPABASE_SERVICE_ROLE_KEY
                else self.client
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
        Note: Full-text search is in Meilisearch. This is basic DB search.
        
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
    
    # ==================== Search Enrichment (OpenSearch -> Supabase) ====================

    def get_cases_by_ids(self, case_ids: List[str]) -> Dict[str, Dict]:
        """Batch-fetch case rows. Returns {case_id: row}."""
        if not case_ids:
            return {}
        try:
            resp = self.admin.table("cases").select("*").in_("case_id", case_ids).execute()
            return {r["case_id"]: r for r in (resp.data or [])}
        except Exception as e:
            logger.error(f"❌ get_cases_by_ids failed: {str(e)}")
            return {}

    def get_chunk_bboxes_by_ids(self, chunk_ids: List[str]) -> Dict[str, Dict]:
        """Batch-fetch {chunk_id: {page_range, bbox}} for PDF highlighting."""
        if not chunk_ids:
            return {}
        try:
            resp = self.admin.table("chunk_bboxes").select("*").in_("chunk_id", chunk_ids).execute()
            return {r["chunk_id"]: r for r in (resp.data or [])}
        except Exception as e:
            logger.error(f"❌ get_chunk_bboxes_by_ids failed: {str(e)}")
            return {}

    def get_case_by_id(self, case_id: str) -> Optional[Dict]:
        """Fetch a single case row by case_id (PK)."""
        try:
            resp = self.admin.table("cases").select("*").eq("case_id", case_id).execute()
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error(f"❌ get_case_by_id failed: {str(e)}")
            return None

    def get_citations(self, case_id: str) -> List[Dict]:
        """Outbound citation edges for a case (citation_graph)."""
        try:
            resp = (
                self.admin.table("citation_graph")
                .select("cited_canonical_key, relationship, chunk_id")
                .eq("citing_case_id", case_id)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error(f"❌ get_citations failed: {str(e)}")
            return []

    def get_pdf_signed_url(self, case_id: str, expiry: Optional[int] = None) -> Optional[str]:
        """Signed URL for case_pdfs/<case_id>.pdf (Option 1 — name-by-case_id)."""
        path = settings.PDF_PATH_TEMPLATE.format(case_id=case_id)
        try:
            resp = self.admin.storage.from_(settings.PDF_BUCKET).create_signed_url(
                path, expiry or settings.PDF_SIGNED_URL_EXPIRY
            )
            return resp.get("signedURL") or resp.get("signedUrl")
        except Exception as e:
            logger.warning(f"⚠️ signed URL failed for {case_id}: {str(e)}")
            return None

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

    # ==================== Groups & Annotations (PDF reader) ====================
    # The service-role client bypasses RLS, so EVERY method here is scoped by the
    # caller's user_id (groups/annotations) or by a parent group the caller owns
    # (items/annotations). Routes verify group ownership before touching children.

    def create_group(self, user_id: str, name: str) -> Optional[Dict]:
        try:
            resp = self.admin.table("groups").insert(
                {"user_id": user_id, "name": name}
            ).execute()
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error(f"❌ create_group failed: {str(e)}")
            return None

    def list_groups(self, user_id: str, case_id: Optional[str] = None) -> List[Dict]:
        """User's groups, newest first, with item_count. When case_id is given,
        also flags `has_case` for groups that already contain that case."""
        try:
            resp = (
                self.admin.table("groups").select("*")
                .eq("user_id", user_id).order("created_at", desc=True).execute()
            )
            groups = resp.data or []
            if not groups:
                return []
            ids = [g["id"] for g in groups]
            items = self.admin.table("group_items").select("group_id").in_("group_id", ids).execute()
            counts: Dict[str, int] = {}
            for it in (items.data or []):
                counts[it["group_id"]] = counts.get(it["group_id"], 0) + 1
            members: set = set()
            if case_id:
                m = (
                    self.admin.table("group_items").select("group_id")
                    .in_("group_id", ids).eq("case_id", case_id).execute()
                )
                members = {r["group_id"] for r in (m.data or [])}
            for g in groups:
                g["item_count"] = counts.get(g["id"], 0)
                g["has_case"] = g["id"] in members
            return groups
        except Exception as e:
            logger.error(f"❌ list_groups failed: {str(e)}")
            return []

    def get_group(self, user_id: str, group_id: str) -> Optional[Dict]:
        """Fetch a group only if owned by user_id (ownership gate)."""
        try:
            resp = (
                self.admin.table("groups").select("*")
                .eq("id", group_id).eq("user_id", user_id).execute()
            )
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error(f"❌ get_group failed: {str(e)}")
            return None

    def update_group(self, user_id: str, group_id: str, name: str) -> Optional[Dict]:
        try:
            resp = (
                self.admin.table("groups")
                .update({"name": name, "updated_at": datetime.utcnow().isoformat()})
                .eq("id", group_id).eq("user_id", user_id).execute()
            )
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error(f"❌ update_group failed: {str(e)}")
            return None

    def delete_group(self, user_id: str, group_id: str) -> bool:
        """Delete a group; items + annotations cascade via FK."""
        try:
            resp = (
                self.admin.table("groups").delete()
                .eq("id", group_id).eq("user_id", user_id).execute()
            )
            return bool(resp.data)
        except Exception as e:
            logger.error(f"❌ delete_group failed: {str(e)}")
            return False

    def list_group_items(self, group_id: str) -> List[Dict]:
        try:
            resp = (
                self.admin.table("group_items").select("*")
                .eq("group_id", group_id).order("created_at", desc=True).execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error(f"❌ list_group_items failed: {str(e)}")
            return []

    def add_group_item(self, group_id: str, case_id: str) -> Optional[Dict]:
        """Idempotent: returns the existing row if the case is already in the group."""
        try:
            existing = (
                self.admin.table("group_items").select("*")
                .eq("group_id", group_id).eq("case_id", case_id).execute()
            )
            if existing.data:
                return existing.data[0]
            resp = self.admin.table("group_items").insert(
                {"group_id": group_id, "case_id": case_id}
            ).execute()
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error(f"❌ add_group_item failed: {str(e)}")
            return None

    def remove_group_item(self, group_id: str, case_id: str) -> bool:
        try:
            resp = (
                self.admin.table("group_items").delete()
                .eq("group_id", group_id).eq("case_id", case_id).execute()
            )
            return bool(resp.data)
        except Exception as e:
            logger.error(f"❌ remove_group_item failed: {str(e)}")
            return False

    def list_annotations(self, group_id: str, case_id: str) -> List[Dict]:
        try:
            resp = (
                self.admin.table("annotations").select("*")
                .eq("group_id", group_id).eq("case_id", case_id)
                .order("created_at", desc=False).execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error(f"❌ list_annotations failed: {str(e)}")
            return []

    def create_annotation(self, user_id: str, group_id: str, payload: Dict[str, Any]) -> Optional[Dict]:
        """payload: {case_id, type, rects:[{page,rect}], color?, comment?}."""
        try:
            row = {"user_id": user_id, "group_id": group_id, **payload}
            resp = self.admin.table("annotations").insert(row).execute()
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error(f"❌ create_annotation failed: {str(e)}")
            return None

    def update_annotation(
        self, user_id: str, group_id: str, annotation_id: str, fields: Dict[str, Any]
    ) -> Optional[Dict]:
        try:
            fields = {**fields, "updated_at": datetime.utcnow().isoformat()}
            resp = (
                self.admin.table("annotations").update(fields)
                .eq("id", annotation_id).eq("group_id", group_id).eq("user_id", user_id)
                .execute()
            )
            return resp.data[0] if resp.data else None
        except Exception as e:
            logger.error(f"❌ update_annotation failed: {str(e)}")
            return None

    def delete_annotation(self, user_id: str, group_id: str, annotation_id: str) -> bool:
        try:
            resp = (
                self.admin.table("annotations").delete()
                .eq("id", annotation_id).eq("group_id", group_id).eq("user_id", user_id)
                .execute()
            )
            return bool(resp.data)
        except Exception as e:
            logger.error(f"❌ delete_annotation failed: {str(e)}")
            return False


# Global Supabase service instance
supabase_service = SupabaseService()
