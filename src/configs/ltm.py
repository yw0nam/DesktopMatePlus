import os
from typing import Any, Dict, Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# .env 파일 로드
load_dotenv()


class Mem0LongTermMemoryConfig(BaseModel):
    """
    Mem0를 Long-Term Memory로 구성하기 위한 설정 클래스
    """

    # --- 1. 모든 하위 설정 클래스들을 내부에 정의 ---

    class Mem0LLMConfig(BaseModel):
        """Mem0의 LLM 설정 (OpenAI 호환)"""

        provider: Literal["openai"] = Field("openai")
        config: Dict[str, Any] = Field(
            default_factory=lambda: {
                "openai_base_url": "http://localhost:55120/v1",
                "api_key": os.getenv("LLM_API_KEY"),
                "model": "chat_model",
            }
        )

    class Mem0EmbedderConfig(BaseModel):
        """Mem0의 Embedder 설정 (Langchain 호환)"""

        provider: Literal["langchain"] = Field("langchain")
        config: Dict[str, Any] = Field(
            default_factory=lambda: {
                "model_name": "chat_model",
                "openai_api_base": "http://localhost:5504/v1",
                "openai_api_key": os.getenv("EMB_API_KEY"),
                "embedding_dims": 2560,
            }
        )

    class Mem0VectorStoreConfig(BaseModel):
        """Mem0의 Vector Store 설정 (Qdrant)"""

        provider: Literal["qdrant"] = Field("qdrant")
        config: Dict[str, Any] = Field(
            default_factory=lambda: {
                "url": "http://localhost:6333",
                "embedding_model_dims": 2560,
                "collection_name": "mem0_collection",
            }
        )

    class Mem0GraphStoreConfig(BaseModel):
        """Mem0의 Graph Store 설정 (Neo4j)"""

        provider: Literal["neo4j"] = Field("neo4j")
        config: Dict[str, Any] = Field(
            default_factory=lambda: {
                "url": "bolt://localhost:7687",
                "username": os.getenv("NEO4J_USER"),
                "password": os.getenv("NEO4J_PASSWORD"),
            }
        )

    llm: "Mem0LongTermMemoryConfig.Mem0LLMConfig" = Field(
        default_factory=lambda: Mem0LongTermMemoryConfig.Mem0LLMConfig()
    )
    embedder: "Mem0LongTermMemoryConfig.Mem0EmbedderConfig" = Field(
        default_factory=lambda: Mem0LongTermMemoryConfig.Mem0EmbedderConfig()
    )
    vector_store: "Mem0LongTermMemoryConfig.Mem0VectorStoreConfig" = Field(
        default_factory=lambda: Mem0LongTermMemoryConfig.Mem0VectorStoreConfig()
    )
    graph_store: "Mem0LongTermMemoryConfig.Mem0GraphStoreConfig" = Field(
        default_factory=lambda: Mem0LongTermMemoryConfig.Mem0GraphStoreConfig()
    )


class MemoryConfig(BaseModel):
    """최종 메모리 설정"""

    memory_type: Literal["mem0"] = Field("mem0", description="사용할 메모리 유형")
    mem0: Optional[Mem0LongTermMemoryConfig] = Field(
        default_factory=Mem0LongTermMemoryConfig,
        description="Mem0 Long-Term Memory 설정",
    )
