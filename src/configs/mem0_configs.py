import os
from typing import Dict

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

load_dotenv()
embedding_model = OpenAIEmbeddings(
    model=os.getenv("EMB_MODEL_NAME"),
    openai_api_base=os.getenv("EMB_BASE_URL"),
    openai_api_key=os.getenv("EMB_API_KEY"),
)

MEM0_CONFIG = {
    # 1. LLM 설정 (OpenAI 호환)
    "llm": {
        "provider": "openai",
        "config": {
            "openai_base_url": os.getenv("LLM_BASE_URL"),
            "api_key": os.getenv("LLM_API_KEY"),
            "model": os.getenv("LLM_MODEL_NAME"),
        },
    },
    # 2. 임베딩 모델 설정 (OpenAI 호환)
    "embedder": {
        "provider": "langchain",
        "config": {
            "model": embedding_model,
            "embedding_dims": 2560,
        },
    },
    # 3. 벡터 스토어 설정 (Qdrant)
    "vector_store": {
        "provider": "qdrant",
        "config": {
            # Mem0는 단일 URL을 기본으로 사용하므로, 클러스터의 대표 REST API 엔드포인트를 지정합니다.
            "url": os.getenv("QDRANT_URL"),
            "embedding_model_dims": 2560,
            "collection_name": os.getenv("QDRANT_COLLECTION_NAME"),
        },
    },
    # 4. 그래프 스토어 설정 (Neo4j)
    "graph_store": {
        "provider": "neo4j",
        "config": {
            # Mem0는 Bolt 프로토콜을 사용하여 Neo4j에 연결합니다. 기본 포트는 7687입니다.
            "url": os.getenv("NEO4J_URI"),
            # Neo4j 데이터베이스의 사용자 이름과 비밀번호를 입력해야 합니다.
            "username": os.getenv("NEO4J_USER"),
            "password": os.getenv("NEO4J_PASSWORD"),
        },
    },
}

VOCABULARY_DB_CONFIG: Dict[str, str] = {
    "host": os.getenv("VOCABULARY_DB_HOST", "localhost"),
    "database": os.getenv("VOCABULARY_DB_NAME", "memory_system_dev"),
    "user": os.getenv("VOCABULARY_DB_USER", "memory_system"),
    "password": os.getenv("VOCABULARY_DB_PASSWORD", "memory_system"),
    "port": os.getenv("VOCABULARY_DB_PORT", "5432"),
}
