from __future__ import annotations

import os

from langgraph.graph import END, StateGraph

from agents import db_agent, email_agent
from agents.state import AgentState

def build_resume_graph():
    graph = StateGraph(AgentState)
    # Start directly from tech stack analysis since we already have the job and match score
    graph.add_node("analyze_tech_stack", email_agent.analyze_tech_stack)
    graph.add_node("tailor_resume", email_agent.tailor_resume)
    graph.add_node("generate_email", email_agent.generate)
    graph.add_node("check_duplicate", db_agent.check_duplicate)
    graph.add_node("send_email", email_agent.send)
    graph.add_node("store_result", db_agent.store_result)

    graph.set_entry_point("analyze_tech_stack")
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
