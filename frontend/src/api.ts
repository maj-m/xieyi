import type { ApiErrorBody, CaseItem, WorkflowSnapshot } from './types'

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
  return response.json() as Promise<T>
}

export const listCases = () => request<CaseItem[]>('/cases')

export const createCase = (name: string) =>
  request<CaseItem>('/cases', {
    method: 'POST',
    body: JSON.stringify({ name, description: '由研判控制台创建' }),
  })

export const startWorkflow = (caseId: string, analysisScope: string) =>
  request<WorkflowSnapshot>(`/cases/${caseId}/workflows`, {
    method: 'POST',
    body: JSON.stringify({ analysis_scope: analysisScope }),
  })

export const getWorkflow = (threadId: string) =>
  request<WorkflowSnapshot>(`/workflows/${threadId}`)

export const resumeWorkflow = (threadId: string, approved: boolean, comment: string) =>
  request<WorkflowSnapshot>(`/workflows/${threadId}/resume`, {
    method: 'POST',
    body: JSON.stringify({ approved, comment: comment || null }),
  })

export const workflowEventsUrl = (threadId: string) =>
  `${API}/workflows/${threadId}/events`
