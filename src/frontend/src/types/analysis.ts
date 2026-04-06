/** Possible analysis statuses. */
export type AnalysisStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed";

/** Evaluation verdict for a completed analysis. */
export type AnalysisVerdict = "PASSED" | "FAILED" | "INCONCLUSIVE";

/** A tool call made during analysis. */
export interface AnalysisToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: string;
}

/** Single analysis record returned by the API. */
export interface Analysis {
  id: string;
  projectId: string;
  prompt: string;
  status: AnalysisStatus;
  response?: string;
  verdict?: AnalysisVerdict;
  confidenceScore?: number;
  toolCalls?: AnalysisToolCall[];
  errorMessage?: string;
  createdAt: string;
  updatedAt: string;
}

/** Response shape for paginated analysis list. */
export interface AnalysisListResponse {
  data: Analysis[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next_page: boolean;
  };
}

/** Response shape for single analysis. */
export interface AnalysisSingleResponse {
  data: Analysis;
}
