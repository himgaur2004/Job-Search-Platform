from __future__ import annotations

import os
import time
from typing import Dict, Any
from playwright.sync_api import sync_playwright

def _get_browser(p):
    return p.chromium.launch(headless=True)

def apply_to_workday(job_url: str, resume_path: str, candidate_details: Dict[str, str]) -> Dict[str, Any]:
    """
    Attempts to auto-apply to a Workday job listing.
    Workday instances vary heavily, this represents a generalized heuristic approach.
    """
    if not os.path.exists(resume_path):
        return {"success": False, "error": f"Resume not found at {resume_path}"}
        
    result = {"success": False, "error": None}
    
    with sync_playwright() as p:
        browser = _get_browser(p)
        page = browser.new_page()
        
        try:
            page.goto(job_url)
            
            # Click 'Apply' button
            apply_btn = page.query_selector("button:has-text('Apply'), a:has-text('Apply')")
            if apply_btn:
                apply_btn.click()
                page.wait_for_load_state("networkidle")
                
            # Handle Workday account creation / login (often requires creating an account per company)
            # This is highly complex. For this implementation, we look for guest apply or fast-path.
            
            # Upload Resume
            file_input = page.query_selector("input[type='file']")
            if file_input:
                file_input.set_input_files(resume_path)
                time.sleep(2) # Wait for parsing
                
            # Fill basic fields based on heuristics
            inputs = page.query_selector_all("input[type='text'], input[type='email']")
            for input_field in inputs:
                label = page.evaluate("(elem) => { let l = elem.closest('div').querySelector('label'); return l ? l.innerText : ''; }", input_field)
                label = label.lower()
                
                if "first name" in label:
                    input_field.fill(candidate_details.get("first_name", "John"))
                elif "last name" in label:
                    input_field.fill(candidate_details.get("last_name", "Doe"))
                elif "email" in label:
                    input_field.fill(candidate_details.get("email", "john.doe@example.com"))
                elif "phone" in label:
                    input_field.fill(candidate_details.get("phone", "555-0100"))
            
            # Click submit/next
            next_btn = page.query_selector("button:has-text('Next'), button:has-text('Submit')")
            if next_btn:
                next_btn.click()
                time.sleep(3)
                
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
        finally:
            browser.close()
            
    return result
