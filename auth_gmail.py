import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly"
]

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python auth_gmail.py <path_to_client_secret_json>")
        sys.exit(1)

    client_secret_file = sys.argv[1]
    
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    creds = flow.run_local_server(port=0)

    token_dict = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }

    token_json_str = json.dumps(token_dict)
    
    print("\n\n" + "="*50)
    print("Authentication Successful!")
    print("Copy the entire string below and paste it as your GMAIL_TOKEN_JSON in the .env file:")
    print("="*50 + "\n")
    print(token_json_str)
    print("\n" + "="*50)

if __name__ == "__main__":
    main()
