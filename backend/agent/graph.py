"""
LangGraph wiring for the Prior Authorization Appeal Agent.

Graph shape:
  denial_reader
       ↓
  policy_retriever          ← must run before evidence_retriever (sequential dep)
       ↓
  evidence_retriever
       ↓
  contradiction_finder
       ↓ (conditional)
  appeal_drafter   OR   escalation_node
       ↓
  quality_checker          ← loops back to appeal_drafter if quality < 0.70
       ↓ (conditional)
      END
"""

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    denial_reader,
    admin_error_checker,
    policy_retriever,
    evidence_retriever,
    contradiction_finder,
    appeal_drafter,
    escalation_node,
    quality_checker,
)
from config import settings


def route_after_denial_reader(state: AgentState) -> str:
    """Skip admin_error_checker when the user has already acknowledged the error."""
    if state.get("skip_admin_check", False):
        return "policy_retriever"
    return "admin_error_checker"


def route_after_admin_check(state: AgentState) -> str:
    if state.get("admin_error", False):
        return "admin_error"
    return "clinical"


def route_after_contradiction_finder(state: AgentState) -> str:
    score = state.get("confidence_score", 0.0)
    if score >= settings.confidence_threshold_high:
        return "appeal_drafter"
    elif score >= settings.confidence_threshold_low:
        # Partial draft — same node, state carries lower confidence signal
        return "appeal_drafter"
    else:
        return "escalation_node"


def route_after_quality_check(state: AgentState) -> str:
    """
    Loop back to appeal_drafter if quality is insufficient.
    Max 2 loops to prevent infinite revision — after that, return what we have.
    The quality_issues from this node are injected into appeal_drafter's prompt.
    """
    quality_score = state.get("quality_score", 1.0)
    loop_count = state.get("quality_loop_count", 1)

    if quality_score >= settings.quality_threshold or loop_count >= settings.max_quality_loops:
        return "done"
    return "revise"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("denial_reader", denial_reader)
    graph.add_node("admin_error_checker", admin_error_checker)
    graph.add_node("policy_retriever", policy_retriever)
    graph.add_node("evidence_retriever", evidence_retriever)
    graph.add_node("contradiction_finder", contradiction_finder)
    graph.add_node("appeal_drafter", appeal_drafter)
    graph.add_node("escalation_node", escalation_node)
    graph.add_node("quality_checker", quality_checker)

    # Entry point
    graph.set_entry_point("denial_reader")

    # Route after denial_reader: skip admin check if user requested it
    graph.add_conditional_edges(
        "denial_reader",
        route_after_denial_reader,
        {
            "admin_error_checker": "admin_error_checker",
            "policy_retriever": "policy_retriever",
        },
    )
    graph.add_conditional_edges(
        "admin_error_checker",
        route_after_admin_check,
        {
            "admin_error": END,
            "clinical": "policy_retriever",
        },
    )
    graph.add_edge("policy_retriever", "evidence_retriever")
    graph.add_edge("evidence_retriever", "contradiction_finder")

    # Conditional routing after contradiction analysis
    graph.add_conditional_edges(
        "contradiction_finder",
        route_after_contradiction_finder,
        {
            "appeal_drafter": "appeal_drafter",
            "escalation_node": "escalation_node",
        },
    )

    # Quality check loop
    graph.add_edge("appeal_drafter", "quality_checker")
    graph.add_conditional_edges(
        "quality_checker",
        route_after_quality_check,
        {
            "done": END,
            "revise": "appeal_drafter",
        },
    )

    # Escalation goes straight to END
    graph.add_edge("escalation_node", END)

    return graph.compile()


# Singleton compiled graph
appeal_graph = build_graph()
