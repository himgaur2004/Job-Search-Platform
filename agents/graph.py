from __future__ import annotations

import os

from langgraph.graph import END, StateGraph

from agents import db_agent, email_agent, recruiter_agent, resume_agent, search_agent
from agents.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("search_jobs", search_agent.run)
    graph.add_node("find_recruiter", recruiter_agent.run)
    graph.add_node("match_resume", resume_agent.run)
    graph.add_node("analyze_tech_stack", email_agent.analyze_tech_stack)
    graph.add_node("tailor_resume", email_agent.tailor_resume)
    graph.add_node("generate_email", email_agent.generate)
    graph.add_node("check_duplicate", db_agent.check_duplicate)
    graph.add_node("send_email", email_agent.send)
    graph.add_node("store_result", db_agent.store_result)

    graph.set_entry_point("search_jobs")
    graph.add_edge("search_jobs", "find_recruiter")
    graph.add_edge("find_recruiter", "match_resume")
    graph.add_conditional_edges(
        "match_resume",
        lambda s: "analyze_tech_stack"
        if (s.get("match_score") is not None and s["match_score"] >= float(os.getenv("MATCH_THRESHOLD", "0.70")) and s.get("recruiter_email"))
        else "store_result",
    )
    graph.add_edge("analyze_tech_stack", "tailor_resume")
    graph.add_edge("tailor_resume", "generate_email")
    graph.add_edge("generate_email", "check_duplicate")
    graph.add_conditional_edges(
        "check_duplicate",
        lambda s: "store_result" if s.get("already_sent") else "send_email",
    )
    graph.add_edge("send_email", "store_result")
    graph.add_edge("store_result", END)
    return graph.compile()
