import requests

url = "https://formapptest-144989130507.asia-east1.run.app/tasks/send-notifications"
headers = {
    "X-Task-Secret": "hehe",
    "Content-Type": "application/json"
}
# Include a data payload if the endpoint expects one
data = {
    "message": "Hello from Python"
}

response = requests.post(url, headers=headers, json=data)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
