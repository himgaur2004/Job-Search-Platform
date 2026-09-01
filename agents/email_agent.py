from __future__ import annotations

import os
import subprocess
from pathlib import Path

from agents.state import AgentState
from services import gmail, llm
from services.db import get_active_resume, get_active_template, update_job_stage


def analyze_tech_stack(state: AgentState) -> AgentState:
    job = state.get("current_job")
    if job and job.get("id"):
        update_job_stage(job["id"], "Analyzing Tech Stack")
    if not job or not job.get("jd_text"):
        state["tech_stack"] = ""
        return state

    prompt = f"""Extract the core technology stack and required skills from the following job description.
Return ONLY a concise, comma-separated list of the top 5-10 most important technologies/skills. Do not include introductory text.

Job Description:
{job.get("jd_text")}
"""
    state["tech_stack"] = llm.generate(prompt).strip()
    return state


def tailor_resume(state: AgentState) -> AgentState:
    job = state.get("current_job")
    if job and job.get("id"):
        update_job_stage(job["id"], "Generating Resume")
    if not job or not state.get("tech_stack"):
        return state
        
    active_resume = get_active_resume()
    if not active_resume:
        state["errors"].append("No active resume template found in DB.")
        state["send_status"] = "skipped"
        return state

    base_latex = active_resume["latex_content"]
    
    prompt = f"""You are an expert resume writer. I am giving you my base resume written in LaTeX.
Your task is to modify the LaTeX code to heavily emphasize the following tech stack and skills which are required for the job I am applying for.
You MUST output valid, compilable LaTeX code and absolutely nothing else. Do not use markdown code blocks, just raw LaTeX text.

Tech Stack to emphasize: {state["tech_stack"]}

Base LaTeX Resume:
{base_latex}
"""
    tailored_latex = llm.generate(prompt)
    if tailored_latex.startswith("```"):
        # Strip markdown formatting if the LLM adds it
        tailored_latex = "\n".join(tailored_latex.split("\n")[1:-1])

    state["latex_content"] = tailored_latex

    # Compile the PDF using tectonic
    pdf_path = f"resume_{job.get('id', 'out')}.pdf"
    tex_path = f"resume_{job.get('id', 'out')}.tex"
    
    with open(tex_path, "w") as f:
        f.write(tailored_latex)
        
    try:
        subprocess.run(["tectonic", tex_path], check=True, capture_output=True)
        state["pdf_path"] = pdf_path
    except subprocess.CalledProcessError as e:
        state["errors"].append(f"LaTeX compilation failed: {e.stderr.decode('utf-8', errors='ignore')}")
        state["send_status"] = "skipped"
        
    return state


def generate(state: AgentState) -> AgentState:
    if state.get("send_status") == "skipped":
        return state
        
    job = state.get("current_job")
    if job and job.get("id"):
        update_job_stage(job["id"], "Drafting Email")
    if not job:
        state["errors"].append("Missing current_job for generation.")
        state["send_status"] = "failed"
        return state
    if not state.get("recruiter_email"):
        state["send_status"] = "skipped"
        return state
    
    active_template = get_active_template()
    if not active_template:
        state["errors"].append("No active email template found in DB.")
        state["send_status"] = "skipped"
        return state
        
    # Replace simple variables in the body template to form the prompt
    prompt_body = active_template["body_template"]
    prompt_body = prompt_body.replace("{{company}}", job.get("company", "the company"))
    prompt_body = prompt_body.replace("{{recruiter_name}}", state.get("recruiter_name") or "Hiring Team")
    prompt_body = prompt_body.replace("{{jd_text}}", job.get("jd_text", ""))

    prompt = f"""You are drafting an outreach email to a recruiter. 
Use the following template as your strict structure and tone:

{prompt_body}

Output ONLY the final email body. No pleasantries like 'Here is the email'.
"""
    state["email_body"] = llm.generate(prompt)
    
    # Simple substitution for the subject line
    subject = active_template["subject_template"]
    subject = subject.replace("{{company}}", job.get("company", "the company"))
    state["email_subject"] = subject
    
    return state


def send(state: AgentState) -> AgentState:
    if state.get("send_status") == "skipped":
        return state
        
    job = state.get("current_job")
    if job and job.get("id"):
        update_job_stage(job["id"], "Dispatching Email")
        
    recipient = state.get("recruiter_email")
    body = state.get("email_body")
    subject = state.get("email_subject")
    
    if not recipient or not body or not subject:
        state["send_status"] = "failed"
        state["errors"].append("Cannot send without recipient, subject, and body.")
        return state
        
    if os.getenv("DRY_RUN", "true").lower() == "true":
        state["send_status"] = "skipped"
        return state
        
    pdf_path = state.get("pdf_path")
    send_result = gmail.send_email(to=recipient, subject=subject, body=body, pdf_path=pdf_path)
    state["gmail_message_id"] = send_result.message_id
    state["gmail_thread_id"] = send_result.thread_id
    state["send_status"] = "sent"
    return state
