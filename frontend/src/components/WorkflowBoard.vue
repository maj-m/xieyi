<script setup lang="ts">
/** 工作流节点看板：将后端快照映射为节点状态、数据流向和基础设施关系。 */

import { computed } from 'vue'
import type { WorkflowSnapshot } from '../types'

type StepStatus = 'pending' | 'active' | 'waiting' | 'complete' | 'rejected'

const props = defineProps<{
  workflow: WorkflowSnapshot | null
  connection: 'offline' | 'connecting' | 'live'
}>()

const terminal = computed(() =>
  ['COMPLETED', 'CANCELLED', 'REJECTED'].includes(props.workflow?.status ?? '') ||
  ['COMPLETED', 'CANCELLED', 'FAILED', 'TIMED_OUT'].includes(props.workflow?.run?.status ?? ''),
)
const isCustoms = computed(() => props.workflow?.state.analysis_scope === 'customs_risk_analysis')
const waitingEvidence = computed(() => props.workflow?.status === 'WAITING_EVIDENCE')
const waitingReview = computed(() => props.workflow?.status === 'WAITING_REVIEW')

const statusLabel: Record<StepStatus, string> = {
  pending: '待执行',
  active: '执行中',
  waiting: '暂停等待',
  complete: '已执行',
  rejected: '未通过',
}

const accessSteps = computed(() => [
  {
    no: '01', title: '选择案件与上传材料', tech: 'Vue 3 Console', detail: '邮件、附件、付款和查验文件',
    status: (props.workflow ? 'complete' : 'active') as StepStatus,
  },
  {
    no: '02', title: '文件与摘要分开保存', tech: 'MinIO + PostgreSQL', detail: '原文件入对象存储，元数据入业务库',
    status: (props.workflow ? 'complete' : 'pending') as StepStatus,
  },
  {
    no: '03', title: '异步解析并标准化', tech: 'Evidence Worker', detail: 'EML / Office / CSV / TXT / PDF → JSON',
    status: (props.workflow ? 'complete' : 'pending') as StepStatus,
  },
  {
    no: '04', title: '启动前技术门禁', tech: 'FastAPI preflight', detail: '全部证据就绪后才创建工作流',
    status: (props.workflow ? 'complete' : 'pending') as StepStatus,
  },
])

const graphSteps = computed(() => [
    {
      no: '05', title: '加载标准化证据', tech: 'load_normalized_evidence', detail: '从 MinIO 读取标准化 JSON 正文',
      status: (!props.workflow || waitingEvidence.value ? 'pending' : 'complete') as StepStatus,
    },
    {
      no: '06', title: '海关要素关联研判', tech: 'analyze_customs_case', detail: '报关单 / 发票 / 邮件 / 付款金额关联',
      status: (!props.workflow || waitingEvidence.value ? 'pending' : isCustoms.value ? 'complete' : 'pending') as StepStatus,
    },
    {
      no: '07', title: '生成第一轮研判结果', tech: 'prepare_case + checkpoint', detail: '保存风险、差额、依据和证据引用',
      status: (!props.workflow || waitingEvidence.value ? 'pending' : 'complete') as StepStatus,
    },
    {
      no: '08', title: '人工复核与多分支', tech: 'interrupt() + conditional_edges', detail: '批准 / 重研 / 补证 / 终止',
      status: (!props.workflow || waitingEvidence.value ? 'pending' : waitingReview.value ? 'waiting' : 'complete') as StepStatus,
    },
    {
      no: '09', title: '恢复、循环或归档', tech: 'Command(resume)', detail: '重新研判或保存最终结果',
      status: (!terminal.value ? 'pending' : props.workflow?.status === 'COMPLETED' ? 'complete' : 'rejected') as StepStatus,
    },
])
</script>

<template>
  <section class="architecture-board panel">
    <div class="section-heading board-heading">
      <div>
        <span class="eyebrow">SYSTEM EXECUTION MAP / 系统执行全景</span>
        <h2>海关案件最小研判链路</h2>
        <p>按真实请求顺序展示文件存储、数据持久化、标准化、规则研判与人工复核。</p>
      </div>
      <span v-if="workflow" class="thread-label" :title="workflow.thread_id">
        THREAD {{ workflow.thread_id.slice(0, 8) }}
      </span>
    </div>

    <div class="flow-lane">
      <div class="lane-label"><b>应用、数据与证据处理</b><span>APPLICATION / DATA / EVIDENCE</span></div>
      <div class="detailed-flow access-flow">
        <template v-for="(step, index) in accessSteps" :key="step.no">
          <article class="flow-step" :class="`step-${step.status}`">
            <div class="flow-step-head"><span>{{ step.no }}</span><em><i />{{ statusLabel[step.status] }}</em></div>
            <strong>{{ step.title }}</strong><b>{{ step.tech }}</b><small>{{ step.detail }}</small>
          </article>
          <div v-if="index < accessSteps.length - 1" class="flow-arrow">→</div>
        </template>
      </div>
    </div>

    <div class="lane-turn"><span>传入持久化 StateGraph</span><i>↓</i></div>

    <div class="flow-lane graph-lane">
      <div class="lane-label"><b>LangGraph 研判运行时</b><span>STATE GRAPH / CHECKPOINT</span></div>
      <div class="detailed-flow graph-flow">
        <template v-for="(step, index) in graphSteps" :key="step.no">
          <article class="flow-step" :class="`step-${step.status}`">
            <div class="flow-step-head"><span>{{ step.no }}</span><em><i />{{ statusLabel[step.status] }}</em></div>
            <strong>{{ step.title }}</strong><b>{{ step.tech }}</b><small>{{ step.detail }}</small>
          </article>
          <div v-if="index < graphSteps.length - 1" class="flow-arrow">→</div>
        </template>
      </div>
    </div>

    <div class="infra-grid">
      <article class="infra-card active-resource">
        <div class="infra-icon">PG</div>
        <div><span>业务状态与恢复依据</span><strong>PostgreSQL</strong><p>保存案件元数据、处理任务、运行事件、复核意见、分析产物和 LangGraph checkpoint。</p></div>
      </article>
      <article class="infra-card side-channel" :class="connection">
        <div class="infra-icon">SSE</div>
        <div><span>{{ connection === 'live' ? '实时连接' : connection === 'connecting' ? '正在重连' : '等待流程启动' }}</span><strong>状态快照通道</strong><p>后端读取 checkpoint，向浏览器推送 workflow_snapshot；断线不改变流程状态。</p></div>
      </article>
      <article class="infra-card active-resource">
        <div class="infra-icon">S3</div>
        <div><span>原始文件与标准化正文</span><strong>MinIO</strong><p>保存邮件、附件和解析后的完整 JSON；研判启动时按对象键读取正文。</p></div>
      </article>
    </div>

    <div class="truth-note">
      <b>当前实现边界</b>
      <span>已落地文件解析、金额和编号关联、风险规则、人工多分支与完整持久化；LLM/Agent 尚未接入。</span>
    </div>
  </section>
</template>
