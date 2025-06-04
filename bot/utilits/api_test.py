import requests
from pprint import pprint

url = "https://api.intelligence.io.solutions/api/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6IjYzMmFiNzhjLTUwYWMtNDExNS1hMGFkLWYxOWU0MzFmOWU3ZSIsImV4cCI6NDg5OTY5Mzg2N30.Pl1tJYeBqgFfBn8Rp-jnC7PYHxREd_b8N7akQl80TBkP6iWXgGwMdA1bX7cAQoGZ67ypXPn3Mjv6piORIewG8g",
}

data = {
    "model": "deepseek-ai/DeepSeek-R1",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant"
        },
        {
            "role": "user",
            "content": "how are you doing"
        }
    ],
}

response = requests.post(url, headers=headers, json=data)
data = response.json()
pprint(data)

#"text = data['choices'][0]['message']['content']
#print(text.split('</think>\n\n')[1])