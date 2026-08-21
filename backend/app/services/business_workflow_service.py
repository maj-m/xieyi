"""研判工作流业务协调层：连接 LangGraph 与业务持久化表，负责启动、暂停、恢复、重试和取消。"""

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi.encoders import jsonable_encoder
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, StateSnapshot
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import (
    EvidenceProcessingStatus,
    NormalizedDocumentStatus,
    ReviewTaskStatus,
    WorkflowEventType,
    WorkflowRunStatus,
)
from app.errors import ConflictError, NotFoundError
from app.graph.state import CaseState, EvidenceDocument
from app.graph.workflow import CaseWorkflowGraph
from app.models.evidence import Evidence
from app.models.evidence_processing import EvidenceProcessingJob, NormalizedDocument
from app.models.workflow import WorkflowEvent, WorkflowRun
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_processing_repository import EvidenceProcessingRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.workflow import (
    AnalysisArtifactResponse,
    ReviewTaskResponse,
    WorkflowCancel,
    WorkflowEventResponse,
    WorkflowResponse,
    WorkflowResume,
    WorkflowRetry,
    WorkflowRunResponse,
    WorkflowStart,
    WorkflowStateResponse,
    WorkflowTimelineResponse,
)
from app.storage.base import ObjectStorage

ACTIVE_RUN_STATUSES = {
    WorkflowRunStatus.CREATED,
    WorkflowRunStatus.RUNNING,
    WorkflowRunStatus.WAITING_REVIEW,
    WorkflowRunStatus.WAITING_EVIDENCE,
}


class BusinessWorkflowService:
    def __init__(
        self,
        session: AsyncSession,
        case_repository: CaseRepository,
        evidence_repository: EvidenceRepository,
        evidence_processing_repository: EvidenceProcessingRepository,
        workflow_repository: WorkflowRepository,
        storage: ObjectStorage,
        graph: CaseWorkflowGraph,
    ) -> None:
        self.session = session
        self.case_repository = case_repository
        self.evidence_repository = evidence_repository
        self.evidence_processing_repository = evidence_processing_repository
        self.workflow_repository = workflow_repository
        self.storage = storage
        self.graph = graph

    @staticmethod
    def _config(thread_id: uuid.UUID) -> RunnableConfig:
        return {"configurable": {"thread_id": str(thread_id)}}

    async def start(self, case_id: uuid.UUID, data: WorkflowStart) -> WorkflowResponse:
        case = await self.case_repository.get(case_id)
        if case is None:
            raise NotFoundError("CASE_NOT_FOUND", "Case not found")
        if data.idempotency_key:
            existing = await self.workflow_repository.get_run_by_idempotency(
                case_id, data.idempotency_key
            )
            if existing is not None:
                return await self.get(existing.thread_id)

        evidence, evidence_documents, evidence_processing = await self._evidence_context(case_id)
        if data.analysis_scope == "customs_risk_analysis":
            blocked = sum(
                evidence_processing.get(name, 0)
                for name in ("pending", "failed", "blocked", "not_queued")
            )
            failed_or_unsupported = evidence_processing.get("failed", 0) + evidence_processing.get(
                "blocked", 0
            )
            if evidence_processing.get("ready", 0) == 0 or blocked:
                raise ConflictError(
                    "EVIDENCE_NOT_READY",
                    "证据尚未全部标准化，不能启动研判："
                    f"已就绪 {evidence_processing.get('ready', 0)}，"
                    f"处理中 {evidence_processing.get('pending', 0)}，"
                    f"失败/不支持 {failed_or_unsupported}，"
                    f"未入队 {evidence_processing.get('not_queued', 0)}。",
                )
        now = datetime.now(UTC)
        thread_id = uuid.uuid4()
        run = WorkflowRun(
            thread_id=thread_id,
            case_id=case.id,
            analysis_scope=data.analysis_scope,
            status=WorkflowRunStatus.CREATED,
            current_node="load_normalized_evidence",
            review_round=1,
            attempt_count=1,
            max_attempts=data.max_attempts,
            idempotency_key=data.idempotency_key,
            timeout_at=(
                now + timedelta(seconds=data.timeout_seconds) if data.timeout_seconds else None
            ),
            heartbeat_at=now,
        )
        await self.workflow_repository.create_run(run)
        await self.workflow_repository.append_event(
            run,
            WorkflowEventType.WORKFLOW_STARTED,
            payload={
                "analysis_scope": data.analysis_scope,
                "evidence_count": len(evidence),
                "idempotency_key": data.idempotency_key or "",
            },
        )
        await self.session.commit()

        initial_state: CaseState = {
            "case_id": str(case.id),
            "case_name": case.name,
            "evidence_count": len(evidence),
            "analysis_scope": data.analysis_scope,
            "evidence_documents": evidence_documents,
            "evidence_processing": evidence_processing,
            "customs_analysis": None,
            "status": "PREPARING",
            "summary": "",
            "review_approved": None,
            "review_decision": None,
            "review_comment": None,
            "reviewer": None,
            "reviewed_at": None,
            "review_round": 1,
            "max_review_rounds": 3,
            "review_history": [],
            "result": None,
        }
        await self._execute_graph(run, initial_state)
        snapshot = await self.graph.aget_state(self._config(thread_id))
        await self._synchronize_snapshot(run, snapshot)
        return await self._to_response(thread_id, snapshot, run)

    async def get(self, thread_id: uuid.UUID) -> WorkflowResponse:
        snapshot = await self.graph.aget_state(self._config(thread_id))
        if not snapshot.values:
            raise NotFoundError("WORKFLOW_NOT_FOUND", "Workflow thread not found")
        run = await self.workflow_repository.get_run(thread_id)
        if run is not None:
            await self._expire_if_needed(run)
        return await self._to_response(thread_id, snapshot, run)

    async def resume(self, thread_id: uuid.UUID, data: WorkflowResume) -> WorkflowResponse:
        config = self._config(thread_id)
        snapshot = await self.graph.aget_state(config)
        if not snapshot.values:
            raise NotFoundError("WORKFLOW_NOT_FOUND", "Workflow thread not found")
        state = cast(CaseState, snapshot.values)
        run = await self.workflow_repository.get_run(thread_id, for_update=True)
        if run is None:
            run = await self._backfill_run(thread_id, state)
        await self._expire_if_needed(run)
        if data.idempotency_key:
            duplicate = await self.workflow_repository.get_review_by_idempotency(
                run.id, data.idempotency_key
            )
            if duplicate is not None:
                return await self._to_response(thread_id, snapshot, run)
        if run.status not in {
            WorkflowRunStatus.WAITING_REVIEW,
            WorkflowRunStatus.WAITING_EVIDENCE,
        }:
            raise ConflictError(
                "WORKFLOW_NOT_WAITING", f"Workflow run is {run.status} and cannot be resumed"
            )
        if not snapshot.interrupts:
            raise ConflictError("WORKFLOW_NOT_WAITING", "Workflow is not waiting for review")

        interrupt_value = snapshot.interrupts[0].value
        interrupt_payload = interrupt_value if isinstance(interrupt_value, dict) else {}
        interrupt_type = str(interrupt_payload.get("type", "UNKNOWN"))
        decision = data.resolved_decision
        allowed = (
            {"APPROVE", "REANALYZE", "REQUEST_EVIDENCE", "CANCEL"}
            if interrupt_type == "CASE_ANALYSIS_REVIEW"
            else {"EVIDENCE_READY"}
        )
        if decision not in allowed:
            raise ConflictError(
                "INVALID_WORKFLOW_DECISION",
                f"Decision {decision} is not valid for {interrupt_type}",
            )

        review_round = state.get("review_round", 1)
        task = await self.workflow_repository.ensure_pending_review(
            run, review_round, interrupt_type
        )
        if task.status == ReviewTaskStatus.DECIDED:
            raise ConflictError("REVIEW_ALREADY_DECIDED", "This review task was already decided")
        decided_at = datetime.now(UTC)
        await self.workflow_repository.decide_review(
            task,
            decision=decision,
            reviewer=data.reviewer,
            comment=data.comment,
            idempotency_key=data.idempotency_key,
            decided_at=decided_at,
        )
        await self.workflow_repository.append_event(
            run,
            WorkflowEventType.REVIEW_DECIDED,
            node_name=str(snapshot.next[0]) if snapshot.next else None,
            payload={
                "decision": decision,
                "reviewer": data.reviewer or "",
                "comment": data.comment or "",
                "review_round": review_round,
                "review_task_id": str(task.id),
            },
        )
        self.workflow_repository.set_run_status(
            run,
            WorkflowRunStatus.RUNNING,
            current_node=str(snapshot.next[0]) if snapshot.next else None,
            now=decided_at,
        )
        await self.workflow_repository.append_event(
            run,
            WorkflowEventType.WORKFLOW_RESUMED,
            node_name=run.current_node,
            payload={"decision": decision},
        )
        await self.session.commit()

        payload: dict[str, object] = {
            "action": decision,
            "comment": data.comment,
            "reviewer": data.reviewer,
            "reviewed_at": decided_at.isoformat(),
        }
        if decision == "EVIDENCE_READY":
            evidence, documents, processing = await self._evidence_context(
                uuid.UUID(state["case_id"])
            )
            payload["evidence_count"] = len(evidence)
            payload["evidence_documents"] = documents
            payload["evidence_processing"] = processing
        await self._execute_graph(run, Command(resume=payload))
        latest = await self.graph.aget_state(config)
        await self._synchronize_snapshot(run, latest)
        return await self._to_response(thread_id, latest, run)

    async def retry(self, thread_id: uuid.UUID, data: WorkflowRetry) -> WorkflowResponse:
        run = await self.workflow_repository.get_run(thread_id, for_update=True)
        if run is None:
            raise NotFoundError("WORKFLOW_RUN_NOT_FOUND", "Workflow business run not found")
        if run.status != WorkflowRunStatus.FAILED:
            raise ConflictError("WORKFLOW_NOT_FAILED", "Only failed workflows can be retried")
        if run.attempt_count >= run.max_attempts:
            raise ConflictError("WORKFLOW_RETRY_EXHAUSTED", "Workflow retry limit exhausted")
        snapshot = await self.graph.aget_state(self._config(thread_id))
        if not snapshot.values:
            raise ConflictError("WORKFLOW_NO_CHECKPOINT", "No checkpoint is available for retry")

        run.attempt_count += 1
        run.last_error_code = None
        run.last_error_message = None
        self.workflow_repository.set_run_status(
            run,
            WorkflowRunStatus.RUNNING,
            current_node=str(snapshot.next[0]) if snapshot.next else None,
            now=datetime.now(UTC),
        )
        await self.workflow_repository.append_event(
            run,
            WorkflowEventType.WORKFLOW_RETRYING,
            node_name=run.current_node,
            payload={"requested_by": data.requested_by or ""},
        )
        await self.session.commit()
        retry_input: Command[object] | None = None
        if snapshot.interrupts:
            state = cast(CaseState, snapshot.values)
            interrupt_value = snapshot.interrupts[0].value
            interrupt_payload = interrupt_value if isinstance(interrupt_value, dict) else {}
            interrupt_type = str(interrupt_payload.get("type", "UNKNOWN"))
            decided_task = await self.workflow_repository.get_review(
                run.id, state.get("review_round", 1), interrupt_type
            )
            if decided_task is not None and decided_task.status == ReviewTaskStatus.DECIDED:
                replay_payload: dict[str, object] = {
                    "action": decided_task.decision or "",
                    "comment": decided_task.comment,
                    "reviewer": decided_task.reviewer,
                    "reviewed_at": (
                        decided_task.decided_at.isoformat()
                        if decided_task.decided_at
                        else datetime.now(UTC).isoformat()
                    ),
                }
                if decided_task.decision == "EVIDENCE_READY":
                    evidence, documents, processing = await self._evidence_context(run.case_id)
                    replay_payload["evidence_count"] = len(evidence)
                    replay_payload["evidence_documents"] = documents
                    replay_payload["evidence_processing"] = processing
                retry_input = Command(resume=replay_payload)
        await self._execute_graph(run, retry_input)
        latest = await self.graph.aget_state(self._config(thread_id))
        await self._synchronize_snapshot(run, latest)
        return await self._to_response(thread_id, latest, run)

    async def cancel(self, thread_id: uuid.UUID, data: WorkflowCancel) -> WorkflowTimelineResponse:
        run = await self.workflow_repository.get_run(thread_id, for_update=True)
        if run is None:
            raise NotFoundError("WORKFLOW_RUN_NOT_FOUND", "Workflow business run not found")
        if run.status not in ACTIVE_RUN_STATUSES:
            raise ConflictError("WORKFLOW_NOT_CANCELLABLE", f"Workflow run is {run.status}")
        now = datetime.now(UTC)
        self.workflow_repository.set_run_status(
            run, WorkflowRunStatus.CANCELLED, current_node=None, now=now
        )
        run.completed_at = now
        reviews = await self.workflow_repository.list_reviews(run.id)
        for task in reviews:
            if task.status == ReviewTaskStatus.PENDING:
                task.status = ReviewTaskStatus.CANCELLED
        await self.workflow_repository.append_event(
            run,
            WorkflowEventType.WORKFLOW_CANCELLED,
            payload={
                "requested_by": data.requested_by or "",
                "reason": data.reason or "",
            },
        )
        await self.session.commit()
        return await self.timeline(thread_id)

    async def timeline(self, thread_id: uuid.UUID) -> WorkflowTimelineResponse:
        run = await self.workflow_repository.get_run(thread_id)
        if run is None:
            raise NotFoundError("WORKFLOW_RUN_NOT_FOUND", "Workflow business run not found")
        await self._expire_if_needed(run)
        await self.session.refresh(run)
        events = await self.workflow_repository.list_events(run.id)
        reviews = await self.workflow_repository.list_reviews(run.id)
        artifacts = await self.workflow_repository.list_artifacts(run.id)
        return WorkflowTimelineResponse(
            run=WorkflowRunResponse.model_validate(run),
            events=[WorkflowEventResponse.model_validate(item) for item in events],
            reviews=[ReviewTaskResponse.model_validate(item) for item in reviews],
            artifacts=[AnalysisArtifactResponse.model_validate(item) for item in artifacts],
        )

    async def list_events(
        self, thread_id: uuid.UUID, after_sequence: int = 0
    ) -> list[WorkflowEvent]:
        run = await self.workflow_repository.get_run(thread_id)
        if run is None:
            return []
        return await self.workflow_repository.list_events(run.id, after_sequence=after_sequence)

    async def _execute_graph(
        self, run: WorkflowRun, graph_input: CaseState | Command[object] | None
    ) -> None:
        self.workflow_repository.set_run_status(
            run,
            WorkflowRunStatus.RUNNING,
            current_node=run.current_node,
            now=datetime.now(UTC),
        )
        await self.session.commit()
        try:
            async for raw_chunk in self.graph.astream(
                graph_input,
                config=self._config(run.thread_id),
                stream_mode="tasks",
                durability="sync",
            ):
                task = cast(Mapping[str, object], raw_chunk)
                node_name = str(task.get("name", "unknown"))
                run.current_node = node_name
                run.heartbeat_at = datetime.now(UTC)
                if "result" not in task:
                    await self.workflow_repository.append_event(
                        run,
                        WorkflowEventType.NODE_STARTED,
                        node_name=node_name,
                        payload={"task_id": str(task.get("id", ""))},
                    )
                elif not task.get("interrupts"):
                    payload = self._json_payload(task.get("result", {}))
                    run.heartbeat_at = datetime.now(UTC)
                    await self.workflow_repository.append_event(
                        run,
                        WorkflowEventType.NODE_COMPLETED,
                        node_name=node_name,
                        payload=payload,
                    )
                    await self._record_artifact(run, node_name, payload)
                await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            failed_run = await self.workflow_repository.get_run(run.thread_id, for_update=True)
            if failed_run is not None:
                failed_run.last_error_code = type(exc).__name__
                failed_run.last_error_message = str(exc)[:2000]
                self.workflow_repository.set_run_status(
                    failed_run,
                    WorkflowRunStatus.FAILED,
                    current_node=run.current_node,
                    now=datetime.now(UTC),
                )
                await self.workflow_repository.append_event(
                    failed_run,
                    WorkflowEventType.WORKFLOW_FAILED,
                    node_name=failed_run.current_node,
                    error_code=failed_run.last_error_code,
                    error_message=failed_run.last_error_message,
                )
                await self.session.commit()
            raise

    async def _record_artifact(
        self, run: WorkflowRun, node_name: str, payload: dict[str, object]
    ) -> None:
        artifact_type: str | None = None
        content: dict[str, object] = {}
        if isinstance(payload.get("customs_analysis"), dict):
            artifact_type = "CUSTOMS_RISK_ANALYSIS"
            content = cast(dict[str, object], payload["customs_analysis"])
        elif isinstance(payload.get("summary"), str):
            artifact_type = "CASE_SUMMARY"
            content = {
                "summary": payload["summary"],
                "review_round": payload.get("review_round", run.review_round),
            }
        elif isinstance(payload.get("result"), str):
            artifact_type = "WORKFLOW_RESULT"
            content = {"result": payload["result"], "status": payload.get("status", "")}
        if artifact_type is None:
            return
        artifact = await self.workflow_repository.create_artifact(
            run,
            node_name=node_name,
            artifact_type=artifact_type,
            content=content,
        )
        await self.workflow_repository.append_event(
            run,
            WorkflowEventType.ARTIFACT_CREATED,
            node_name=node_name,
            payload={"artifact_id": str(artifact.id), "artifact_type": artifact_type},
        )

    async def _synchronize_snapshot(self, run: WorkflowRun, snapshot: StateSnapshot) -> None:
        state = cast(CaseState, snapshot.values)
        graph_status = state["status"]
        now = datetime.now(UTC)
        run.review_round = state.get("review_round", 1)
        run.current_node = str(snapshot.next[0]) if snapshot.next else None
        previous_status = run.status

        if graph_status == "WAITING_REVIEW":
            status = WorkflowRunStatus.WAITING_REVIEW
        elif graph_status == "WAITING_EVIDENCE":
            status = WorkflowRunStatus.WAITING_EVIDENCE
        elif graph_status == "COMPLETED":
            status = WorkflowRunStatus.COMPLETED
        elif graph_status in {"CANCELLED", "REJECTED"}:
            status = WorkflowRunStatus.CANCELLED
        else:
            status = WorkflowRunStatus.RUNNING
        self.workflow_repository.set_run_status(run, status, current_node=run.current_node, now=now)

        if status in {WorkflowRunStatus.WAITING_REVIEW, WorkflowRunStatus.WAITING_EVIDENCE}:
            interrupt_payload: dict[str, object] = {}
            if snapshot.interrupts and isinstance(snapshot.interrupts[0].value, dict):
                interrupt_payload = cast(dict[str, object], snapshot.interrupts[0].value)
            interrupt_type = str(interrupt_payload.get("type", "UNKNOWN"))
            existing = await self.workflow_repository.get_review(
                run.id, run.review_round, interrupt_type
            )
            if existing is None:
                task = await self.workflow_repository.ensure_pending_review(
                    run, run.review_round, interrupt_type
                )
                await self.workflow_repository.append_event(
                    run,
                    WorkflowEventType.WORKFLOW_PAUSED,
                    node_name=run.current_node,
                    payload={
                        "interrupt_type": interrupt_type,
                        "review_round": run.review_round,
                        "review_task_id": str(task.id),
                    },
                )
        elif status == WorkflowRunStatus.COMPLETED:
            run.completed_at = now
            if previous_status != status:
                await self.workflow_repository.append_event(
                    run,
                    WorkflowEventType.WORKFLOW_COMPLETED,
                    payload={"result": state["result"] or ""},
                )
        elif status == WorkflowRunStatus.CANCELLED:
            run.completed_at = now
            if previous_status != status:
                await self.workflow_repository.append_event(
                    run,
                    WorkflowEventType.WORKFLOW_CANCELLED,
                    payload={"result": state["result"] or ""},
                )
        await self.session.commit()

    async def _expire_if_needed(self, run: WorkflowRun) -> None:
        now = datetime.now(UTC)
        if run.status in ACTIVE_RUN_STATUSES and run.timeout_at and run.timeout_at <= now:
            self.workflow_repository.set_run_status(
                run, WorkflowRunStatus.TIMED_OUT, current_node=run.current_node, now=now
            )
            run.completed_at = now
            await self.workflow_repository.append_event(
                run,
                WorkflowEventType.WORKFLOW_TIMED_OUT,
                node_name=run.current_node,
                payload={"timeout_at": run.timeout_at.isoformat()},
            )
            await self.session.commit()

    async def _backfill_run(self, thread_id: uuid.UUID, state: CaseState) -> WorkflowRun:
        graph_status = state["status"]
        status = (
            WorkflowRunStatus.WAITING_EVIDENCE
            if graph_status == "WAITING_EVIDENCE"
            else WorkflowRunStatus.WAITING_REVIEW
        )
        run = WorkflowRun(
            thread_id=thread_id,
            case_id=uuid.UUID(state["case_id"]),
            analysis_scope=state["analysis_scope"],
            status=status,
            current_node="human_review",
            review_round=state.get("review_round", 1),
            attempt_count=1,
            max_attempts=3,
            heartbeat_at=datetime.now(UTC),
        )
        await self.workflow_repository.create_run(run)
        await self.workflow_repository.append_event(
            run,
            WorkflowEventType.WORKFLOW_STARTED,
            payload={"backfilled_from_checkpoint": True},
        )
        await self.session.commit()
        return run

    async def _to_response(
        self, thread_id: uuid.UUID, snapshot: StateSnapshot, run: WorkflowRun | None
    ) -> WorkflowResponse:
        state = cast(CaseState, snapshot.values)
        interrupt_payload: dict[str, object] | None = None
        if snapshot.interrupts and isinstance(snapshot.interrupts[0].value, dict):
            interrupt_payload = cast(dict[str, object], snapshot.interrupts[0].value)
        run_response: WorkflowRunResponse | None = None
        if run is not None:
            await self.session.refresh(run)
            run_response = WorkflowRunResponse.model_validate(run)
        return WorkflowResponse(
            thread_id=thread_id,
            case_id=uuid.UUID(state["case_id"]),
            status=state["status"],
            next_nodes=list(snapshot.next),
            interrupt=interrupt_payload,
            state=WorkflowStateResponse(
                case_name=state["case_name"],
                evidence_count=state["evidence_count"],
                analysis_scope=state["analysis_scope"],
                evidence_documents=state.get("evidence_documents", []),
                evidence_processing=state.get("evidence_processing", {}),
                customs_analysis=state.get("customs_analysis"),
                summary=state["summary"],
                review_approved=state["review_approved"],
                review_decision=state.get("review_decision"),
                review_comment=state["review_comment"],
                reviewer=state.get("reviewer"),
                reviewed_at=state.get("reviewed_at"),
                review_round=state.get("review_round", 1),
                max_review_rounds=state.get("max_review_rounds", 3),
                review_history=state.get("review_history", []),
                result=state["result"],
            ),
            run=run_response,
        )

    async def _evidence_context(
        self, case_id: uuid.UUID
    ) -> tuple[list[Evidence], list[EvidenceDocument], dict[str, int]]:
        evidence = await self.evidence_repository.list(case_id)
        jobs = await self.evidence_processing_repository.list_jobs(case_id)
        normalized = await self.evidence_processing_repository.list_documents(case_id)
        latest_jobs: dict[uuid.UUID, EvidenceProcessingJob] = {}
        for job_item in jobs:
            latest_jobs.setdefault(job_item.evidence_id, job_item)
        latest_documents: dict[uuid.UUID, NormalizedDocument] = {}
        for document_item in normalized:
            latest_documents.setdefault(document_item.evidence_id, document_item)
        counts = {"ready": 0, "pending": 0, "failed": 0, "blocked": 0, "not_queued": 0}
        documents: list[EvidenceDocument] = []
        total_characters = 0
        for evidence_item in evidence:
            job = latest_jobs.get(evidence_item.id)
            document = latest_documents.get(evidence_item.id)
            if job is None:
                counts["not_queued"] += 1
                continue
            if job.status in {
                EvidenceProcessingStatus.QUEUED,
                EvidenceProcessingStatus.PROCESSING,
            }:
                counts["pending"] += 1
                continue
            if job.status == EvidenceProcessingStatus.FAILED:
                counts["failed"] += 1
                continue
            if job.status in {
                EvidenceProcessingStatus.UNSUPPORTED,
                EvidenceProcessingStatus.OCR_REQUIRED,
            }:
                counts["blocked"] += 1
                continue
            if (
                document is None
                or document.status != NormalizedDocumentStatus.READY
                or not document.content_object_key
            ):
                counts["failed"] += 1
                continue
            payload = json.loads((await self.storage.get(document.content_object_key)).decode())
            document_payload = payload.get("document", {})
            metadata = payload.get("metadata", {})
            text = str(document_payload.get("text", ""))
            # ponytail: checkpoint text is capped; move facts-only extraction before LangGraph
            # if real cases regularly exceed this ceiling.
            remaining = max(0, 500_000 - total_characters)
            text = text[: min(100_000, remaining)]
            total_characters += len(text)
            documents.append(
                {
                    "evidence_id": str(evidence_item.id),
                    "filename": evidence_item.original_filename,
                    "document_type": evidence_item.document_type.value,
                    "title": str(document_payload.get("title") or evidence_item.original_filename),
                    "text": text,
                    "metadata": metadata if isinstance(metadata, dict) else {},
                }
            )
            counts["ready"] += 1
        return evidence, documents, counts

    @staticmethod
    def _json_payload(value: object) -> dict[str, object]:
        encoded = jsonable_encoder(value)
        if isinstance(encoded, dict):
            return cast(dict[str, object], encoded)
        return {"output": cast(object, encoded)}
