export type WorkflowStatus =
  | 'PREPARING'
  | 'REANALYZING'
  | 'WAITING_REVIEW'
  | 'WAITING_EVIDENCE'
  | 'COMPLETED'
  | 'REJECTED'
  | 'CANCELLED'

export type ReviewAction =
  | 'APPROVE'
  | 'REANALYZE'
  | 'REQUEST_EVIDENCE'
  | 'CANCEL'
  | 'EVIDENCE_READY'

export interface ReviewRecord {
  action: ReviewAction
  comment: string | null
  reviewer: string | null
  reviewed_at: string
  round: number
}

export interface CaseItem {
  id: string
  case_no: string
  name: string
  description: string | null
  status: string
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface WorkflowState {
  case_name: string
  evidence_count: number
  analysis_scope: string
  evidence_documents: Array<{
    evidence_id: string
    filename: string
    document_type: string
    title: string
    text: string
    metadata: Record<string, unknown>
  }>
  evidence_processing: Record<string, number>
  customs_analysis: Record<string, unknown> | null
  summary: string
  review_approved: boolean | null
  review_decision: ReviewAction | null
  review_comment: string | null
  reviewer: string | null
  reviewed_at: string | null
  review_round: number
  max_review_rounds: number
  review_history: ReviewRecord[]
  result: string | null
}

export type WorkflowRunStatus =
  | 'CREATED'
  | 'RUNNING'
  | 'WAITING_REVIEW'
  | 'WAITING_EVIDENCE'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'FAILED'
  | 'TIMED_OUT'

export interface WorkflowRun {
  id: string
  thread_id: string
  case_id: string
  analysis_scope: string
  status: WorkflowRunStatus
  current_node: string | null
  review_round: number
  attempt_count: number
  max_attempts: number
  last_error_code: string | null
  last_error_message: string | null
  started_at: string
  timeout_at: string | null
  completed_at: string | null
  heartbeat_at: string | null
  version: number
}

export interface WorkflowEvent {
  id: string
  sequence: number
  event_type: string
  node_name: string | null
  status: string
  attempt: number
  payload_json: Record<string, unknown>
  error_code: string | null
  error_message: string | null
  created_at: string
}

export interface WorkflowTimeline {
  run: WorkflowRun
  events: WorkflowEvent[]
  reviews: Array<Record<string, unknown>>
  artifacts: Array<Record<string, unknown>>
}

export interface WorkflowSnapshot {
  thread_id: string
  case_id: string
  status: WorkflowStatus
  next_nodes: string[]
  interrupt: Record<string, unknown> | null
  state: WorkflowState
  run: WorkflowRun | null
}

export interface ApiErrorBody {
  error?: { message?: string }
}

export interface EvidenceItem {
  id: string
  case_id: string
  original_filename: string
  mime_type: string
  file_size: number
  sha256: string
  document_type: string
  parent_evidence_id: string | null
  created_at: string
}

export type EvidenceProcessingStatus =
  | 'QUEUED'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'UNSUPPORTED'
  | 'OCR_REQUIRED'
  | 'FAILED'

export interface EvidenceProcessingJob {
  id: string
  case_id: string
  evidence_id: string
  status: EvidenceProcessingStatus
  parser_name: string | null
  parser_version: string | null
  attempt_count: number
  max_attempts: number
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface NormalizedDocument {
  id: string
  evidence_id: string
  status: 'READY' | 'UNSUPPORTED' | 'OCR_REQUIRED'
  title: string | null
  text_preview: string | null
  content_object_key: string | null
  metadata_json: Record<string, unknown>
}
