"""
In-memory case index: case_id -> case_name for the FULL processed corpus
(~26k judgments), generated from the pipeline's case_identity_table.json into
app/data/case_index.json.

Supabase `cases` only holds the subset actually uploaded (with PDFs). This index
lets the reader mark a cited precedent as *known in the dataset* (clickable to
demo the resolution) even before it's uploaded — distinct from *openable* (a real
Supabase row + PDF). Missing/corrupt index simply disables demo-clickability.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "case_index.json"
_index: Dict[str, str] = {}

try:
    with open(_INDEX_PATH, encoding="utf-8") as f:
        _index = json.load(f)
    logger.info(f"✅ case_index loaded: {len(_index)} cases")
except Exception as e:
    logger.warning(f"⚠️ case_index not loaded ({_INDEX_PATH}): {e}")


def known(case_id: str) -> bool:
    """Is this case_id anywhere in the full processed corpus?"""
    return case_id in _index


def name_of(case_id: str) -> Optional[str]:
    return _index.get(case_id)
