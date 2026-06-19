// Types for groups + group-scoped annotations. Mirrors the backend schemas in
// AllLegal/app/schemas/schemas.py (Group / GroupItem / Annotation, Option B:
// one row per gesture, `rects` carrying every PDF-native rectangle it covers).

export type AnnotationType = 'highlight' | 'underline' | 'note';

/** One PDF-native rectangle on one page (bottom-left origin) — same convention
 *  as ReaderChunk bbox rects, so the reader's coords transform applies as-is. */
export interface AnnotationRect {
  page: number; // 1-based
  rect: [number, number, number, number]; // [x0,y0,x1,y1]
}

export interface Annotation {
  id: string;
  group_id: string;
  case_id: string;
  type: AnnotationType;
  rects: AnnotationRect[];
  color?: string | null;
  comment?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Body for POST /groups/{id}/annotations — one gesture. */
export interface AnnotationCreateBody {
  case_id: string;
  type: AnnotationType;
  rects: AnnotationRect[];
  color?: string;
  comment?: string;
}

/** What the reader's capture layer emits for a new gesture (the case_id/group
 *  are added by the persistence layer, not the page). */
export interface AnnotationDraft {
  type: AnnotationType;
  rects: AnnotationRect[];
  color: string;
  comment?: string;
}

export interface Group {
  id: string;
  name: string;
  item_count: number;
  has_case?: boolean; // set when listGroups(caseId) is queried: case already in group
  created_at?: string | null;
  updated_at?: string | null;
}

export interface GroupItem {
  id: string;
  group_id: string;
  case_id: string;
  created_at?: string | null;
}

export interface GroupDetail extends Group {
  items: GroupItem[];
}
