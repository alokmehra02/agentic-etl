from __future__ import annotations

import uuid
from typing import Literal

from langgraph.graph import END, StateGraph

from app.agents.nodes.core import engineer_node, ingestion_node, profiler_node
from app.agents.nodes.executor import executor_node, human_review_node, validator_node
from app.agents.state import AgentETLState
from app.config import get_settings
from app.database import session_scope


def _route_after_executor(state: AgentETLState) -> Literal["engineer", "validator"]:
    if state.get("last_error"):
        if state.get("retry_count", 0) >= state.get("max_retries", 3):
            return "validator"
        return "engineer"
    return "validator"


def _route_after_human_review(state: AgentETLState) -> Literal["complete", "await"]:
    if state.get("human_approval") is True:
        return "complete"
    if state.get("human_approval") is False:
        return "complete"
    return "await"


def build_etl_graph():
    settings = get_settings()
    graph = StateGraph(AgentETLState)

    def wrap(node_fn):
        def runner(state: AgentETLState):
            with session_scope() as db:
                result = node_fn(state, db)
            return result

        return runner

    graph.add_node("ingestion", wrap(ingestion_node))
    graph.add_node("profiler", wrap(profiler_node))
    graph.add_node("engineer", wrap(engineer_node))
    graph.add_node("executor", wrap(executor_node))
    graph.add_node("validator", wrap(validator_node))
    graph.add_node("human_review", wrap(human_review_node))

    graph.set_entry_point("ingestion")
    graph.add_edge("ingestion", "profiler")
    graph.add_edge("profiler", "engineer")
    graph.add_edge("engineer", "executor")
    graph.add_conditional_edges("executor", _route_after_executor, {"engineer": "engineer", "validator": "validator"})
    graph.add_edge("validator", "human_review")
    graph.add_conditional_edges(
        "human_review",
        _route_after_human_review,
        {"complete": END, "await": END},
    )

    return graph.compile()


def run_etl_pipeline(
    job_id: str,
    source_path: str,
    source_type: Literal["data_export", "sample_json"] = "data_export",
    thread_id: str | None = None,
    human_approval: bool | None = None,
    simulate_failure: bool = False,
) -> AgentETLState:
    settings = get_settings()
    thread_id = thread_id or str(uuid.uuid4())

    initial_state: AgentETLState = {
        "job_id": job_id,
        "thread_id": thread_id,
        "source_type": source_type,
        "source_path": source_path,
        "parsed_summary": {},
        "schema_profile": {},
        "transform_plan": {},
        "bronze_count": 0,
        "silver_count": 0,
        "gold_profile_id": None,
        "quality_score": 0.0,
        "retry_count": 0,
        "max_retries": settings.max_executor_retries,
        "last_error": None,
        "human_approval": human_approval,
        "logs": [],
        "current_step": "pending",
    }
    if simulate_failure:
        initial_state["simulate_failure"] = True  # type: ignore[typeddict-unknown-key]

    app = build_etl_graph()
    return app.invoke(initial_state)
