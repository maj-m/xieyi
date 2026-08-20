export type WorkflowStatus = 'PREPARING' | 'WAITING_REVIEW' | 'COMPLETED' | 'REJECTED'

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
  review_comment: string | null
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
