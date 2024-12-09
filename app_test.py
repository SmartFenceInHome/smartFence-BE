import requests

url = "https://api.flrou.site/test"
headers = {
    'Content-Type': 'application/json'
}

data = {
    "key": "value"
}

response = requests.post(url, json=data, headers=headers)

print('Status Code:', response.status_code)
# print('Message:', response.message)
print('Response Text:', response.text)
