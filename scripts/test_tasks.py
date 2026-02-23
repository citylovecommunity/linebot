import requests

from form_app.config import settings

url = "http://127.0.0.1:5000/tasks/load-data-from-gs"
headers = {
    "X-Task-Secret": settings.TASK_SECRET,
}

response = requests.post(url, headers=headers)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
