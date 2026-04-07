/** Standard metadata included in every API response. */
export interface Meta {
  requestId: string;
  timestamp: string;
}

/** Standard API response envelope. */
export interface ResponseEnvelope<T> {
  meta: Meta;
  data: T;
}

/** Pagination details returned by list endpoints. */
export interface PaginationInfo {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

/** Paginated API response envelope. */
export interface PaginatedResponse<T> {
  meta: Meta;
  data: T[];
  pagination: PaginationInfo;
}

/** Structured error returned by the API on non-OK responses. */
export interface ApiError {
  status: number;
  message: string;
  detail?: string;
}

/** All possible artifact processing statuses. */
export type ArtifactStatus =
  | "uploading"
  | "uploaded"
  | "scanning"
  | "scan_passed"
  | "scan_failed"
  | "quarantined"
  | "parsing"
  | "parsed"
  | "parse_failed"
  | "graph_building"
  | "graph_built"
  | "graph_failed"
  | "unsupported";
