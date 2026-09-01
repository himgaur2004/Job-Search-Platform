from __future__ import annotations

import re

def parse_name_from_email(email: str) -> str:
    """
    Attempts to parse a human-readable name from an email address.
    e.g. john.doe@company.com -> John Doe
         jdoe@company.com -> Jdoe
         jane_smith123@... -> Jane Smith
    """
    if not email or "@" not in email:
        return "Hiring Team"
    
    # Get the local part (before the @)
    local_part = email.split("@")[0]
    
    # Remove numbers
    local_part = re.sub(r'\d+', '', local_part)
    
    # Split by common separators (. _ -)
    parts = re.split(r'[.\-_]', local_part)
    
    # Filter out empty strings
    parts = [p for p in parts if p]
    
    if not parts:
        return "Hiring Team"
    
    # Capitalize each part and join
    name = " ".join(p.capitalize() for p in parts)
    
    return name
