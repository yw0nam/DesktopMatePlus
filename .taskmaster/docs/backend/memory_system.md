# 요약: 단계별 구현 로드맵

- Phase 1: 핵심 기능 구현 (The MVP - Minimum Viable Product)

목표: mem0과 LangChain을 사용하여, 대화 내용을 기억하고 검색할 수 있는 가장 기본적인 상태 저장(Stateful) 에이전트를 만듭니다.

결과물: 사용자와의 대화에서 정보를 저장하고, 다음 대화에서 저장된 정보를 바탕으로 답변하는 에이전트.

- Phase 2: 지능적 메모리 관리 및 일관성 확보

목표: 메모리를 수정하고 삭제하는 기능을 추가하고, 메타데이터를 체계적으로 관리하여 검색 성능과 데이터 일관성을 높입니다.

결과물: 정보 변경에 대응할 수 있고, 통제된 어휘를 사용하여 메타데이터를 관리하는 더 똑똑한 에이전트.

- Phase 3: 고급 기능 (선택적 확장)

목표: 이전에 논의했던 'Fresh/Old' 메모리 계층화와 같은 고급 정리 기능을 간단한 형태로 구현합니다.

결과물: 오래된 기억을 자동으로 아카이빙하여 핵심 메모리(Fresh)를 가볍게 유지하는 시스템.

## Phase 1: 핵심 기능 구현 (The MVP)

가장 먼저 구현해야 할 것은 에이전트가 기억을 '읽고 쓰는' 기본 능력입니다. 복잡한 정리 로직은 이 단계에서 제외합니다.

1. 어디부터 구현할 것인가?
기본 환경 설정:

mem0와 Langgraph 라이브러리를 설치합니다.

mem0 클라이언트를 초기화합니다. Qdrant, Embedding 모델, Neo4j, LLM 설정은 필수입니다.

LangGraph로 에이전트 뼈대 만들기:

LangGraph는 상태를 관리하는 데 가장 적합한 최신 프레임워크입니다.   

에이전트의 상태(State)를 정의합니다. messages (대화 기록)을 포함해야야합니다.

핵심 로직: "행동 전 검색 (Search-Before-Act)" 패턴 구현:

에이전트가 사용자의 입력에 응답하기 전에 항상 먼저 메모리를 검색하도록 만들어야 합니다. 이것이 에이전트가 기억을 가지고 있는 것처럼 느끼게 하는 가장 중요한 첫걸음입니다.   

LangGraph의 첫 번째 노드(Node)를 load_memories로 정의합니다. 이 노드는 사용자 입력을 받아 mem0.search()를 호출하고, 결과를 System Message에 추가합니다.

메모리 기반 응답 및 저장 기능 구현:

두 번째 노드인 agent 노드를 만듭니다. 이 노드는 시스템 프롬프트, 사용자 입력, 그리고 load_memories 노드에서 가져온 retrieved_memories를 모두 컨텍스트로 받아 LLM을 호출합니다.   

add_memory Tool을 정의합니다. 이 Tool은 대화 내용(content)과 user_id를 필수로 받도록 Pydantic 스키마를 설계합니다.

agent 노드의 프롬프트에 "새롭고 중요한 정보(예: 사용자 선호도, 이름)가 나타나면 add_memory Tool을 호출하여 저장하라"는 지침을 추가합니다.   

2. 어디까지 구현해야 하는가?
Phase 1은 다음 기능이 동작하면 완성된 것입니다.

에이전트가 매번 사용자 질문에 답하기 전에, 관련 기억을 mem0에서 자동으로 검색합니다.

검색된 기억을 바탕으로 개인화된 답변을 생성합니다.

대화 중 "내 이름은 OOO이야" 또는 "기억해줘: 나는 매운 음식을 좋아해" 와 같은 명시적 요청이 있을 때, 에이전트가 add_memory Tool을 호출하여 정보를 저장합니다.

이 단계에서 제외할 것: update, delete 기능, Fresh/Old 메모리 분리, 메타데이터 어휘집 관리

## Phase 2: 지능적 메모리 관리 및 일관성 확보
MVP가 완성되면, 이제 메모리의 품질과 일관성을 높이는 단계로 넘어갑니다.

1. 어디부터 구현할 것인가?
update 및 delete Tool 구현:

이전 논의에서 설계한 Pydantic 데이터 모델을 사용하여 update_memory와 delete_memory Tool을 추가합니다.

중요: 이 Tool들은 memory_id를 필수로 요구해야 합니다. 이는 LLM이 정보를 수정하거나 삭제하기 전에 반드시 search를 통해 대상 정보를 먼저 찾아야 하는 '읽기 후 쓰기(Read-then-Write)' 패턴을 강제하여 안정성을 높입니다.   

에이전트의 시스템 프롬프트에 관련 지침을 추가합니다.

update 지침: "만약 새로운 정보가 기존 기억과 충돌한다면, 먼저 search_memory로 기존 기억의 ID를 찾은 뒤, update_memory를 호출하여 정보를 수정하라."    

delete 지침: "사용자가 무언가를 잊어달라고 명시적으로 요청하면, search_memory로 해당 기억의 ID를 찾고 delete_memory를 호출하여 삭제하라."    

통제된 어휘(Controlled Vocabulary) 관리자 구현:

SQLite 대신 PostgreSQL 사용: 운영 환경에서 안전한 트랜잭션과 동시성을 보장하기 위해 PostgreSQL을 선택합니다. 환경 변수로 연결 정보를 관리하며, 유효한 카테고리를 한 곳에서 관리합니다.

VocabularyManager 클래스를 만듭니다.

__init__: PostgreSQL 데이터베이스에 연결하고 controlled_vocabulary 테이블(category TEXT UNIQUE)을 생성합니다. UNIQUE 제약조건이 중복을 자동으로 방지해줍니다.

get_all_terms(): SELECT category FROM controlled_vocabulary ORDER BY category 쿼리로 모든 카테고리를 조회합니다.

ensure_categories(term_list): 전달된 카테고리를 정규화하고, 존재하지 않으면 INSERT ... ON CONFLICT DO NOTHING으로 추가한 뒤, 정리된 목록을 반환합니다.

add_memory Tool과 search_memory Tool의 로직을 수정하여 metadata에 포함된 category 값을 ensure_categories()로 확인하고, 존재하는 범위 내에서 저장 또는 검색하도록 통제합니다.

2. 어디까지 구현해야 하는가?
Phase 2는 다음 기능이 구현되면 완료됩니다.

에이전트가 대화 중 정보의 변경(e.g., "이제 매운 음식을 싫어해")이나 삭제 요청에 대응할 수 있습니다.

add_memory Tool을 통해 추가되는 모든 메타데이터 카테고리가 SQLite 데이터베이스에 일관되게 기록되고 관리됩니다.

## Phase 3: 고급 기능 (선택적 확장)
이제 시스템의 핵심은 완성되었습니다. 사용자가 요청한 '기억 정리' 기능을 간단한 형태로 구현해 봅니다.

1. 어디부터 구현할 것인가?
'Fresh'/'Old' 메모리 개념 도입:

mem0 설정에서 두 개의 컬렉션(또는 Qdrant의 경우 두 개의 컬렉션)을 사용하도록 구성합니다: fresh_memory와 old_memory.

기본적으로 모든 add와 search는 fresh_memory를 대상으로 하도록 기존 Tool들을 수정합니다.

주기적인 메모리 이전(Migration) 스크립트 작성:

실시간으로 복잡한 ARC 알고리즘을 구현하는 대신, 별도의 간단한 Python 스크립트(cleanup.py)를 작성하여 주기적으로 실행하는 방식을 채택합니다. 이는 "Simple as possible" 원칙에 부합합니다.

cleanup.py 스크립트의 로직:

mem0 클라이언트로 fresh_memory에 연결합니다.

mem0.get_all()을 사용해 모든 기억을 가져옵니다.   

각 기억의 metadata에 저장된 updated_at 타임스탬프를 확인합니다. (이 타임스탬프는 add/update 시점에 항상 기록되어야 합니다.)

updated_at이 특정 기간(예: 30일) 이상 지난 기억들을 식별합니다.

식별된 '오래된' 기억들을 old_memory 컬렉션에 새로 추가하고, fresh_memory에서는 삭제합니다.

확장된 검색 로직 구현:

search_memory Tool을 수정하여 '순차적 확장 검색(Sequential Probing)' 로직을 구현합니다.

먼저 fresh_memory를 검색합니다.

만약 결과가 충분하지 않거나 없다면, old_memory를 추가로 검색합니다.

두 결과를 합쳐서 반환합니다.

2. 어디까지 구현해야 하는가?
Phase 3는 cleanup.py 스크립트를 수동으로 실행했을 때, 오래된 기억들이 fresh_memory에서 old_memory로 이동하고, 수정된 search_memory Tool이 두 컬렉션을 모두 검색할 수 있게 되면 완료됩니다.

이 단계적 접근법을 통해, 복잡한 기능들을 한 번에 구현하려 하기보다 안정적인 핵심 기능부터 시작하여 점진적으로 시스템을 확장해 나갈 수 있습니다.