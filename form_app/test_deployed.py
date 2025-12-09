import os

import requests
from dotenv import load_dotenv

load_dotenv()


url = os.getenv("FORM_WEB_URL") + "/version"
response = requests.get(url)
print(response.json())
