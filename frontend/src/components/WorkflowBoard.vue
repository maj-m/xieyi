<script setup lang="ts">
import { computed } from 'vue'
import type { WorkflowSnapshot } from '../types'

type StepStatus = 'pending' | 'active' | 'waiting' | 'complete' | 'rejected'

const props = defineProps<{
  workflow: WorkflowSnapshot | null
  connection: 'offline' | 'connecting' | 'live'
}>()

const terminal = computed(
  () => props.workflow?.status === 'COMPLETED' || props.workflow?.status === 'REJECTED',
)

const statusLabel: Record<StepStatus, string> = {
  pending: '待执行',
  active: '当前入口',
  waiting: '暂停等待',
  complete: '已执行',
  rejected: '未通过',
}

const accessSteps = computed(() => [
  {
    no: '01', title: '选择案件', tech: 'Vue 3 Console', detail: 'GET /api/v1/cases',
    status: (props.workflow ? 'complete' : 'active') as StepStatus,
  },
  {
    no: '02', title: '接收启动请求', tech: 'FastAPI', detail: 'POST /cases/{id}/workflows',
    status: (props.workflow ? 'complete' : 'pending') as StepStatus,
  },
  {
    no: '03', title: '读取案件数据', tech: 'PostgreSQL', detail: '案件 + 证据元数据',
    status: (props.workflow ? 'complete' : 'pending') as StepStatus,
  },
  {
    no: '04', title: '组装初始状态', tech: 'CaseState', detail: 'case_id / scope / evidence_count',
    status: (props.workflow ? 'complete' : 'pending') as StepStatus,
  },
])

const graphSteps = computed(() => {
  const status = props.workflow?.status
  return [
    {
      no: '05', title: '案件准备节点', tech: 'prepare_case', detail: '生成当前最小研判摘要',
      status: (!status ? 'pending' : status === 'PREPARING' ? 'active' : 'complete') as StepStatus,
    },
    {
      no: '06', title: '写入 Checkpoint', tech: 'PostgreSQL Saver', detail: 'durability = sync',
      status: (status && status !== 'PREPARING' ? 'complete' : 'pending') as StepStatus,
    },
    {
      no: '07', title: '人工复核暂停', tech: 'interrupt()', detail: '保存 WAITING_REVIEW',
      status: (!status ? 'pending' : status === 'WAITING_REVIEW' ? 'waiting' : terminal.value ? 'complete' : 'pending') as StepStatus,
    },
    {
      no: '08', title: '携带决定恢复', tech: 'Command(resume)', detail: '批准或退回',
      status: (terminal.value ? 'complete' : 'pending') as StepStatus,
    },
    {
      no: '09', title: '完成并持久化', tech: 'finalize_case', detail: 'COMPLETED / REJECTED',
      status: (!terminal.value ? 'pending' : props.workflow?.status === 'REJECTED' ? 'rejected' : 'complete') as StepStatus,
    },
  ]
})
</script>

<template>
  <section class="architecture-board panel">
    <div class="section-heading board-heading">
      <div>
        <span class="eyebrow">SYSTEM EXECUTION MAP / 系统执行全景</span>
        <h2>最小案件研判链路</h2>
        <p>按一次真实请求的调用顺序展示应用层、数据层与 LangGraph 运行时。</p>
      </div>
      <span v-if="workflow" class="thread-label" :title="workflow.thread_id">
        THREAD {{ workflow.thread_id.slice(0, 8) }}
      </span>
    </div>

    <div class="flow-lane">
      <div class="lane-label"><b>应用与数据访问</b><span>APPLICATION / DATA ACCESS</span></div>
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

    <div class="lane-turn"><span>传入 StateGraph</span><i>↓</i></div>

    <div class="flow-lane graph-lane">
      <div class="lane-label"><b>LangGraph 运行时</b><span>STATE GRAPH / CHECKPOINT</span></div>
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
        <div><span>当前链路正在使用</span><strong>PostgreSQL</strong><p>案件/证据元数据、LangGraph checkpoint。服务重启后恢复以此为事实来源。</p></div>
      </article>
      <article class="infra-card side-channel" :class="connection">
        <div class="infra-icon">SSE</div>
        <div><span>{{ connection === 'live' ? '实时连接' : connection === 'connecting' ? '正在重连' : '等待流程启动' }}</span><strong>状态快照通道</strong><p>后端读取 checkpoint，向浏览器推送 workflow_snapshot；断线不改变流程状态。</p></div>
      </article>
      <article class="infra-card dormant-resource">
        <div class="infra-icon">S3</div>
        <div><span>存储已就绪 · 本链路尚未读取</span><strong>MinIO</strong><p>保存邮件与附件等文件正文；当前 prepare_case 只统计 PostgreSQL 中的证据元数据。</p></div>
      </article>
    </div>

    <div class="truth-note">
      <b>当前实现边界</b>
      <span>尚未接入文件解析、实体抽取、要素关联、LLM/Agent 与持久化失败事件；图中仅展示已经落地的真实调用。</span>
    </div>
  </section>
</template>
