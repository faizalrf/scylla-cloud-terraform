import requests

account_id = 929
cluster_id = 34797
headers = {"Authorization": f""}

url = f"https://api.cloud.scylladb.com/api/v1/accounts/self/clusters/{cluster_id}/auth/cql"

response = requests.get(url, headers=headers)
response.raise_for_status()
auth = response.json()["data"]

cql_username = auth["username"]
cql_password = auth["password"]

print(f"User: {cql_username} & Password: {cql_password}")
