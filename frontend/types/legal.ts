export type RhetoricalRole = 
  | 'Fact' 
  | 'Argument' 
  | 'Statute' 
  | 'Precedent' 
  | 'RatioOfTheDecision' 
  | 'RulingByLowerCourt' 
  | 'FinalDecision';

export interface MatchedChunk {
  chunk_id: string;
  chunk_type?: string;
  chunk_text?: string;
  chunk_sequence?: number;
  score?: number;
  page_range?: [number, number];
  bbox?: any; // List of per-block bounding boxes
}

export interface CaseResult {
  case_id: string;
  case_name: string;
  citation?: string;
  court?: string;
  case_type?: string;
  verdict?: string;
  year?: number;
  date_decided?: string;
  bench: string[];
  bench_strength?: number;
  acts_cited: string[];
  sections_cited: string[];
  pdf_url?: string;
  score?: number;
  matched_chunks: MatchedChunk[];
}

export interface FacetValue {
  value: any;
  count: number;
}

export interface Facets {
  court: FacetValue[];
  case_type: FacetValue[];
  verdict: FacetValue[];
  acts_cited: FacetValue[];
  sections_cited: FacetValue[];
  bench_strength: FacetValue[];
  year_range: {
    min: number | null;
    max: number | null;
  };
}

export interface SuppressedCase {
  case_id: string;
  case_name: string;
  score?: number;
  failing_filters: Array<{ field: string; value: any }>;
}

export interface SearchResponse {
  query: string | null;
  total_cases: number;
  took_ms: number;
  results: CaseResult[];
  facets: Facets;
  suppressed: SuppressedCase[];
}
