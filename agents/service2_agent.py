import re
import urllib.request
from bs4 import BeautifulSoup
from typing import Optional, TypedDict, List
from langgraph.graph import END, StateGraph

from agents.state import AgentState, JobLead
from agents import email_agent, db_agent
from services import llm
from services.db import upsert_job, update_job_stage

class Service2State(AgentState):
    target_email: str
    target_domain: str
    company_name: str
    company_info: str

def extract_domain(state: Service2State) -> Service2State:
    email = state.get("target_email")
    if not email:
        state["errors"].append("No target email provided.")
        state["send_status"] = "failed"
        return state
        
    match = re.search(r"@([\w.-]+)", email)
    if not match:
        state["errors"].append(f"Could not extract domain from email: {email}")
        state["send_status"] = "failed"
        return state
        
    domain = match.group(1)
    state["target_domain"] = domain
    
    # Simple extraction of company name from domain (e.g. stripe.com -> Stripe)
    name = domain.split(".")[0].capitalize()
    state["company_name"] = name
    
    # Initialize current_job with mock data for downstream agents
    job_data = {
        "company": name,
        "title": "Software Engineer", # Generic title for cold outreach
        "location": "Remote",
        "url": f"https://{domain}",
        "jd_text": "", # Will be filled by profile_company
        "source": "service2",
        "recruiter_name": "Hiring Team",
        "recruiter_email": email
    }
    
    # Insert job immediately so we can track its stages in real-time
    job_id = upsert_job(job_data, None)
    job_data["id"] = job_id
    
    state["current_job"] = job_data
    state["recruiter_email"] = email
    
    update_job_stage(job_id, "Profiling Company")
    
    return state

def profile_company(state: Service2State) -> Service2State:
    if state.get("send_status") == "failed":
        return state
        
    domain = state.get("target_domain")
    
    # Try to scrape the homepage for info
    try:
        url = f"https://{domain}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
            soup = BeautifulSoup(html, 'html.parser')
            # Extract basic text
            text = ' '.join(soup.stripped_strings)[:2000] # First 2000 chars
            
            prompt = f"""Analyze this text from {domain}'s homepage.
What does the company do, and what is their likely tech stack?
Return a concise summary and list the tech stack.

Homepage Text:
{text}
"""
            analysis = llm.generate(prompt)
            state["company_info"] = analysis
            
            # Update the mock job with this info so downstream agents can use it
            if "current_job" in state and state["current_job"]:
                state["current_job"]["jd_text"] = analysis
                
    except Exception as e:
        state["errors"].append(f"Failed to scrape {domain}: {str(e)}")
        # Fallback if scrape fails: just use generic tech stack or LLM knowledge
        prompt = f"What does the company {state.get('company_name')} ({domain}) do, and what is their likely tech stack? If you don't know, guess standard web stack."
        analysis = llm.generate(prompt)
        state["company_info"] = analysis
        if "current_job" in state and state["current_job"]:
            state["current_job"]["jd_text"] = analysis
            
    return state

def build_service2_graph():
    graph = StateGraph(Service2State)
    graph.add_node("extract_domain", extract_domain)
    graph.add_node("profile_company", profile_company)
    
    # Reuse nodes from email_agent and db_agent
    graph.add_node("analyze_tech_stack", email_agent.analyze_tech_stack)
    graph.add_node("tailor_resume", email_agent.tailor_resume)
    graph.add_node("generate_email", email_agent.generate)
    graph.add_node("send_email", email_agent.send)
    graph.add_node("store_result", db_agent.store_result)
    
    graph.set_entry_point("extract_domain")
    
    graph.add_conditional_edges(
        "extract_domain",
        lambda s: "profile_company" if s.get("send_status") != "failed" else END
    )
    graph.add_edge("profile_company", "analyze_tech_stack")
    graph.add_edge("analyze_tech_stack", "tailor_resume")
    graph.add_edge("tailor_resume", "generate_email")
    graph.add_edge("generate_email", "send_email")
    graph.add_edge("send_email", "store_result")
    graph.add_edge("store_result", END)
    
    return graph.compile()
