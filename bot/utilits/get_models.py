import requests
from pprint import pprint


url = "https://api.intelligence.io.solutions/api/v1/models"

headers = {
    "accept": "application/json",
    "Authorization": "Bearer io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6IjYzMmFiNzhjLTUwYWMtNDExNS1hMGFkLWYxOWU0MzFmOWU3ZSIsImV4cCI6NDg5OTY5Mzg2N30.Pl1tJYeBqgFfBn8Rp-jnC7PYHxREd_b8N7akQl80TBkP6iWXgGwMdA1bX7cAQoGZ67ypXPn3Mjv6piORIewG8g",
}

response = requests.get(url, headers=headers)
data = response.json()
pprint(data)

for i in range(len(data['data'])):
    name = data['data'][i]['id']
    print(name)