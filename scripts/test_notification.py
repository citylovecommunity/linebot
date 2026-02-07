import requests

from form_app.config import settings

url = f"{settings.APP_URL}/tasks/send-notifications"
headers = {
    "X-Task-Secret": settings.TASK_SECRET,
    "Content-Type": "application/json"
}
# Include a data payload if the endpoint expects one
data = {
    "message": "Hello from Python"
}

response = requests.post(url, headers=headers, json=data)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
