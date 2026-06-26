import requests, json

BASE = "http://127.0.0.1:8004"

# 1. 健康检查
r = requests.get(f"{BASE}/health")
print("Health:", r.status_code, r.json() if r.status_code == 200 else r.text)

# 2. 检查索引状态
r = requests.get(f"{BASE}/api/knowledge/status")
print("Index status:", r.status_code)
if r.status_code == 200:
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))

# 3. 测试检索（向量+BM25）
r = requests.post(f"{BASE}/api/knowledge/retrieve", json={
    "query": "二甲双胍 肾功能不全",
    "top_k": 3,
    "path_filter": "knowledge/medical/"
})
print("\nRetrieve:", r.status_code)
if r.status_code == 200:
    print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:2000])
