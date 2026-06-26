import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings
from knowledge_retrieval.indexer import knowledge_indexer

backend_dir = Path(__file__).resolve().parent.parent
knowledge_indexer.configure(backend_dir)

print("=" * 50)
print("Knowledge Index Rebuild")
print("=" * 50)
print(f"Knowledge dir: {knowledge_indexer._knowledge_dir}")
print(f"Storage dir: {knowledge_indexer._storage_dir}")
print(f"Vector dir: {knowledge_indexer._vector_dir}")
print(f"Embedding API key present: {'Yes' if get_settings().embedding_api_key else 'No'}")
print(f"Embedding provider: {get_settings().embedding_provider}")
print(f"Embedding model: {get_settings().embedding_model}")
print(f"Embedding base URL: {get_settings().embedding_base_url}")
print("=" * 50)

start = time.time()

try:
    knowledge_indexer.rebuild_index()
    elapsed = time.time() - start
    status = knowledge_indexer.status()
    print(f"\nRebuild completed in {elapsed:.2f}s")
    print(f"Total chunks: {len(knowledge_indexer._documents)}")
    print(f"Indexed files: {status.indexed_files}")
    print(f"Vector ready: {status.vector_ready}")
    print(f"BM25 ready: {status.bm25_ready}")
except Exception as e:
    elapsed = time.time() - start
    print(f"\nRebuild failed after {elapsed:.2f}s: {e}")
    import traceback
    traceback.print_exc()
