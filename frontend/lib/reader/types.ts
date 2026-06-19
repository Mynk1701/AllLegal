// Types for the PDF reader. Mirrors the backend `CaseDetail` payload from
// GET /api/cases/{case_id} (see AllLegal/app/schemas/schemas.py).

/** One highlight rectangle, tagged with its 1-based PDF page. PDF-NATIVE
 *  (bottom-left origin) coordinates in PDF points — ready for PDF.js's
 *  viewport.convertToViewportPoint without further flipping. */
export type BboxRect = { page: number; rect: [number, number, number, number] };

/** A chunk's full highlight payload: a flat list of page-tagged rects.
 *  Multi-page chunks (16%) carry rects with differing `page` values. */
export type Bbox = BboxRect[];

export interface ReaderChunk {
  chunk_id: string;
  chunk_type?: string | null;
  chunk_text?: string | null;
  chunk_sequence?: number | null;
  score?: number | null;
  page_range?: [number, number] | null;
  bbox?: Bbox | null;
}

export interface CaseCitation {
  cited_canonical_key?: string | null;
  relationship?: string | null;
  chunk_id?: string | null;
  cited_case_id?: string | null; // set when the cited case is in our dataset (clickable)
  cited_case_name?: string | null;
  openable?: boolean; // true if actually uploaded (PDF loads); false = demo link
}

export interface CaseDetail {
  case_id: string;
  case_name: string;
  citation?: string | null;
  court?: string | null;
  case_type?: string | null;
  verdict: string[];
  year?: number | null;
  date_decided?: string | null;
  bench: string[];
  bench_strength?: number | null;
  acts_cited: string[];
  sections_cited: string[];
  pdf_url?: string | null;
  chunks: ReaderChunk[];
  cites: CaseCitation[];
}

/** A chunk's rects that fall on ONE page, used to draw highlights and to
 *  hit-test hover for that page. Built by grouping each chunk's bbox by page. */
export interface PageChunk {
  chunkId: string;
  chunkType?: string | null;
  rects: [number, number, number, number][];
}

/** What the hover bar needs: which chunk, and where the cursor is (viewport px). */
export interface HoverInfo {
  chunkId: string;
  chunkType?: string | null;
  x: number;
  y: number;
}
