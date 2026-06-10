export type RhetoricalRole = 
  | 'Fact' 
  | 'Argument' 
  | 'Statute' 
  | 'Precedent' 
  | 'RatioOfTheDecision' 
  | 'RulingByLowerCourt' 
  | 'FinalDecision';

export interface CaseChunk {
  chunk_id: string;
  doc_id: string;
  case_name: string;
  court: string;
  year: number;
  segment_label: RhetoricalRole;
  raw_text: string;
  page_number: number;
  statute_tags?: string[];
  precedent_citations?: string[];
  relevance_score: number;
}

export interface SearchResponse {
  query: string;
  total_results: number;
  results: CaseChunk[];
  search_time_ms: number;
}
