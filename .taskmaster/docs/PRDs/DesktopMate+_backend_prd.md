

# **DesktopMate-Plus: Python 백엔드 기술 사양 및 PRD**

## **1\. 개요**

### **1.1. 문서의 목적**

본 문서는 "DesktopMate-Plus" 데스크톱 애플리케이션의 핵심 지능을 담당하는 Python 백엔드(이하 '사이드카')의 개발 요구사항을 상세히 정의합니다. 이 문서는 프론트엔드(Tauri)와의 연동을 위한 명확한 API 계약을 수립하고, 백엔드 개발자가 독립적으로 핵심 AI 기능을 개발 및 테스트할 수 있도록 가이드하는 것을 목표로 합니다.

### **1.2. 백엔드 아키텍처 원칙**

백엔드는 FastAPI를 기반으로 하는 경량 HTTP 서버로 구축됩니다. 1 이 서버는 최종적으로 PyInstaller와 같은 도구를 사용하여 모든 종속성과 모델을 포함하는 단일 실행 파일로 패키징될 예정입니다. 3 이 방식은 Rust 기반의 메인 애플리케이션이 사이드카 프로세스를 쉽게 생성하고 관리할 수 있도록 합니다. 3

* **독립성:** 백엔드는 프론트엔드 없이도 독립적으로 실행되고 테스트될 수 있어야 합니다.  
* **상태 기반 API:** API 자체는 상태 비저장(stateless)으로 설계되지만, LangGraph의 내장 메모리 및 Checkpointer 기능을 통해 대화의 상태(stateful)를 완벽하게 관리합니다.  
* **단순함 우선(Simple as possible):** 불필요한 복잡도를 피하고 작은 단위로 명확히 분리합니다.  
* **서비스 독립성:** VLM, TTS, 에이전트 등은 느슨하게 결합되어 개별 기동/교체/테스트가 가능해야 합니다.  
* **테스트 가능성:** 외부 의존성 모킹이 가능한 인터페이스(내부 함수/도구)로 설계하여 단위/통합 테스트 용이성을 확보합니다.  
* **외부화된 모델 서버:** OpenAI, 로컬 vLLM, Fish Speech 등 외부 API/프로세스만 호출합니다. 백엔드 프로세스 내부에 GPU 추론을 직접 포함하지 않습니다.  
* **버전관리**: 모든 버전관리는 pyproject.toml 과 uv를 사용합니다.
* **코드 스타일**: 모든 코드는 PEP8 스타일 가이드를 준수합니다.

## **2\. 핵심 모듈별 기술 사양**

백엔드는 크게 세 가지 핵심 AI 모듈과 이를 총괄하는 API 서버로 구성됩니다.

### **2.1. 시각 인지 모듈 (VLM 서비스)**

컴패니언의 '눈' 역할을 하며, 사용자의 화면을 시각적으로 이해합니다.

* **핵심 기술:** vLLM 추론 서버  
  * **선택 이유:** vLLM은 OpenAI 호환 API 엔드포인트를 제공하여 LangGraph와의 통합이 용이하며, PagedAttention과 같은 최적화 기술을 통해 높은 처리량과 효율적인 메모리 관리를 지원합니다.  
* **기능 요구사항:**  
  1. **화면 캡처:** DXcam(Windows) 또는 MSS(macOS/Linux)와 같은 고성능 라이브러리를 사용하여 화면 이미지를 효율적으로 캡처하는 기능을 구현해야 합니다.  
  2. **이미지 처리:** 캡처된 이미지를 Base64로 인코딩하여 VLM API 요청에 포함할 수 있도록 처리합니다.  
  3. **내부 인터페이스:** LangGraph 에이전트가 호출할 수 있는 get\_visual\_description(image: bytes) \-\> str 형태의 내부 Python 함수를 제공해야 합니다. 이 함수는 vLLM 서버로 API 요청을 보내고 결과 텍스트를 반환합니다.

### **2.2. 음성 생성 모듈 (TTS 서비스)**

컴패니언의 '목소리' 역할을 하며, 텍스트를 자연스러운 음성으로 변환합니다.

* **핵심 기술:** Fish Speech (OpenAudio) 로컬 HTTP API 서버 4  
* **추천 모델:** OpenAudio S1-mini (0.5B 파라미터) 4  
  * **선택 이유:** 낮은 리소스 요구사항으로 대부분의 사용자 환경에 적합합니다.  
* **기능 요구사항:**  
  1. **음성 합성 인터페이스:** LangGraph 에이전트가 호출할 synthesize\_speech(text: str) \-\> bytes 형태의 API를 구현하여, 외부 TTS서버에 요청하여야함. 이 함수는 Fish Speech 서버에 HTTP POST 요청을 보내고, 생성된 오디오 데이터(예: .wav 또는 .mp3)를 반환합니다.  
  2. **음성 복제 인터페이스:** 사용자가 제공한 오디오 파일(.wav)을 받아 Fish Speech의 제로샷 음성 복제 기능을 활성화하는 clone\_voice\_from\_audio(audio\_file: bytes) 함수를 구현해야 합니다.

### **2.3. 인지 엔진 (LangGraph 에이전트)**

컴패니언의 '두뇌' 역할을 하며, 상황을 인지하고, 추론하며, 행동을 결정합니다.

* **핵심 기술:** LangGraph 6  
  * **선택 이유:** 상태 기반의 순환적 그래프 구조를 통해 복잡하고 동적인 에이전트 워크플로우를 유연하게 구축할 수 있습니다. 7  
* **상태 정의 (GraphState):**  
  * 에이전트의 메모리와 작업 흐름을 관리하기 위해 TypedDict를 사용하여 상태를 정의합니다.

Python  
class GraphState(TypedDict):  
    messages: Annotated\[list, operator.add\]  \# 대화 기록  
    visual\_context: str                      \# 현재 화면에 대한 시각적 설명  
    action\_plan: str                         \# LLM이 결정한 다음 행동  
    user\_id: str                             \# 사용자를 식별하기 위한 ID

* **노드(Node) 정의:**  
  * perceive\_environment: 시각 인지 모듈을 호출하여 화면 정보를 가져오고 visual\_context 상태를 업데이트합니다.  
  * query\_memory: mem0 라이브러리를 사용하여 현재 대화 및 시각적 컨텍스트와 관련된 장기 기억을 조회합니다.  
  * reason\_and\_plan: 현재 messages, visual\_context, 그리고 query\_memory에서 가져온 장기 기억을 종합하여 핵심 LLM을 호출하고, 다음 행동(예: '응답 생성', '침묵')을 결정하여 action\_plan 상태를 업데이트합니다.  
  * generate\_response: reason\_and\_plan 노드의 결정에 따라 사용자에게 전달할 응답 텍스트를 생성하고 messages 상태에 추가합니다.  
  * update\_memory: 대화가 끝난 후, mem0를 사용하여 현재 대화의 핵심 내용을 장기 기억에 저장합니다.  
* **엣지(Edge) 정의:**  
  * **조건부 엣지:** reason\_and\_plan 노드 이후, action\_plan 상태에 따라 generate\_response 노드로 이동할지, 아니면 워크플로우를 종료할지를 결정하는 조건부 엣지를 구현합니다. 7  
* **도구(Tool) 통합:**  
  * get\_screen\_context 도구: perceive\_environment 노드에서 사용되며, 시각 인지 모듈을 통해 화면 분석을 수행합니다.  
  * memory\_tool: query\_memory 및 update\_memory 노드에서 사용되며, mem0 라이브러리와 상호작용합니다.  
  * speak 도구: 최종 응답이 생성되면, 이 도구는 음성 생성 모듈을 호출하여 오디오를 생성하고, 이 오디오 데이터는 최종 API 응답으로 프론트엔드에 전달됩니다.

#### **2.3.1. 메모리 관리 (Memory Management)**

컴패니언이 대화의 연속성을 유지하고 사용자에 대해 학습할 수 있도록 두 가지 수준의 메모리 시스템을 구현합니다.

* **대화 기록 (Checkpointer):**  
  * **기술:** LangGraph의 내장 Checkpointer 기능을 사용합니다 (예: SqliteSaver). 9  
  * **역할:** 각 대화 스레드(thread\_id)별로 전체 GraphState를 지속적으로 저장하고 복원합니다. 이를 통해 API 호출이 분리되어 있어도 대화의 맥락(최근 메시지, 중간 상태 등)이 완벽하게 유지됩니다. 6 conversation\_history를 API 요청으로 전달할 필요가 없어집니다.  
* **장기/단기 기억 (mem0):**  
  * **기술:** mem0 라이브러리를 사용합니다.  
  * **역할:** 단순한 대화 기록을 넘어선 의미론적 기억을 관리합니다.  
    * **장기 기억 (Long-term Memory):** 사용자의 이름, 선호도, 과거에 언급했던 중요한 사실 등 핵심 정보를 저장합니다.  
    * **단기 기억 (Short-term Memory):** 현재 대화의 요약이나 핵심 엔티티를 저장하여 에이전트가 대화의 초점을 잃지 않도록 돕습니다.  
  * **통합 방식:** mem0는 LangGraph 에이전트 내에서 memory\_tool로 통합됩니다. reason\_and\_plan 노드는 LLM에게 더 풍부한 컨텍스트를 제공하기 위해 이 도구를 호출하여 관련 기억을 조회합니다.

##### A) 구현 로드맵 요약 (Phase 1 → 3)

- **Phase 1 (MVP):** LangGraph 상태 + mem0 검색 기반 "Search-Before-Act" 패턴 도입. 모든 응답 전에 관련 기억을 자동 검색하고 컨텍스트로 결합합니다. 대화 중 새롭고 중요한 정보가 감지되면 `add_memory` 도구로 저장합니다(업데이트/삭제 제외).  
- **Phase 2:** `update_memory`/`delete_memory` 도구 추가. 모든 변경은 반드시 "Read-then-Write"(search → modify) 절차를 거칩니다. 메타데이터의 통제된 어휘(Controlled Vocabulary)를 도입하여 일관성을 보장합니다.  
- **Phase 3:** 'Fresh/Old' 메모리 계층화를 도입합니다. 주기 스크립트(cleanup.py)로 오래된 기억을 Old로 이동하고, 검색은 Fresh → 부족 시 Old 순차 확장(Sequential Probing)으로 수행합니다.

##### B) 메모리 도구(내부 API)와 계약

- **add_memory(content, user_id, metadata?) → memory_id**  
  - Pydantic 스키마로 content(str), user_id(str) 필수. metadata에는 `category`, `updated_at`(UTC ISO8601) 등 포함.  
- **update_memory(memory_id, content?, metadata?) → ok**  
  - 업데이트 전 반드시 검색(search)로 대상 `memory_id` 식별(읽고-쓴다). 충돌 시 가장 최신(updated_at) 기준 병합 정책 정의.  
- **delete_memory(memory_id) → ok**  
  - 사용자의 명시적 삭제 요청 문맥에서만 호출.  
- 모든 도구 호출은 LangGraph 노드 안에서만 발생하며, 외부 HTTP API로 직접 노출하지 않습니다.

##### C) 통제된 어휘(Controlled Vocabulary) 관리

- **목표:** 메타데이터의 `category` 등 용어를 통제하여 검색 품질과 데이터 일관성을 높임.  
- **스토리지:** 개발 초기엔 SQLite 가능하나, 운영 환경에선 트랜잭션/동시성 보장을 위해 PostgreSQL 권장.  
- **VocabularyManager 요구사항:**  
  - 앱 시작 시 `controlled_vocabulary(category TEXT UNIQUE)` 테이블 보장.  
  - `get_all_terms()`로 정렬된 카테고리 목록 제공.  
  - `ensure_categories(term_list)`는 정규화 후 존재하지 않는 항목만 `INSERT ... ON CONFLICT DO NOTHING`로 추가.  
  - `add_memory`/`search_memory` 로직은 metadata.category를 `ensure_categories()`로 검증 후 저장/검색.

##### D) Fresh/Old 계층화와 주기적 마이그레이션

- mem0(또는 벡터 스토어) 내에 `fresh_memory`/`old_memory` 두 컬렉션(혹은 네임스페이스)을 구성.  
- 기본 `add`/`search` 대상은 `fresh_memory`.  
- `cleanup.py` 주기 스크립트 요구사항:  
  - 모든 기억의 `updated_at` 확인(추가/업데이트 시 반드시 기록).  
  - 임계기간(예: 30일) 경과 항목은 Old로 이동, Fresh에선 삭제.  
- 검색 로직: 먼저 Fresh 검색 → 결과 부족 시 Old 추가 검색 → 결과 합쳐 반환(Sequential Probing).

##### E) 수용 기준(Acceptance Criteria)

- 검색-전-행동(Search-Before-Act)이 항상 수행됨을 단위/통합 테스트로 보장.  
- 업데이트/삭제는 `memory_id` 확인을 위한 선행 검색을 필수로 거침(Read-then-Write).  
- 모든 저장 항목에 `updated_at` 타임스탬프가 존재.  
- metadata.category는 VocabularyManager를 통해 검증 및 관리.  
- Fresh/Old 순차 검색이 기능 플래그 또는 설정으로 제어 가능.  
- 모든 메모리 도구는 외부 API 비노출(에이전트 내부 전용).

## **3\. 외부 API 사양 (FastAPI)**

백엔드는 Tauri 프론트엔드와의 통신을 위해 다음과 같은 HTTP 엔드포인트를 제공해야 합니다.

### **3.1. 서버 설정**

* **호스트:** 127.0.0.1  
* **포트:** 동적으로 할당되거나 미리 지정된 포트 (예: 8000\)  
* **문서:** FastAPI의 자동 생성 문서(http://127.0.0.1:8000/docs)를 통해 모든 엔드포인트를 테스트할 수 있어야 합니다.

### **3.2. API 엔드포인트**

#### **POST /v1/chat**

* **설명:** 사용자의 메시지를 받아 LangGraph 에이전트를 실행하고, 컴패니언의 음성 응답을 반환합니다. 대화의 연속성은 thread\_id를 통해 관리됩니다.  
* **요청 본문 (JSON):**  
  JSON  
  {  
    "user\_id": "unique\_user\_identifier\_123",  
    "thread\_id": "conversation\_thread\_abc\_456", // 새로운 대화 시작 시 null 또는 생략 가능  
    "message": "지금 화면에 뭐가 보여?"  
  }

* **처리 흐름:**  
  1. 요청에서 thread\_id와 user\_id를 가져옵니다.  
  2. Checkpointer를 사용하여 해당 thread\_id에 대한 대화 상태를 로드합니다. thread\_id가 없으면 새로운 대화를 시작하고 새 thread\_id를 생성합니다.  
  3. 사용자의 message를 GraphState에 추가합니다.  
  4. LangGraph 워크플로우(perceive \-\> query\_memory \-\> reason \-\> generate \-\> update\_memory)를 실행합니다. 이때 query\_memory는 "Search-Before-Act"를 준수하며, update/delete 동작은 내부 정책(읽고-쓴다: Read-then-Write)을 따릅니다.  
  5. 최종적으로 생성된 응답 텍스트를 speak 도구(음성 생성 모듈)에 전달하여 오디오 데이터를 생성합니다.  
* **응답 본문:**  
  * **성공 (200 OK):**  
    JSON  
    {  
      "thread\_id": "conversation\_thread\_abc\_456", // 클라이언트가 다음 요청에 사용해야 할 ID  
      "text\_response": "화면 중앙에 리그 오브 레전드 게임이 실행 중인 것으로 보입니다.",  
      "audio\_response\_b64": "..." // Base64 인코딩된 WAV 또는 MP3 데이터  
    }

  * **오류 (500 Internal Server Error):**  
    JSON  
    {"detail": "Error processing request: \[에러 메시지\]"}

#### **POST /v1/voice**

* **설명:** 제로샷 음성 복제를 위해 사용자 음성 오디오 파일을 업로드합니다.  
* **요청 본문 (Multipart/Form-Data):**  
  * audio\_file: 사용자의 음성이 녹음된 .wav 파일  
* **처리 흐름:**  
  1. 업로드된 오디오 파일을 음성 생성 모듈의 clone\_voice\_from\_audio 함수에 전달합니다.  
  2. Fish Speech가 참조 음성을 업데이트하도록 처리합니다.  
* **응답 본문 (JSON):**  
  * **성공 (200 OK):** {"status": "success", "message": "Voice reference updated successfully."}  
  * **오류 (400 Bad Request):** {"detail": "Invalid audio file format."}

#### **GET /health**

* **설명:** 백엔드 서버와 모든 AI 모듈이 정상적으로 실행 중인지 확인하는 상태 체크 엔드포인트입니다.  
* **요청 본문:** 없음  
* **응답 본문 (JSON):**  
  * **성공 (200 OK):** {"status": "ok", "modules": {"vlm": "ready", "tts": "ready", "agent": "ready"}}  
  * **실패 (503 Service Unavailable):** {"status": "error", "modules": {"vlm": "loading", "tts": "error", "agent": "ready"}}

## **4\. 패키징 및 배포**

* **패키징 도구:** PyInstaller 1  
* **요구사항:**  
  1. 모든 Python 종속성(fastapi, vllm, langgraph, fish-speech, mem0 등)을 포함해야 합니다.  
  2. AI 모델 가중치 파일(VLM, TTS)을 실행 파일 내에 포함하거나, 실행 파일과 함께 배포될 특정 폴더에서 로드할 수 있어야 합니다.  
  3. 최종 결과물은 Tauri 빌드 프로세스에 포함될 수 있는 단일 실행 파일이어야 합니다. 3

## **5\. 개발 및 테스트 계획**

1. **모듈별 단위 테스트:** 각 AI 모듈(VLM, TTS, LangGraph 노드, 메모리 도구)이 독립적으로 기능하는지 검증하는 단위 테스트를 작성합니다.  
2. **API 통합 테스트:** requests 라이브러리나 Postman과 같은 도구를 사용하여 FastAPI 서버를 로컬에서 실행하고, 정의된 모든 엔드포인트가 예상대로 작동하는지 테스트합니다. 특히 thread\_id를 사용하여 여러 번의 POST /v1/chat 호출이 대화 맥락을 유지하는지 확인하는 것이 중요합니다.  
3. **개발 환경:** 개발 단계에서는 Docker를 사용하여 Python 환경과 모델 서버(VLM, TTS)를 구성하는 것을 권장합니다. 이는 팀원 간의 일관된 개발 환경을 보장하고 의존성 관리를 용이하게 합니다. 4 최종 배포용 실행 파일은 이 Docker 환경 내에서 PyInstaller를 통해 빌드할 수 있습니다.

#### **참고 자료**

1. dieharders/example-tauri-python-server-sidecar: An ... \- GitHub, 10월 15, 2025에 액세스, [https://github.com/dieharders/example-tauri-python-server-sidecar](https://github.com/dieharders/example-tauri-python-server-sidecar)  
2. Python as Tauri sidecar \- Reddit, 10월 15, 2025에 액세스, [https://www.reddit.com/r/tauri/comments/1clkf1j/python\_as\_tauri\_sidecar/](https://www.reddit.com/r/tauri/comments/1clkf1j/python_as_tauri_sidecar/)  
3. How to write and package desktop apps with Tauri \+ Vue \+ Python \- Senhaji Rhazi hamza, 10월 15, 2025에 액세스, [https://hamza-senhajirhazi.medium.com/how-to-write-and-package-desktop-apps-with-tauri-vue-python-ecc08e1e9f2a](https://hamza-senhajirhazi.medium.com/how-to-write-and-package-desktop-apps-with-tauri-vue-python-ecc08e1e9f2a)  
4. OpenAudio, 10월 15, 2025에 액세스, [https://speech.fish.audio/](https://speech.fish.audio/)  
5. Fish Speech: An Efficient Low-Memory Voice Cloning Open Source Tool | by Gen. Devin DL., 10월 15, 2025에 액세스, [https://medium.com/@tubelwj/fish-speech-an-efficient-low-memory-voice-cloning-open-source-tool-7abb935b521f](https://medium.com/@tubelwj/fish-speech-an-efficient-low-memory-voice-cloning-open-source-tool-7abb935b521f)  
6. LangGraph: Build Stateful AI Agents in Python \- Real Python, 10월 15, 2025에 액세스, [https://realpython.com/langgraph-python/](https://realpython.com/langgraph-python/)  
7. LangGraph Tutorial: Complete Beginner's Guide to Getting Started \- Latenode, 10월 15, 2025에 액세스, [https://latenode.com/blog/langgraph-tutorial-complete-beginners-guide-to-getting-started](https://latenode.com/blog/langgraph-tutorial-complete-beginners-guide-to-getting-started)  
8. Learn LangGraph basics \- Overview, 10월 15, 2025에 액세스, [https://langchain-ai.github.io/langgraph/concepts/why-langgraph/](https://langchain-ai.github.io/langgraph/concepts/why-langgraph/)  
9. Comparing Desktop Application Development Frameworks: Electron, Flutter, Tauri, React Native, and Qt | by Wassim | Medium, 10월 15, 2025에 액세스, [https://medium.com/@maxel333/comparing-desktop-application-development-frameworks-electron-flutter-tauri-react-native-and-fd2712765377](https://medium.com/@maxel333/comparing-desktop-application-development-frameworks-electron-flutter-tauri-react-native-and-fd2712765377)