import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from knowledge_retrieval.indexer import knowledge_indexer

backend_dir = Path(__file__).resolve().parent.parent
knowledge_indexer.configure(backend_dir)

print("=== Test Retrieval ===")
print(f"Vector ready: {knowledge_indexer._vector_ready}")
print(f"BM25 ready: {knowledge_indexer._bm25_ready}")
print()

# Test 1: Vector retrieval
query = "二甲双胍 肾功能不全"
print(f"Query: {query}")
print()

vector_results = knowledge_indexer.retrieve_vector(query, top_k=3)
print(f"Vector results: {len(vector_results)}")
for i, ev in enumerate(vector_results):
    print(f"  [{i+1}] {ev.source_path} | score={ev.score:.4f}")
    print(f"      {ev.snippet[:120]}...")
print()

# Test 2: BM25 retrieval
bm25_results = knowledge_indexer.retrieve_bm25(query, top_k=3)
print(f"BM25 results: {len(bm25_results)}")
for i, ev in enumerate(bm25_results):
    print(f"  [{i+1}] {ev.source_path} | score={ev.score:.4f}")
    print(f"      {ev.snippet[:120]}...")
print()

# Test 3: Path filter
filtered = knowledge_indexer.retrieve_vector(
    query, top_k=3, path_filters=["knowledge/medical/literature/"]
)
print(f"Filtered (medical/literature only): {len(filtered)}")
for ev in filtered:
    print(f"  - {ev.source_path}")
