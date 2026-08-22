<script setup lang="ts">
/**
 * 研判控制台主页面：组织案件选择、证据标准化、工作流控制、人工复核和运行事件展示。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  cancelWorkflow,
  createCase,
  deleteEvidence,
  findWorkflowRun,
  getWorkflow,
  getWorkflowTimeline,
  getNormalizedDocument,
  enqueueEvidenceProcessing,
  listEvidence,
  listEvidenceProcessingJobs,
  listCases,
  resumeWorkflow,
  retryWorkflow,
  startWorkflow,
  workflowEventsUrl,
  uploadEvidence,
} from './api'
import WorkflowBoard from './components/WorkflowBoard.vue'
import type {
  CaseItem,
  EvidenceItem,
  EvidenceProcessingJob,
  NormalizedDocument,
  ReviewAction,
  WorkflowEvent,
  WorkflowSnapshot,
} from './types'

interface CustomsAnalysis {
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW'
  declared_amount_usd: number | null
  actual_amount_usd: number | null
  payment_total_usd: number | null
  difference_usd: number | null
  declaration_numbers: string[]
  invoice_numbers: string[]
  findings: string[]
  evidence_reasons?: Array<{ finding: string; evidence_ids: string[] }>
  evidence_refs: Array<{ evidence_id: string; filename: string; document_type: string }>
  rule_version: string
  analysis_method?: 'LLM' | 'RULE' | 'RULE_FALLBACK'
  llm_trace?: { model?: string }
}

const cases = ref<CaseItem[]>([])
const selectedCaseId = ref('')
const workflow = ref<WorkflowSnapshot | null>(null)
const scope = ref('customs_risk_analysis')
const reviewComment = ref('')
const reviewer = ref('本地复核人')
const newCaseName = ref('')
const busy = ref(false)
const error = ref('')
const connection = ref<'offline' | 'connecting' | 'live'>('offline')
const workflowEvents = ref<WorkflowEvent[]>([])
const evidenceItems = ref<EvidenceItem[]>([])
const processingJobs = ref<EvidenceProcessingJob[]>([])
const normalizedDocument = ref<NormalizedDocument | null>(null)
const hoveredEvidenceId = ref('')
const hoverPreview = ref<NormalizedDocument | null>(null)
const hoverPreviewError = ref('')
const uploadingEvidence = ref(false)
const evidencePreviewCache = new Map<string, NormalizedDocument>()
let eventSource: EventSource | null = null
let evidenceTimer: number | null = null

const selectedCase = computed(() => cases.value.find((item) => item.id === selectedCaseId.value))
const customsAnalysis = computed(
  () => workflow.value?.state.customs_analysis as CustomsAnalysis | null,
)
const evidenceReady = computed(
  () =>
    evidenceItems.value.length > 0 &&
    evidenceItems.value.every((item) => jobFor(item.id)?.status === 'COMPLETED'),
)
const canStart = computed(
  () =>
    Boolean(selectedCaseId.value) &&
    (scope.value !== 'customs_risk_analysis' || evidenceReady.value),
)
const waitingReview = computed(
  () =>
    workflow.value?.status === 'WAITING_REVIEW' &&
    (!workflow.value.run || workflow.value.run.status === 'WAITING_REVIEW'),
)
const waitingEvidence = computed(
  () =>
    workflow.value?.status === 'WAITING_EVIDENCE' &&
    (!workflow.value.run || workflow.value.run.status === 'WAITING_EVIDENCE'),
)
const statusText = computed(() => {
  if (workflow.value?.run?.status === 'FAILED') return '执行失败，等待重试'
  if (workflow.value?.run?.status === 'TIMED_OUT') return '工作流已超时'
  if (workflow.value?.run?.status === 'CANCELLED') return '工作流已取消'
  const labels = {
    PREPARING: '正在准备',
    REANALYZING: '正在重新研判',
    WAITING_REVIEW: '等待人工复核',
    WAITING_EVIDENCE: '等待补充证据',
    COMPLETED: '研判已完成',
    REJECTED: '复核未通过',
    CANCELLED: '流程已终止',
  }
  return workflow.value ? labels[workflow.value.status] : '尚未启动'
})
const progress = computed(() => {
  if (!workflow.value) return 0
  if (['COMPLETED', 'CANCELLED', 'FAILED', 'TIMED_OUT'].includes(workflow.value.run?.status ?? '')) return 100
  if (workflow.value.status === 'PREPARING') return 18
  if (workflow.value.status === 'REANALYZING') return 48
  if (workflow.value.status === 'WAITING_REVIEW') return 62
  if (workflow.value.status === 'WAITING_EVIDENCE') return 72
  return 100
})

function showError(cause: unknown) {
  error.value = cause instanceof Error ? cause.message : '发生未知错误'
}

function connectEvents(threadId: string) {
  eventSource?.close()
  connection.value = 'connecting'
  const source = new EventSource(workflowEventsUrl(threadId))
  eventSource = source
  source.addEventListener('workflow_snapshot', (event) => {
    workflow.value = JSON.parse((event as MessageEvent<string>).data) as WorkflowSnapshot
    connection.value = 'live'
  })
  source.addEventListener('workflow_event', (event) => {
    const item = JSON.parse((event as MessageEvent<string>).data) as WorkflowEvent
    if (!workflowEvents.value.some((existing) => existing.sequence === item.sequence)) {
      workflowEvents.value.push(item)
      workflowEvents.value.sort((left, right) => left.sequence - right.sequence)
    }
  })
  source.onopen = () => (connection.value = 'live')
  source.onerror = () => (connection.value = 'connecting')
}

async function refreshCases() {
  try {
    cases.value = await listCases()
    if (!selectedCaseId.value && cases.value.length) selectedCaseId.value = cases.value[0].id
  } catch (cause) {
    showError(cause)
  }
}

async function refreshEvidence() {
  if (!selectedCaseId.value) return
  evidenceItems.value = await listEvidence(selectedCaseId.value)
  processingJobs.value = await listEvidenceProcessingJobs(selectedCaseId.value)
}

function jobFor(evidenceId: string) {
  return processingJobs.value.find((item) => item.evidence_id === evidenceId)
}

function evidenceRefsForFinding(finding: string) {
  const ids = new Set(
    customsAnalysis.value?.evidence_reasons?.find((item) => item.finding === finding)
      ?.evidence_ids ?? [],
  )
  return customsAnalysis.value?.evidence_refs.filter((item) => ids.has(item.evidence_id)) ?? []
}

async function showEvidencePreview(evidenceId: string) {
  if (!selectedCaseId.value) return
  hoveredEvidenceId.value = evidenceId
  hoverPreviewError.value = ''
  const cached = evidencePreviewCache.get(evidenceId)
  if (cached) {
    hoverPreview.value = cached
    return
  }
  hoverPreview.value = null
  try {
    const document = await getNormalizedDocument(selectedCaseId.value, evidenceId)
    evidencePreviewCache.set(evidenceId, document)
    if (hoveredEvidenceId.value === evidenceId) hoverPreview.value = document
  } catch {
    if (hoveredEvidenceId.value === evidenceId) hoverPreviewError.value = '暂时无法加载文件预览'
  }
}

function hideEvidencePreview() {
  hoveredEvidenceId.value = ''
  hoverPreview.value = null
  hoverPreviewError.value = ''
}

async function submitEvidence(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !selectedCaseId.value) return
  uploadingEvidence.value = true
  error.value = ''
  try {
    const evidence = await uploadEvidence(selectedCaseId.value, file)
    await enqueueEvidenceProcessing(selectedCaseId.value, evidence.id)
    await refreshEvidence()
  } catch (cause) {
    showError(cause)
  } finally {
    uploadingEvidence.value = false
    input.value = ''
  }
}

async function queueEvidence(evidenceId: string) {
  busy.value = true
  error.value = ''
  try {
    await enqueueEvidenceProcessing(selectedCaseId.value, evidenceId)
    await refreshEvidence()
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function removeEvidence(item: EvidenceItem) {
  if (!selectedCaseId.value || !window.confirm(`确认删除“${item.original_filename}”？此操作不可撤销。`)) return
  busy.value = true
  error.value = ''
  try {
    await deleteEvidence(selectedCaseId.value, item.id)
    if (normalizedDocument.value?.evidence_id === item.id) normalizedDocument.value = null
    await refreshEvidence()
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function inspectNormalized(evidenceId: string) {
  if (!selectedCaseId.value) return
  try {
    normalizedDocument.value = await getNormalizedDocument(selectedCaseId.value, evidenceId)
  } catch (cause) {
    showError(cause)
  }
}

async function addCase() {
  if (!newCaseName.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    const created = await createCase(newCaseName.value.trim())
    cases.value.unshift(created)
    selectedCaseId.value = created.id
    newCaseName.value = ''
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function start() {
  if (!selectedCaseId.value) return
  busy.value = true
  error.value = ''
  try {
    await refreshEvidence()
    workflowEvents.value = []
    const caseId = selectedCaseId.value
    const idempotencyKey = crypto.randomUUID()
    let settled = false
    const startRequest = startWorkflow(caseId, scope.value, idempotencyKey).finally(() => {
      settled = true
    })
    while (!settled && !workflow.value) {
      await new Promise((resolve) => window.setTimeout(resolve, 150))
      try {
        const run = await findWorkflowRun(caseId, idempotencyKey)
        workflow.value = await getWorkflow(run.thread_id)
        localStorage.setItem('whale-mas:last-thread', run.thread_id)
        connectEvents(run.thread_id)
      } catch {
        // 工作流记录或首个 checkpoint 尚未提交，继续短暂轮询。
      }
    }
    workflow.value = await startRequest
    localStorage.setItem('whale-mas:last-thread', workflow.value.thread_id)
    connectEvents(workflow.value.thread_id)
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function loadTimeline(threadId: string) {
  try {
    const timeline = await getWorkflowTimeline(threadId)
    workflowEvents.value = timeline.events
    if (workflow.value) workflow.value.run = timeline.run
  } catch (cause) {
    showError(cause)
  }
}

async function retryFailedWorkflow() {
  if (!workflow.value) return
  busy.value = true
  error.value = ''
  try {
    workflow.value = await retryWorkflow(workflow.value.thread_id)
    await loadTimeline(workflow.value.thread_id)
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function forceCancelWorkflow() {
  if (!workflow.value || !window.confirm('确认取消整个工作流？取消后不能继续恢复。')) return
  busy.value = true
  error.value = ''
  try {
    const timeline = await cancelWorkflow(workflow.value.thread_id, '由研判控制台取消')
    workflow.value.run = timeline.run
    workflowEvents.value = timeline.events
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function decide(decision: ReviewAction) {
  if (!workflow.value) return
  if (decision === 'CANCEL' && !window.confirm('确认终止当前案件研判流程？')) return
  busy.value = true
  error.value = ''
  try {
    workflow.value = await resumeWorkflow(
      workflow.value.thread_id,
      decision,
      reviewComment.value,
      reviewer.value,
    )
    reviewComment.value = ''
  } catch (cause) {
    showError(cause)
  } finally {
    busy.value = false
  }
}

async function recoverLastWorkflow() {
  const threadId = localStorage.getItem('whale-mas:last-thread')
  if (!threadId) return
  try {
    workflow.value = await getWorkflow(threadId)
    selectedCaseId.value = workflow.value.case_id
    await loadTimeline(threadId)
    connectEvents(threadId)
  } catch {
    localStorage.removeItem('whale-mas:last-thread')
  }
}

function resetBoard() {
  eventSource?.close()
  eventSource = null
  workflow.value = null
  workflowEvents.value = []
  connection.value = 'offline'
  reviewComment.value = ''
  localStorage.removeItem('whale-mas:last-thread')
}

function eventLabel(eventType: string) {
  const labels: Record<string, string> = {
    WORKFLOW_STARTED: '工作流启动',
    WORKFLOW_RESUMED: '工作流恢复',
    NODE_STARTED: '节点开始执行',
    NODE_COMPLETED: '节点执行完成',
    WORKFLOW_PAUSED: '工作流暂停',
    REVIEW_DECIDED: '人工复核决定',
    ARTIFACT_CREATED: '分析产物生成',
    WORKFLOW_COMPLETED: '工作流完成',
    WORKFLOW_CANCELLED: '工作流取消',
    WORKFLOW_FAILED: '工作流失败',
    WORKFLOW_RETRYING: '工作流重试',
    WORKFLOW_TIMED_OUT: '工作流超时',
  }
  return labels[eventType] ?? eventType
}

function usd(value: number | null) {
  return value === null ? '未识别' : `$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
}

onMounted(async () => {
  await refreshCases()
  await refreshEvidence()
  await recoverLastWorkflow()
  evidenceTimer = window.setInterval(() => {
    if (processingJobs.value.some((item) => ['QUEUED', 'PROCESSING'].includes(item.status))) {
      void refreshEvidence()
    }
  }, 2000)
})
watch(selectedCaseId, () => {
  normalizedDocument.value = null
  evidencePreviewCache.clear()
  hideEvidencePreview()
  void refreshEvidence()
})
onBeforeUnmount(() => {
  eventSource?.close()
  if (evidenceTimer !== null) window.clearInterval(evidenceTimer)
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <a class="brand" href="#" aria-label="鲸鲨 MAS 首页">
        <span class="brand-mark">鲸</span>
        <span><strong>鲸鲨 MAS</strong><small>MULTI-AGENT SYSTEM</small></span>
      </a>
      <div class="system-state"><i /> 本地研判环境</div>
    </header>

    <main>
      <section class="hero">
        <div>
          <span class="eyebrow">INVESTIGATION WORKSPACE / 研判工作台</span>
          <h1>案件研判框架运行全景</h1>
          <p>面向技术汇报展示请求如何经过应用、数据存储、LangGraph 与人工复核节点。</p>
        </div>
        <button v-if="workflow" class="ghost-button" type="button" @click="resetBoard">开始新流程</button>
      </section>

      <div v-if="error" class="error-banner"><span>!</span>{{ error }}<button @click="error = ''">×</button></div>

      <section class="control-grid">
        <div class="panel case-panel">
          <div class="section-heading compact"><div><span class="eyebrow">CASE INPUT</span><h2>选择案件</h2></div></div>
          <label>案件</label>
          <select v-model="selectedCaseId" :disabled="Boolean(workflow)">
            <option value="" disabled>请选择案件</option>
            <option v-for="item in cases" :key="item.id" :value="item.id">{{ item.case_no }} · {{ item.name }}</option>
          </select>
          <div class="case-meta" v-if="selectedCase">
            <span>状态 {{ selectedCase.status }}</span><span>创建于 {{ new Date(selectedCase.created_at).toLocaleDateString('zh-CN') }}</span>
          </div>
          <div v-if="!workflow" class="new-case-row">
            <input v-model="newCaseName" placeholder="没有案件？输入名称快速创建" @keyup.enter="addCase" />
            <button type="button" :disabled="busy || !newCaseName.trim()" @click="addCase">创建</button>
          </div>
        </div>

        <div class="panel launch-panel">
          <div class="section-heading compact"><div><span class="eyebrow">WORKFLOW CONTROL</span><h2>流程控制</h2></div></div>
          <label>分析范围</label>
          <input v-model="scope" :disabled="Boolean(workflow)" />
          <button v-if="!workflow" class="primary-button" type="button" :disabled="busy || !canStart" @click="start">
            <span>{{ busy ? '正在启动…' : '启动最小研判链路' }}</span><b>→</b>
          </button>
          <small v-if="!workflow && scope === 'customs_risk_analysis' && !evidenceReady" class="evidence-gate">
            请先确保所有证据均为 COMPLETED；未入队文件可在下方手动入队。
          </small>
          <div v-else class="progress-block">
            <div><strong>{{ statusText }}</strong><span>{{ progress }}%</span></div>
            <div class="progress-bar"><i :style="{ width: `${progress}%` }" /></div>
            <small class="connection" :class="connection"><i /> SSE {{ connection === 'live' ? '实时连接' : '正在重连' }}</small>
          </div>
        </div>
      </section>

      <section class="panel evidence-panel">
        <div class="section-heading compact">
          <div><span class="eyebrow">EVIDENCE INGESTION</span><h2>证据读取与标准化</h2></div>
          <label class="upload-button" :class="{ disabled: !selectedCaseId || uploadingEvidence }">
            {{ uploadingEvidence ? '正在上传…' : '上传并入队' }}
            <input type="file" :disabled="!selectedCaseId || uploadingEvidence" @change="submitEvidence" />
          </label>
        </div>
        <div v-if="evidenceItems.length" class="evidence-table">
          <article v-for="item in evidenceItems" :key="item.id">
            <div><strong>{{ item.original_filename }}</strong><small>{{ item.document_type }} · {{ (item.file_size / 1024).toFixed(1) }} KiB</small></div>
            <span class="processing-status" :class="`processing-${jobFor(item.id)?.status.toLowerCase()}`">{{ jobFor(item.id)?.status ?? (item.parent_evidence_id ? 'ATTACHMENT' : 'NOT_QUEUED') }}</span>
            <small>{{ jobFor(item.id) ? `${jobFor(item.id)?.attempt_count}/${jobFor(item.id)?.max_attempts} 次尝试` : item.sha256.slice(0, 12) }}</small>
            <span class="evidence-actions">
              <button v-if="jobFor(item.id)?.status === 'COMPLETED'" type="button" @click="inspectNormalized(item.id)">查看标准化结果</button>
              <button v-else-if="!jobFor(item.id)" type="button" :disabled="busy" @click="queueEvidence(item.id)">入队解析</button>
              <button v-if="!workflow" class="delete-evidence-button" type="button" :disabled="busy" @click="removeEvidence(item)">删除</button>
            </span>
          </article>
        </div>
        <p v-else class="empty-events">当前案件暂无证据。已支持 EML、TXT、CSV、XLS/XLSX、DOCX 和 PDF 解析。</p>
        <div v-if="normalizedDocument" class="normalized-preview">
          <div><strong>{{ normalizedDocument.title || '未命名文档' }}</strong><button @click="normalizedDocument = null">×</button></div>
          <p>{{ normalizedDocument.text_preview || '该文档没有可预览正文。' }}</p>
          <small>完整标准化 JSON：{{ normalizedDocument.content_object_key || '未生成' }}</small>
        </div>
      </section>

      <WorkflowBoard :workflow="workflow" :connection="connection" />

      <section v-if="workflow" class="detail-grid">
        <article class="panel analysis-card">
          <div class="section-heading compact"><div><span class="eyebrow">CURRENT OUTPUT</span><h2>当前研判输出</h2></div></div>
          <dl><div><dt>案件</dt><dd>{{ workflow.state.case_name }}</dd></div><div><dt>证据数量</dt><dd>{{ workflow.state.evidence_count }} 份</dd></div><div><dt>Checkpoint</dt><dd>PostgreSQL · 已持久化</dd></div></dl>
          <p v-if="!customsAnalysis" class="summary">{{ workflow.state.summary || '等待节点生成研判摘要…' }}</p>
          <template v-if="customsAnalysis">
            <div class="risk-hero" :class="`risk-${customsAnalysis.risk_level.toLowerCase()}`">
              <div><span>海关价格申报风险</span><strong>{{ customsAnalysis.risk_level }}</strong></div>
              <p>{{ customsAnalysis.risk_level === 'HIGH' ? '发现显著风险信号，建议优先人工复核' : customsAnalysis.risk_level === 'MEDIUM' ? '发现需要进一步核验的风险信号' : '当前材料未发现显著价格申报风险' }}</p>
              <small>{{ customsAnalysis.analysis_method ?? 'RULE' }} · {{ customsAnalysis.llm_trace?.model ?? customsAnalysis.rule_version }}</small>
            </div>
            <div class="amount-grid">
              <div><span>申报金额</span><strong>{{ usd(customsAnalysis.declared_amount_usd) }}</strong></div>
              <div><span>实际成交/付款</span><strong>{{ usd(customsAnalysis.actual_amount_usd) }}</strong></div>
              <div><span>申报差额</span><strong>{{ usd(customsAnalysis.difference_usd) }}</strong></div>
            </div>
            <div class="linked-identifiers">
              <span>报关单：{{ customsAnalysis.declaration_numbers.join('、') || '未识别' }}</span>
              <span>发票：{{ customsAnalysis.invoice_numbers.join('、') || '未识别' }}</span>
              <span>关联证据：{{ customsAnalysis.evidence_refs.length }} 份</span>
            </div>
            <div class="analysis-conversation">
              <article class="analysis-message conclusion-message">
                <span class="agent-avatar">AI</span>
                <div><small>综合研判结论</small><p>{{ workflow.state.summary }}</p></div>
              </article>
              <article v-for="(finding, index) in customsAnalysis.findings" :key="finding" class="analysis-message">
                <span class="message-index">{{ String(index + 1).padStart(2, '0') }}</span>
                <div>
                  <small>研判依据</small>
                  <p>{{ finding }}</p>
                  <div v-if="evidenceRefsForFinding(finding).length" class="evidence-citations">
                    <span
                      v-for="reference in evidenceRefsForFinding(finding)"
                      :key="reference.evidence_id"
                      class="evidence-citation"
                      @mouseenter="showEvidencePreview(reference.evidence_id)"
                      @mouseleave="hideEvidencePreview"
                      @focusin="showEvidencePreview(reference.evidence_id)"
                      @focusout="hideEvidencePreview"
                    >
                      <button type="button" @click="inspectNormalized(reference.evidence_id)">▧ {{ reference.filename }}</button>
                      <aside v-if="hoveredEvidenceId === reference.evidence_id" role="tooltip" class="evidence-tooltip">
                        <strong>{{ reference.filename }}</strong>
                        <small>{{ reference.document_type }} · 标准化内容预览</small>
                        <p v-if="hoverPreview">{{ hoverPreview.text_preview || '该文件没有可预览正文。' }}</p>
                        <p v-else>{{ hoverPreviewError || '正在加载预览…' }}</p>
                      </aside>
                    </span>
                  </div>
                </div>
              </article>
              <div class="all-evidence-links">
                <span>本轮关联文件</span>
                <span
                  v-for="reference in customsAnalysis.evidence_refs"
                  :key="reference.evidence_id"
                  class="evidence-citation"
                  @mouseenter="showEvidencePreview(reference.evidence_id)"
                  @mouseleave="hideEvidencePreview"
                  @focusin="showEvidencePreview(reference.evidence_id)"
                  @focusout="hideEvidencePreview"
                >
                  <button type="button" @click="inspectNormalized(reference.evidence_id)">{{ reference.filename }}</button>
                  <aside v-if="hoveredEvidenceId === reference.evidence_id" role="tooltip" class="evidence-tooltip">
                    <strong>{{ reference.filename }}</strong>
                    <small>{{ reference.document_type }} · 标准化内容预览</small>
                    <p v-if="hoverPreview">{{ hoverPreview.text_preview || '该文件没有可预览正文。' }}</p>
                    <p v-else>{{ hoverPreviewError || '正在加载预览…' }}</p>
                  </aside>
                </span>
              </div>
            </div>
          </template>
          <p v-if="workflow.state.result" class="result">{{ workflow.state.result }}</p>
        </article>

        <article class="panel review-card" :class="{ muted: !waitingReview && !waitingEvidence }">
          <div class="section-heading compact"><div><span class="eyebrow">HUMAN IN THE LOOP</span><h2>人工复核 · 第 {{ workflow.state.review_round }} 轮</h2></div><span class="pause-pill">INTERRUPT</span></div>
          <template v-if="waitingReview">
            <p>{{ String(workflow.interrupt?.question ?? '请确认是否批准当前研判结果。') }}</p>
            <label>复核人</label>
            <input v-model="reviewer" maxlength="128" placeholder="填写复核人" />
            <label class="review-comment-label">复核意见</label>
            <textarea v-model="reviewComment" rows="3" placeholder="填写复核意见（选填）" />
            <div class="review-actions multi-actions">
              <button class="approve-button" :disabled="busy" @click="decide('APPROVE')">批准归档</button>
              <button class="reanalyze-button" :disabled="busy || workflow.state.review_round >= workflow.state.max_review_rounds" @click="decide('REANALYZE')">退回重研</button>
              <button class="evidence-button" :disabled="busy" @click="decide('REQUEST_EVIDENCE')">补充证据</button>
              <button class="reject-button" :disabled="busy" @click="decide('CANCEL')">终止流程</button>
            </div>
            <small class="round-limit">最多 {{ workflow.state.max_review_rounds }} 轮；达到上限后不能继续退回重研。</small>
          </template>
          <template v-else-if="waitingEvidence">
            <p>{{ String(workflow.interrupt?.question ?? '请上传补充材料，完成后恢复流程。') }}</p>
            <label>经办人</label>
            <input v-model="reviewer" maxlength="128" placeholder="填写经办人" />
            <label class="review-comment-label">材料说明</label>
            <textarea v-model="reviewComment" rows="3" placeholder="说明本次补充的材料（选填）" />
            <button class="approve-button evidence-ready-button" :disabled="busy" @click="decide('EVIDENCE_READY')">材料已上传，重新研判 →</button>
          </template>
          <template v-else>
            <p>{{ workflow.state.review_comment || (workflow.status === 'PREPARING' ? '流程运行到此处会自动暂停。' : '复核节点已经处理。') }}</p>
          </template>
          <div v-if="workflow.state.review_history.length" class="review-history">
            <strong>复核记录</strong>
            <div v-for="(record, index) in workflow.state.review_history" :key="`${record.reviewed_at}-${index}`">
              <span>第 {{ record.round }} 轮 · {{ record.action }}</span>
              <small>{{ record.reviewer || '未署名' }} · {{ new Date(record.reviewed_at).toLocaleString('zh-CN') }}</small>
              <p v-if="record.comment">{{ record.comment }}</p>
            </div>
          </div>
        </article>
      </section>

      <section v-if="workflow?.run" class="panel runtime-panel">
        <div class="section-heading compact">
          <div><span class="eyebrow">DURABLE BUSINESS RECORDS</span><h2>业务运行记录</h2></div>
          <span class="run-status" :class="`run-${workflow.run.status.toLowerCase()}`">{{ workflow.run.status }}</span>
        </div>
        <div class="runtime-summary">
          <div><span>当前节点</span><strong>{{ workflow.run.current_node || '已结束' }}</strong></div>
          <div><span>执行尝试</span><strong>{{ workflow.run.attempt_count }} / {{ workflow.run.max_attempts }}</strong></div>
          <div><span>业务版本</span><strong>v{{ workflow.run.version }}</strong></div>
          <div><span>持久化</span><strong>PostgreSQL</strong></div>
        </div>
        <div v-if="workflow.run.last_error_message" class="runtime-error">
          <strong>{{ workflow.run.last_error_code }}</strong><span>{{ workflow.run.last_error_message }}</span>
        </div>
        <div class="runtime-actions">
          <button v-if="workflow.run.status === 'FAILED'" class="reanalyze-button" :disabled="busy" @click="retryFailedWorkflow">重试失败节点</button>
          <button v-if="['CREATED', 'RUNNING', 'WAITING_REVIEW', 'WAITING_EVIDENCE'].includes(workflow.run.status)" class="reject-button" :disabled="busy" @click="forceCancelWorkflow">取消整个工作流</button>
        </div>
        <div class="event-timeline">
          <article v-for="item in workflowEvents.slice().reverse()" :key="item.id" class="event-row">
            <span class="event-sequence">#{{ item.sequence }}</span>
            <i :class="`event-${item.event_type.toLowerCase()}`" />
            <div><strong>{{ eventLabel(item.event_type) }}</strong><small>{{ item.node_name || 'workflow' }} · 第 {{ item.attempt }} 次尝试</small></div>
            <time>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</time>
          </article>
          <p v-if="!workflowEvents.length" class="empty-events">等待业务事件写入…</p>
        </div>
      </section>
    </main>
  </div>
</template>
