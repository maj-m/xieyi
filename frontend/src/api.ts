/** 前端 API 适配层：集中封装案件、证据处理和研判工作流的后端请求。 */

import type {
  ApiErrorBody,
  CaseItem,
  EvidenceItem,
  EvidenceProcessingJob,
  NormalizedDocument,
  ReviewAction,
  WorkflowSnapshot,
  WorkflowRun,
  WorkflowTimeline,
} from './types'

const API = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody
    throw new Error(body.error?.message ?? `请求失败（${response.status}）`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const listCases = () => request<CaseItem[]>('/cases')

export const createCase = (name: string) =>
  request<CaseItem>('/cases', {
    method: 'POST',
    body: JSON.stringify({ name, description: '由研判控制台创建' }),
  })

export const startWorkflow = (caseId: string, analysisScope: string, idempotencyKey: string) =>
  request<WorkflowSnapshot>(`/cases/${caseId}/workflows`, {
    method: 'POST',
    body: JSON.stringify({
      analysis_scope: analysisScope,
      idempotency_key: idempotencyKey,
      max_attempts: 3,
    }),
  })

export const findWorkflowRun = (caseId: string, idempotencyKey: string) =>
  request<WorkflowRun>(
    `/cases/${caseId}/workflows/by-idempotency/${encodeURIComponent(idempotencyKey)}`,
  )

export const getWorkflow = (threadId: string) =>
  request<WorkflowSnapshot>(`/workflows/${threadId}`)

export const resumeWorkflow = (
  threadId: string,
  decision: ReviewAction,
  comment: string,
  reviewer: string,
) =>
  request<WorkflowSnapshot>(`/workflows/${threadId}/resume`, {
    method: 'POST',
    body: JSON.stringify({
      decision,
      comment: comment || null,
      reviewer: reviewer || null,
      idempotency_key: crypto.randomUUID(),
    }),
  })

export const getWorkflowTimeline = (threadId: string) =>
  request<WorkflowTimeline>(`/workflows/${threadId}/timeline`)

export const retryWorkflow = (threadId: string) =>
  request<WorkflowSnapshot>(`/workflows/${threadId}/retry`, {
    method: 'POST',
    body: JSON.stringify({ requested_by: 'console-operator' }),
  })

export const cancelWorkflow = (threadId: string, reason: string) =>
  request<WorkflowTimeline>(`/workflows/${threadId}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ requested_by: 'console-operator', reason: reason || null }),
  })

export const workflowEventsUrl = (threadId: string) =>
  `${API}/workflows/${threadId}/events`

export const listEvidence = (caseId: string) =>
  request<EvidenceItem[]>(`/cases/${caseId}/evidence`)

export const deleteEvidence = (caseId: string, evidenceId: string) =>
  request<void>(`/cases/${caseId}/evidence/${evidenceId}`, { method: 'DELETE' })

export async function uploadEvidence(caseId: string, file: File): Promise<EvidenceItem> {
  const form = new FormData()
  form.append('file', file)
  form.append('source_type', file.name.toLowerCase().endsWith('.eml') ? 'EMAIL' : 'OTHER')
  const response = await fetch(`${API}/cases/${caseId}/evidence`, { method: 'POST', body: form })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody
    throw new Error(body.error?.message ?? `上传失败（${response.status}）`)
  }
  return response.json() as Promise<EvidenceItem>
}

export const enqueueEvidenceProcessing = (caseId: string, evidenceId: string) =>
  request<EvidenceProcessingJob>(`/cases/${caseId}/evidence/${evidenceId}/processing-jobs`, {
    method: 'POST',
    body: JSON.stringify({ idempotency_key: crypto.randomUUID(), max_attempts: 3 }),
  })

export const listEvidenceProcessingJobs = (caseId: string) =>
  request<EvidenceProcessingJob[]>(`/cases/${caseId}/evidence/processing-jobs`)

export const getNormalizedDocument = (caseId: string, evidenceId: string) =>
  request<NormalizedDocument>(`/cases/${caseId}/evidence/${evidenceId}/normalized`)
