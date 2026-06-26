import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge_retrieval.indexer import knowledge_indexer

backend_dir = Path(__file__).resolve().parent.parent
knowledge_indexer.configure(backend_dir)

docs = knowledge_indexer._build_documents()
print(f"Total chunks: {len(docs)}")
if docs:
    print(f"Sample keys: {list(docs[0].keys())}")
    print(f"Sample text length: {len(docs[0]['text'])}")
    print(f"Sample doc_id: {docs[0]['doc_id']}")
    print(f"Sample source_path: {docs[0]['source_path']}")
