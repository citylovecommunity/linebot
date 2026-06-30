"""
One-time script to get a Google OAuth2 refresh token.
Run: uv run python scripts/get_google_refresh_token.py
Then paste the printed values into .env.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secrets.json",  # the OAuth2 desktop JSON you downloaded from GCP
    scopes=SCOPES,
)
creds = flow.run_local_server(port=0)

print("\nAdd these to your .env:\n")
print(f"GOOGLE_CLIENT_ID={creds.client_id}")
print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
