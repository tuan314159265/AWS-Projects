import urllib.request
import json
import sys

url = "https://2ohkfkehda.execute-api.ap-southeast-2.amazonaws.com/prod/query"
query = sys.argv[1] if len(sys.argv) > 1 else "giá vàng"

data = json.dumps({
    "query": query,
    "model": "anthropic.claude-3-5-sonnet-20241022-v2:0"
}).encode('utf-8')

req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print("Success:")
        print(result)
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
