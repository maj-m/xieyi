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

export interface WorkflowSnapshot {
  thread_id: string
  case_id: string
  status: WorkflowStatus
  next_nodes: string[]
  interrupt: Record<string, unknown> | null
  state: WorkflowState
}

export interface ApiErrorBody {
  error?: { message?: string }
}
