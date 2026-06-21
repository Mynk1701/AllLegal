"""
Supabase service for database and authentication operations.
Handles all interactions with Supabase backend.
"""
from supabase import create_client, Client
from app.core.config import settings
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

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

    def log_search(
        self,
        search_id: str,
        query: str,
        results_count: int,
        search_time_ms: float,
        filters_applied: str,
        user_id: Optional[str],
    ) -> bool:
        """
        Log a search DEFINITION (query + filters) for the history feature and analytics.

        Args:
            search_id: Unique id for this search (uuid4 string)
            query: Search query string
            results_count: Number of distinct cases returned
            search_time_ms: Search execution time
            filters_applied: JSON-encoded filter dict
            user_id: User who performed the search (from JWT 'sub'), if any

        Returns:
            True if logged successfully
        """
        try:
            self.admin.table("search_logs").insert({
                "search_id": search_id,
                "query": query,
                "results_count": results_count,
                "search_time_ms": search_time_ms,
                "filters_applied": filters_applied,
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.info(f"✅ Search logged: '{query}' ({results_count} results)")
            return True
        except Exception as e:
            logger.error(f"❌ Error logging search: {str(e)}")
            return False

    def get_search_history(self, user_id: str, limit: int = 200) -> List[Dict]:
        """Most-recent search_logs rows for a user, newest first (raw — caller de-dupes)."""
        try:
            resp = (
                self.admin.table("search_logs")
                .select("query, filters_applied, created_at")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error(f"❌ get_search_history failed: {str(e)}")
            return []

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
