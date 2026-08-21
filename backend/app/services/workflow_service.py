import uuid
from datetime import UTC, datetime
from typing import cast

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, StateSnapshot

from app.errors import ConflictError, NotFoundError
from app.graph.state import CaseState
from app.graph.workflow import CaseWorkflowGraph
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.workflow import (
    WorkflowResponse,
    WorkflowResume,
    WorkflowStart,
    WorkflowStateResponse,
)


class WorkflowService:
    def __init__(
        self,
        case_repository: CaseRepository,
        evidence_repository: EvidenceRepository,
        graph: CaseWorkflowGraph,
    ) -> None:
        self.case_repository = case_repository
        self.evidence_repository = evidence_repository
        self.graph = graph

    @staticmethod
    def _config(thread_id: uuid.UUID) -> RunnableConfig:
        return {"configurable": {"thread_id": str(thread_id)}}

    async def start(self, case_id: uuid.UUID, data: WorkflowStart) -> WorkflowResponse:
        case = await self.case_repository.get(case_id)
        if case is None:
            raise NotFoundError("CASE_NOT_FOUND", "Case not found")
        evidence = await self.evidence_repository.list(case_id)
        thread_id = uuid.uuid4()
        initial_state: CaseState = {
            "case_id": str(case.id),
            "case_name": case.name,
            "evidence_count": len(evidence),
            "analysis_scope": data.analysis_scope,
            "evidence_documents": [],
            "evidence_processing": {},
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
        config = self._config(thread_id)
        await self.graph.ainvoke(initial_state, config=config, durability="sync")
        return self._to_response(thread_id, await self.graph.aget_state(config))

    async def get(self, thread_id: uuid.UUID) -> WorkflowResponse:
        snapshot = await self.graph.aget_state(self._config(thread_id))
        if not snapshot.values:
            raise NotFoundError("WORKFLOW_NOT_FOUND", "Workflow thread not found")
        return self._to_response(thread_id, snapshot)

    async def resume(self, thread_id: uuid.UUID, data: WorkflowResume) -> WorkflowResponse:
        config = self._config(thread_id)
        snapshot = await self.graph.aget_state(config)
        if not snapshot.values:
            raise NotFoundError("WORKFLOW_NOT_FOUND", "Workflow thread not found")
        if not snapshot.interrupts:
            raise ConflictError("WORKFLOW_NOT_WAITING", "Workflow is not waiting for review")
        interrupt_value = snapshot.interrupts[0].value
        interrupt_type = interrupt_value.get("type") if isinstance(interrupt_value, dict) else None
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
        payload: dict[str, object] = {
            "action": decision,
            "comment": data.comment,
            "reviewer": data.reviewer,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        if decision == "EVIDENCE_READY":
            state = cast(CaseState, snapshot.values)
            evidence = await self.evidence_repository.list(uuid.UUID(state["case_id"]))
            payload["evidence_count"] = len(evidence)
        await self.graph.ainvoke(
            Command(resume=payload),
            config=config,
            durability="sync",
        )
        return self._to_response(thread_id, await self.graph.aget_state(config))

    @staticmethod
    def _to_response(thread_id: uuid.UUID, snapshot: StateSnapshot) -> WorkflowResponse:
        state = cast(CaseState, snapshot.values)
        interrupt_payload: dict[str, object] | None = None
        if snapshot.interrupts:
            value = snapshot.interrupts[0].value
            if isinstance(value, dict):
                interrupt_payload = cast(dict[str, object], value)
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
        )
