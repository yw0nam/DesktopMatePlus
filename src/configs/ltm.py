import os
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# .env 파일 로드
load_dotenv()

# --- 각 config 딕셔너리의 내용을 정의하는 내부 모델 ---


class Mem0LLMConfigValues(BaseModel):
    """Mem0 LLM config 내부 값 정의"""

    openai_base_url: str = "http://localhost:55120/v1"
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("LTM_API_KEY"))
    model: str = "chat_model"


class Mem0EmbedderConfigValues(BaseModel):
    """Mem0 Embedder config 내부 값 정의"""

    model_name: str = "chat_model"
    openai_base_url: str = "http://localhost:5504/v1"
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("EMB_API_KEY")
    )
    embedding_dims: int = 2560


class Mem0VectorStoreConfigValues(BaseModel):
    """Mem0 Vector Store config 내부 값 정의"""

    url: str = "http://localhost:6333"
    embedding_model_dims: int = 2560
    collection_name: str = "mem0_collection"


class Mem0GraphStoreConfigValues(BaseModel):
    """Mem0 Graph Store config 내부 값 정의"""

    url: str = "bolt://localhost:7687"
    username: Optional[str] = Field(default_factory=lambda: os.getenv("NEO4J_USER"))
    password: Optional[str] = Field(default_factory=lambda: os.getenv("NEO4J_PASSWORD"))


class Mem0LongTermMemoryConfig(BaseModel):
    """
    Mem0를 Long-Term Memory로 구성하기 위한 설정 클래스 (수정됨)
    """

    class Mem0LLMConfig(BaseModel):
        provider: Literal["openai"] = Field("openai")
        # config 타입을 Dict[str, Any] 대신 명시적인 모델로 변경
        config: Mem0LLMConfigValues = Field(default_factory=Mem0LLMConfigValues)

    class Mem0EmbedderConfig(BaseModel):
        provider: Literal["langchain"] = Field("langchain")
        config: Mem0EmbedderConfigValues = Field(
            default_factory=Mem0EmbedderConfigValues
        )

    class Mem0VectorStoreConfig(BaseModel):
        provider: Literal["qdrant"] = Field("qdrant")
        config: Mem0VectorStoreConfigValues = Field(
            default_factory=Mem0VectorStoreConfigValues
        )

    class Mem0GraphStoreConfig(BaseModel):
        provider: Literal["neo4j"] = Field("neo4j")
        config: Mem0GraphStoreConfigValues = Field(
            default_factory=Mem0GraphStoreConfigValues
        )

    # --- 메인 클래스 필드 ---

    llm: Mem0LLMConfig = Field(default_factory=Mem0LLMConfig)
    embedder: Mem0EmbedderConfig = Field(default_factory=Mem0EmbedderConfig)
    vector_store: Mem0VectorStoreConfig = Field(default_factory=Mem0VectorStoreConfig)
    graph_store: Mem0GraphStoreConfig = Field(default_factory=Mem0GraphStoreConfig)

    # 참고: Python 3.10 이상에서는 순방향 참조를 위한 문자열("")을 사용할 필요가 없습니다.
    # llm: "Mem0LongTermMemoryConfig.Mem0LLMConfig" 대신 llm: Mem0LLMConfig 사용 가능


class MemoryConfig(BaseModel):
    """최종 메모리 설정"""

    memory_type: Literal["mem0"] = Field("mem0", description="사용할 메모리 유형")
    mem0: Optional[Mem0LongTermMemoryConfig] = Field(
        default_factory=Mem0LongTermMemoryConfig,
        description="Mem0 Long-Term Memory 설정",
    )
