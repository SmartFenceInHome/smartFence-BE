import requests
import json

# API 엔드포인트 URL
url = "https://api.flrou.site/test"

# 전송할 데이터
data = {
    "key": "value"
}

# POST 요청 보내기
response = requests.post(url, json=data)

# 응답 확인
print(response.json())