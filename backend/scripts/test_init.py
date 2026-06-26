from config import get_settings
settings = get_settings()
print(f"[Config] LLM: {settings.llm_provider}/{settings.llm_model}")

from graph.agent import agent_manager
agent_manager.initialize(settings.backend_dir)
print("[Agent] init OK")

from knowledge_retrieval.indexer import knowledge_indexer
knowledge_indexer.configure(settings.backend_dir)
print(f"[Indexer] OK: {len(knowledge_indexer._documents)} docs, vector={knowledge_indexer._vector_ready}, bm25={knowledge_indexer._bm25_ready}")

from knowledge_retrieval.skill_retriever_agent import skill_retriever_agent
skill_retriever_agent.configure(settings.backend_dir, agent_manager._build_chat_model)
print("[SkillAgent] configure OK")
