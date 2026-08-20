<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  createCase,
  getWorkflow,
  listCases,
  resumeWorkflow,
  startWorkflow,
  workflowEventsUrl,
} from './api'
import WorkflowBoard from './components/WorkflowBoard.vue'
import type { CaseItem, ReviewAction, WorkflowSnapshot } from './types'

const cases = ref<CaseItem[]>([])
const selectedCaseId = ref('')
const workflow = ref<WorkflowSnapshot | null>(null)
const scope = ref('minimal_case_review')
const reviewComment = ref('')
const reviewer = ref('本地复核人')
const newCaseName = ref('')
const busy = ref(false)
const error = ref('')
const connection = ref<'offline' | 'connecting' | 'live'>('offline')
let eventSource: EventSource | null = null

const selectedCase = computed(() => cases.value.find((item) => item.id === selectedCaseId.value))
const waitingReview = computed(() => workflow.value?.status === 'WAITING_REVIEW')
const waitingEvidence = computed(() => workflow.value?.status === 'WAITING_EVIDENCE')
const statusText = computed(() => {
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
    workflow.value = await startWorkflow(selectedCaseId.value, scope.value)
    localStorage.setItem('whale-mas:last-thread', workflow.value.thread_id)
    connectEvents(workflow.value.thread_id)
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
    connectEvents(threadId)
  } catch {
    localStorage.removeItem('whale-mas:last-thread')
  }
}

function resetBoard() {
  eventSource?.close()
  eventSource = null
  workflow.value = null
  connection.value = 'offline'
  reviewComment.value = ''
  localStorage.removeItem('whale-mas:last-thread')
}

onMounted(async () => {
  await refreshCases()
  await recoverLastWorkflow()
})
onBeforeUnmount(() => eventSource?.close())
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
          <button v-if="!workflow" class="primary-button" type="button" :disabled="busy || !selectedCaseId" @click="start">
            <span>{{ busy ? '正在启动…' : '启动最小研判链路' }}</span><b>→</b>
          </button>
          <div v-else class="progress-block">
            <div><strong>{{ statusText }}</strong><span>{{ progress }}%</span></div>
            <div class="progress-bar"><i :style="{ width: `${progress}%` }" /></div>
            <small class="connection" :class="connection"><i /> SSE {{ connection === 'live' ? '实时连接' : '正在重连' }}</small>
          </div>
        </div>
      </section>

      <WorkflowBoard :workflow="workflow" :connection="connection" />

      <section v-if="workflow" class="detail-grid">
        <article class="panel analysis-card">
          <div class="section-heading compact"><div><span class="eyebrow">CURRENT OUTPUT</span><h2>当前研判输出</h2></div></div>
          <dl><div><dt>案件</dt><dd>{{ workflow.state.case_name }}</dd></div><div><dt>证据数量</dt><dd>{{ workflow.state.evidence_count }} 份</dd></div><div><dt>Checkpoint</dt><dd>PostgreSQL · 已持久化</dd></div></dl>
          <p class="summary">{{ workflow.state.summary || '等待节点生成研判摘要…' }}</p>
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
    </main>
  </div>
</template>
