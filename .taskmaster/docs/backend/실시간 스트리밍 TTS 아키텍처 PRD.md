

# **LangGraph 스트리밍을 활용한 실시간 대화형 에이전트 제품 요구사항 명세서(PRD)**

## **I. 시스템 아키텍처 및 핵심 원칙**

### **1.1. 이벤트 기반 비동기 아키텍처**

본 시스템은 지연 시간을 최소화하고 동시성을 극대화하기 위해, 비동기 이벤트를 통해 통신하는 느슨하게 결합된(loosely coupled) 컴포넌트 집합으로 설계된다. 이 아키텍처는 단일 서버 인스턴스가 수많은 동시 클라이언트 연결을 효율적으로 관리할 수 있도록 하는 핵심적인 설계 원칙이다. 모든 I/O 작업은 논블로킹(non-blocking) 방식으로 처리되어야 하며, 이는 서버가 높은 부하 상황에서도 응답성을 유지하는 데 필수적이다.

**핵심 구성 요소:**

* **WebSocket 게이트웨이 (WebSocket Gateway):** 모든 클라이언트 통신의 상태 기반(stateful) 진입점이다. 연결 수명 주기 관리, 인증, 메시지 직렬화/역직렬화를 책임진다. 각 클라이언트 연결의 상태를 유지하며, 서버의 다른 부분과 클라이언트 간의 안정적인 양방향 통신 채널을 보장한다.
* **오케스트레이션 코어 (MessageProcessor):** 단일 대화 세션을 위한 중앙 처리 장치 역할을 한다. LangGraph 실행의 전체 수명 주기를 관리하고, 그래프에서 생성된 이벤트 스트림이 후처리 파이프라인으로 원활하게 흐르도록 조율한다. 또한, 클라이언트로부터의 인터럽트 신호와 같은 외부 제어 요청을 처리한다.
* **LangGraph 상태 머신 (LangGraph State Machine):** 에이전트의 '두뇌'에 해당한다. 대화 로직을 실행하고, 메모리 및 도구 호출과 같은 상태를 관리하며, 자신의 '사고' 과정을 나타내는 이벤트 스트림을 생성한다. 이 상태 머신은 대화의 맥락을 유지하고 복잡한 작업을 수행하는 중심부이다.
* **텍스트 처리 파이프라인 (Text Processing Pipeline):** LangGraph에서 생성된 원시(raw) 출력물을 클라이언트가 소비할 수 있는 형태로 변환하는 상태 기반 다단계 파이프라인이다. 예를 들어, UI에 실시간 타이핑 효과를 주기 위한 개별 토큰 스트림과 TTS(Text-to-Speech) 합성을 위한 정제된 문장 단위의 청크(chunk)를 생성하는 역할을 분담한다.

### **1.2. End-to-End 스트리밍 데이터 흐름**

사용자 메시지가 시스템을 통과하는 전체 여정은 다음과 같은 순차적 흐름을 따른다. 이 흐름은 시스템의 각 컴포넌트가 어떻게 상호작용하여 실시간 응답을 생성하는지를 명확히 보여준다.

1. **연결 수립:** 클라이언트는 서버의 WebSocket 엔드포인트와 보안 연결(WSS)을 수립한다.
2. **메시지 전송:** 클라이언트는 사용자 쿼리를 포함하는 send\_message 이벤트를 JSON 형식으로 서버에 전송한다. 이 메시지에는 대화의 연속성을 보장하기 위한 conversation\_id가 포함된다.
3. **라우팅 및 초기화:** WebSocket 게이트웨이는 수신된 메시지를 해당 conversation\_id에 할당된 MessageProcessor 인스턴스로 라우팅한다. 만약 기존 인스턴스가 없다면 새로 생성한다.
4. **LangGraph 실행:** MessageProcessor는 graph.astream\_events 메서드를 호출하여 LangGraph 실행을 시작한다. 이때 사용자 메시지와 대화 상태(체크포인터를 통해 로드됨)를 함께 전달한다.
5. **이벤트 스트림 소비:** MessageProcessor는 LangGraph로부터 비동기적으로 생성되는 이벤트 스트림을 소비하기 시작한다.
6. **다중 경로 분기 처리 (Multi-Path Fan-Out):** 새로운 텍스트 토큰을 포함하는 on\_chat\_model\_stream 이벤트가 발생할 때마다, 데이터는 두 개의 독립적인 경로로 동시에 처리된다. 이 분기 처리는 단일 소스 데이터로부터 각기 다른 사용자 경험(실시간 타이핑과 음성 출력)을 동시에 만족시키기 위한 핵심적인 설계이다.
   * **경로 A (UI 스트림):** 수신된 원시 토큰은 즉시 stream\_token WebSocket 이벤트로 패키징되어 클라이언트로 전송된다. 이는 UI에서 AI가 실시간으로 타이핑하는 듯한 효과를 구현하는 데 사용된다.
   * **경로 B (TTS/청킹 파이프라인):** 동일한 토큰이 TextChunkProcessor 인스턴스로 전달된다. 이 프로세서는 토큰들을 버퍼에 축적하여 의미 있는 문장 단위로 재구성하는 역할을 한다.
7. **문장 청크 생성:** TextChunkProcessor가 문장 종결자를 감지하여 완전한 문장(또는 절)을 식별하면, 해당 청크를 파이프라인의 다음 단계로 전달한다.
8. **텍스트 정제:** 생성된 청크는 TTSTextProcessor로 전달되어 TTS 합성에 부적합한 문자(예: 감정 표현, 머뭇거림)를 제거하고, 약어를 풀어쓰는 등 정규화 과정을 거친다.
9. **TTS 준비 완료 청크 전송:** 정제된 텍스트 청크는 tts\_ready\_chunk WebSocket 이벤트로 패키징되어 클라이언트로 전송된다. 클라이언트는 이 청크를 수신하여 TTS 엔진으로 전달, 음성을 생성할 수 있다.
10. **내부 상태 투명성 제공:** on\_tool\_start, on\_tool\_end와 같은 다른 LangGraph 이벤트들도 각각 tool\_call\_start, tool\_call\_end 등의 WebSocket 이벤트로 변환되어 클라이언트로 스트리밍된다. 이는 사용자에게 에이전트가 현재 어떤 작업을 수행하고 있는지(예: '날씨 정보 조회 중...') 투명하게 보여주는 역할을 한다.
11. **스트림 종료:** LangGraph 실행이 완료되면, stream\_end 이벤트가 클라이언트로 전송되어 현재의 응답 스트림이 모두 끝났음을 알린다.

### **1.3. 상태 관리 전략**

효과적인 상태 관리는 본 시스템의 안정성과 확장성을 보장하는 데 매우 중요하다. 시스템은 서로 다른 수명 주기를 가진 여러 계층의 상태를 명확히 구분하고 관리해야 한다. 이러한 계층적 상태 관리는 리소스 누수를 방지하고, 각 컴포넌트의 책임을 명확히 하며, 시스템 전체의 복잡도를 낮추는 효과를 가져온다.

**상태의 계층 구조:**

1. **연결 상태 (Connection State):** WebSocket 연결이 유지되는 동안 존재하는 상태. 사용자의 인증 정보, 고유 연결 ID(connection\_id) 등을 포함한다. 이 상태는 WebSocket 게이트웨이 수준에서 관리되며, 연결이 종료되면 소멸한다.
2. **대화 상태 (Conversation State):** 영속적으로 유지되어야 하는 대화의 전체 맥락. 사용자와 에이전트 간의 모든 메시지 기록을 포함한다. 이 상태는 LangGraph의 체크포인터(Checkpointer)를 통해 관리된다. 프로덕션 환경에서는 MemorySaver 대신 Redis나 데이터베이스와 연동된 RedisSaver와 같은 영속성 백엔드를 사용해야 한다. 이를 통해 서버가 재시작되거나 다른 인스턴스로 요청이 라우팅되어도 대화의 연속성이 보장된다.
3. **턴 상태 (Turn State):** 단일 사용자 메시지에 대한 AI 응답이 생성되는 동안만 존재하는 일시적인(ephemeral) 상태. 현재 실행 중인 LangGraph 스트림 asyncio.Task, TextChunkProcessor의 내부 버퍼 등이 여기에 해당한다. 이 상태는 MessageProcessor 인스턴스에 의해 생성되고 관리되며, stream\_end 이벤트가 전송되면 완전히 소멸되어야 한다.

**상태 간의 연결 및 관리:**

이러한 상태 계층들은 서로 유기적으로 연결되어야 한다. 예를 들어, WebSocket 게이트웨이에서 관리하는 connection\_id는 특정 사용자의 conversation\_id를 조회하는 데 사용될 수 있다. 클라이언트가 send\_message 요청 시 전달하는 conversation\_id는 LangGraph 체크포인터가 올바른 대화 상태를 로드하는 키로 사용된다. MessageProcessor는 이 conversation\_id를 기반으로 새로운 '턴 상태'를 생성하고, 응답이 완료되면 해당 턴 상태와 관련된 모든 리소스(예: asyncio 태스크, 텍스트 프로세서 인스턴스)를 안전하게 정리할 책임이 있다. 이처럼 각 상태의 수명 주기와 관리 주체를 명확히 분리하는 것은 상태 정보의 유출을 막고 시스템의 예측 가능성을 높이는 핵심적인 설계 원칙이다.

## **II. WebSocket 통신 프로토콜**

클라이언트와 서버 간의 통신은 본 명세서에 정의된 엄격하고 명확한 프로토콜을 따라야 한다. 이 프로토콜은 실시간 상호작용의 기반이 되며, 양측 개발자에게 단일 진실 공급원(Single Source of Truth) 역할을 한다.

### **2.1. 연결 수명 주기**

* **엔드포인트:** 클라이언트는 지정된 WebSocket 엔드포인트에 연결해야 한다. (예: wss://api.example.com/v1/chat/stream)
* **연결 초기화 및 인증:** 클라이언트는 WebSocket 연결이 성공적으로 수립된 직후, 반드시 authorize 메시지를 전송해야 한다. 이 메시지에는 JWT(JSON Web Token)와 같은 인증 자격 증명이 포함되어야 한다. 서버는 해당 자격 증명을 검증하고, 성공 시 authorize\_success를, 실패 시 authorize\_fail을 응답한 후 즉시 연결을 종료한다.
* **하트비트 메커니즘 (Heartbeat Mechanism):** 연결 상태를 능동적으로 확인하고 비정상적으로 종료된 연결(좀비 커넥션)을 감지하기 위해, 서버는 20초마다 ping 이벤트를 클라이언트에 전송한다. 클라이언트는 ping 수신 후 5초 이내에 pong 이벤트로 응답해야 한다. 지정된 시간 내에 응답이 없을 경우, 서버는 해당 연결을 비정상적인 것으로 간주하고 종료한다.

### **2.2. 클라이언트-서버 메시지 계약**

클라이언트에서 서버로 전송되는 모든 메시지는 type(문자열) 필드와 payload(객체) 필드를 포함하는 JSON 객체여야 한다.

* **authorize:** 연결 수립 직후 단 한 번 전송된다.
  * payload: { "token": "..." }
* **send\_message:** 새로운 AI 응답 스트림 생성을 요청한다.
  * payload: { "conversation\_id": "...", "input": "User message text" }
  * conversation\_id는 체크포인터에서 올바른 대화 기록을 불러오는 데 사용된다.
* **interrupt\_stream:** 현재 진행 중인 AI 응답 스트림의 즉각적인 중단을 요청한다.
  * payload: { "conversation\_id": "..." }
* **pong:** 서버의 ping에 대한 클라이언트의 응답이다.
  * payload: {}

### **2.3. 서버-클라이언트 이벤트 스트림 계약**

서버에서 클라이언트로 전송되는 모든 메시지는 event(문자열) 필드와 data(객체) 필드를 포함하는 JSON 객체여야 한다. 이 명확한 스키마는 클라이언트가 다양한 종류의 스트리밍 이벤트를 안정적으로 파싱하고 처리할 수 있도록 보장한다. 특히, 동일한 소스(LLM 출력)에서 파생되었지만 목적이 다른 stream\_token과 tts\_ready\_chunk 이벤트를 명확히 구분함으로써, 프론트엔드 개발의 복잡성을 줄이고 각 기능의 독립적인 구현을 가능하게 한다.

**표 1: WebSocket 메시지 스키마 및 이벤트 유형**

| 이벤트 유형 | 방향 | 설명 | 데이터 스키마 | 예시 |
| :---- | :---- | :---- | :---- | :---- |
| authorize\_success | S2C | 인증 성공을 확인한다. | {} | {"event": "authorize\_success", "data": {}} |
| stream\_start | S2C | 새로운 AI 응답 스트림의 시작을 알린다. | { "turn\_id": "uuid" } | {"event": "stream\_start", "data": {"turn\_id": "abc-123"}} |
| stream\_token | S2C | LLM에서 생성된 단일 토큰 또는 작은 토큰 그룹. UI의 실시간 타이핑 효과에 사용된다. | { "token": "string" } | {"event": "stream\_token", "data": {"token": "안녕하세요"}} |
| tts\_ready\_chunk | S2C | TTS 합성을 위해 준비된, 완전하고 정제된 문장 또는 절. | { "chunk": "string" } | {"event": "tts\_ready\_chunk", "data": {"chunk": "안녕하세요, 오늘 무엇을 도와드릴까요?"}} |
| tool\_call\_start | S2C | 에이전트가 도구 호출을 시작했음을 클라이언트에 알린다. | { "tool\_name": "string", "tool\_input": "object" } | {"event": "tool\_call\_start", "data": {"tool\_name": "get\_weather", "tool\_input": {"city": "Seoul"}}} |
| tool\_call\_end | S2C | 도구 호출이 완료되었음을 클라이언트에 알린다. | { "tool\_name": "string", "tool\_output": "string" } | {"event": "tool\_call\_end", "data": {"tool\_name": "get\_weather", "tool\_output": "현재 날씨는 맑습니다."}} |
| stream\_end | S2C | 현재 AI 응답 스트림의 종료를 알린다. | { "turn\_id": "uuid" } | {"event": "stream\_end", "data": {"turn\_id": "abc-123"}} |
| error | S2C | 서버 측에서 발생한 오류를 전달한다. | { "code": "int", "message": "string" } | {"event": "error", "data": {"code": 5001, "message": "도구 실행에 실패했습니다."}} |
| ping | S2C | 서버의 하트비트 신호. | {} | {"event": "ping", "data": {}} |

## **III. 비동기 이벤트 처리 코어**

이 섹션에서는 초기 프로토타입 형태의 process\_message 함수를 프로덕션 환경에 적합한, 클래스 기반의 견고한 컴포넌트로 발전시키는 방안을 상세히 기술한다. 이 컴포넌트는 단일 대화 턴의 전체 스트리밍 수명 주기를 책임지는 오케스트레이터 역할을 수행한다.

### **3.1. MessageProcessor 오케스트레이터**

제공된 async def process\_message 함수는 asyncio.Queue를 사용한 생산자-소비자 패턴의 필요성을 정확히 파악한 훌륭한 프로토타입이다. 그러나 프로덕션 환경에서는 상태와 리소스를 체계적으로 관리하기 위해 이 로직을 MessageProcessor라는 클래스로 캡슐화해야 한다. 함수 기반 접근 방식은 여러 요청이 동시에 처리될 때 상태가 섞이거나 리소스 정리가 누락될 위험이 있지만, 클래스 기반 접근 방식은 각 대화 턴에 대한 상태와 리소스를 인스턴스 내에 격리하여 이러한 문제를 원천적으로 방지한다.

**책임 및 역할:**

* 각 클라이언트 연결 또는 대화 세션별로 인스턴스화된다.
* 메시지 전송을 위한 WebSocket 객체를 관리한다.
* process\_message 함수를 대체하는 메인 진입점 메서드 async handle\_message(input\_data)를 포함한다.
* LangGraph 스트리밍 태스크의 수명 주기를 관리하며, interrupt\_stream 요청이나 클라이언트 연결 해제 시 정상적인 시작과 안전한 취소를 보장한다.
* 텍스트 처리 파이프라인 컴포넌트(TextChunkProcessor, TTSTextProcessor)의 인스턴스를 생성하고 관리한다.

**인터페이스 명세:**

Python

class MessageProcessor:
    def \_\_init\_\_(self, websocket, conversation\_id: str):
        \# WebSocket 객체, conversation\_id, 활성 태스크 추적을 위한 set 등을 초기화
       ...

    async def handle\_message(self, user\_input: str):
        \# LangGraph 스트림 생산자 및 소비자 태스크를 생성하고 실행을 감독
       ...

    async def interrupt(self):
        \# 현재 실행 중인 모든 스트리밍 관련 태스크를 안전하게 취소
       ...

    async def cleanup(self):
        \# 인스턴스와 관련된 모든 리소스를 정리 (interrupt 포함)
       ...

### **3.2. 동시성 및 태스크 관리**

비동기 시스템에서 가장 흔하게 발생하는 문제 중 하나는 예기치 않은 상황으로 인해 백그라운드 태스크가 '고아(orphaned)' 상태로 남아 리소스를 계속 소모하는 것이다. 예를 들어, process\_message 프로토타입은 LangGraph 스트림을 위한 생산자 태스크와 큐를 처리하는 소비자 태스크를 시작한다. 만약 클라이언트의 WebSocket 연결이 갑자기 끊어지면, 소비자 태스크의 websocket.send() 호출에서 예외가 발생할 것이다. 이 예외가 적절히 처리되지 않으면 소비자 태스크는 종료될 수 있지만, 생산자 태스크(LangGraph 실행)는 이를 인지하지 못하고 계속해서 실행되어 CPU와 메모리를 낭비하는 심각한 리소스 누수를 유발할 수 있다.

이러한 문제를 해결하기 위해, MessageProcessor는 자신이 생성한 모든 asyncio.Task 객체에 대한 엄격한 감독자(supervisor) 역할을 수행해야 한다. 이는 단순히 태스크를 시작하고 잊어버리는 것이 아니라, 태스크에 대한 참조를 유지하고 어떤 상황에서든(정상 종료, 오류 발생, 외부 중단 요청) 해당 태스크들이 반드시 취소되고 정리되도록 보장하는 것을 의미한다.

**구현 명세:**

* MessageProcessor는 self.active\_tasks라는 set을 유지하여 현재 활성화된 모든 태스크에 대한 참조를 저장한다.
* handle\_message 메서드는 try...finally 블록으로 전체 로직을 감싼다.
  * try 블록 내에서 생산자(LangGraph)와 소비자(WebSocket 전송) 태스크를 생성하고, 이들을 self.active\_tasks에 추가한 후, asyncio.gather 등을 사용하여 두 태스크가 완료될 때까지 대기한다.
  * finally 블록은 try 블록의 성공 여부와 관계없이 항상 실행되므로, 이곳에서 self.interrupt()를 호출하여 리소스 정리를 보장한다.
* interrupt 메서드는 self.active\_tasks를 순회하며 각 태스크에 대해 task.cancel()을 호출한다. 취소된 태스크가 완전히 종료될 때까지 await를 통해 기다려주는 것이 중요하며, 이후 self.active\_tasks를 비운다.
* 상위 계층인 WebSocket 게이트웨이는 클라이언트 연결이 종료될 때 해당 연결에 연관된 MessageProcessor 인스턴스의 interrupt() 및 cleanup() 메서드를 호출할 책임이 있다. 이 구조는 시스템이 예기치 않은 연결 끊김에 대해 매우 견고하게 대처하고, interrupt\_stream 기능을 안정적으로 구현할 수 있게 한다.

## **IV. LangGraph 상태 머신 및 스트리밍 통합**

이 섹션은 LangGraph 에이전트의 구체적인 구성 방법과, 에이전트가 생성하는 이벤트 스트림을 어떻게 소비하고 해석해야 하는지에 대한 상세 지침을 제공한다.

### **4.1. 그래프 정의 및 노드 명세**

시스템의 핵심 로직은 LangGraph의 StateGraph를 사용하여 정의된다. 그래프의 상태, 노드, 엣지는 다음과 같이 명세된다.

* **상태 (State):** 그래프의 상태는 Annotated TypedDict를 사용하여 정의되며, 최소한 messages: List 필드를 포함해야 한다. 이는 대화 기록을 상태의 일부로 관리하기 위함이다.
* **agent 노드:** 주 LLM 호출을 담당하는 노드이다. 현재 상태의 messages를 입력받아, 도구 호출(tool calls)을 포함할 수 있는 AIMessage를 반환한다.
* **tool\_executor 노드:** agent 노드에서 요청된 도구를 실행하는 노드이다. LangChain의 ToolExecutor 유틸리티를 사용하여 도구를 실행하고, 그 결과를 ToolMessage 리스트로 반환한다.
* **should\_continue 조건부 엣지 (Conditional Edge):** agent 노드의 출력을 검사하여 다음 경로를 결정하는 분기점이다.
  * agent가 반환한 AIMessage에 tool\_calls가 포함되어 있으면, tool\_executor 노드로 라우팅한다.
  * tool\_calls가 없으면, 에이전트가 최종 답변을 생성한 것으로 간주하고 그래프의 END로 라우팅한다.

### **4.2. astream\_events 출력 소비**

MessageProcessor 내의 생산자 태스크는 graph.astream\_events(..., stream\_mode="values") 제너레이터를 반복하며 이벤트를 소비한다. 각 이벤트 유형에 따라 정해진 처리를 수행해야 한다.

* **on\_chat\_model\_stream:** 스트림에서 가장 빈번하게 발생하는 이벤트로, LLM이 생성하는 텍스트 토큰을 포함한다.
  * event.data\['chunk'\].content에서 토큰 데이터를 추출한다.
  * 이 데이터는 1.2절에서 설명한 다중 경로 분기 처리의 소스가 된다.
    1. 추출된 토큰은 즉시 stream\_token WebSocket 이벤트로 포장되어 클라이언트로 전송된다.
    2. 동시에, 동일한 토큰이 TextChunkProcessor 인스턴스의 process 메서드로 전달된다.
* **on\_tool\_start:** 에이전트가 특정 도구를 호출하기 시작했음을 알리는 이벤트이다.
  * event.data\['name'\] (도구 이름)과 event.data\['input'\] (도구 입력)을 추출한다.
  * 이 정보를 사용하여 tool\_call\_start WebSocket 이벤트를 생성하고 클라이언트로 전송한다. 이는 UI에 "날씨 정보 검색 중..."과 같은 상태를 표시하는 데 사용될 수 있다.
* **on\_tool\_end:** 도구 실행이 완료되었음을 알리는 이벤트이다.
  * event.data\['output'\] (도구 실행 결과)을 추출하여 tool\_call\_end WebSocket 이벤트를 생성하고 전송한다. 이 정보는 디버깅이나 UI에 상세 정보를 표시하는 데 사용될 수 있다.
* **기타 이벤트:** on\_chain\_start, on\_chain\_end 등 다른 이벤트들은 클라이언트 UI에 특별히 표시할 필요가 없다면, 서버 측 디버깅을 위해 로그로 기록하는 것을 권장한다.

### **4.3. 체크포인팅 및 상태 영속성**

다회성 대화(multi-turn conversation)를 지원하기 위해, 영속성 있는 체크포인터의 사용이 필수적으로 요구된다.

* **명세:** 개발 환경에서는 인메모리 MemorySaver가 유용하지만, 프로덕션 환경에서는 반드시 RedisSaver와 같은 외부 영속성 저장소를 사용해야 한다. Redis 연결 정보는 환경 변수를 통해 관리되어야 한다.
* **상태 연결:** LangGraph의 stream, invoke 등의 메서드를 호출할 때, configurable 딕셔너리를 사용하여 대화 상태를 지정해야 한다. 이 딕셔너리는 {"configurable": {"thread\_id": conversation\_id}} 형태로 구성된다. 여기서 conversation\_id는 클라이언트가 send\_message 페이로드에 담아 보낸 값으로, 이를 통해 WebSocket 세션을 영속적인 대화 기록과 정확하게 연결할 수 있다.

## **V. 실시간 텍스트 처리 파이프라인**

이 섹션에서는 제공된 텍스트 처리 클래스들의 로직을 분석하고 개선하여, 프로덕션 수준의 안정성과 확장성을 갖춘 컴포넌트로 재설계하는 방안을 제시한다.

### **5.1. TextChunkProcessor 상세 명세**

초기 프로토타입의 TextChunkProcessor는 버퍼를 사용하여 문장 조각을 처리하는 올바른 접근 방식을 취하고 있다. 그러나 더 견고하고 예측 가능한 동작을 위해 알고리즘을 다음과 같이 개선해야 한다.

**개선된 알고리즘:**

1. process 메서드는 입력받은 토큰을 내부 self.buffer에 추가한다.
2. 버퍼 내에서 문장 종결자(예: '.', '?', '\!')를 검색하되, 가장 *마지막*에 나타나는 종결자의 위치를 찾는다. 이는 하나의 토큰 묶음에 여러 문장이 포함된 경우를 올바르게 처리하기 위함이다.
3. 종결자가 발견되면, 해당 위치를 기준으로 버퍼를 분리한다. 종결자를 포함한 앞부분은 클라이언트에 전달할 완전한 청크(chunk\_to\_yield)가 된다. 종결자 뒷부분은 다음 처리를 위해 새로운 self.buffer가 된다.
4. chunk\_to\_yield를 yield 키워드를 통해 반환한다. 이 과정은 버퍼 내에 더 이상 종결자가 없을 때까지 반복된다.
5. flush 메서드가 추가되어야 한다. 이 메서드는 전체 스트림이 끝났을 때 호출되며, 버퍼에 남아있는 모든 텍스트 조각을 마지막 청크로 반환한다. 이는 "감사합니다"와 같이 문장 부호 없이 끝나는 문장이 유실되는 것을 방지한다.

**상태 관리의 중요성:**

TextChunkProcessor는 self.buffer라는 내부 상태를 가지는 상태 기반(stateful) 컴포넌트이다. LangGraph 스트림은 주 LLM의 응답뿐만 아니라, 도구 실행 결과와 같은 다양한 소스에서 텍스트를 생성할 수 있다. 예를 들어, 도구 결과로 "현재 날씨는 맑습니다."라는 텍스트가 나오고, 이어서 LLM이 "따라서 외출하기 좋은 날씨입니다."라고 응답하는 경우를 생각해보자. 만약 단 하나의 TextChunkProcessor 인스턴스가 계속 사용된다면, "맑습니다."와 "따라서"가 의미적으로 무관함에도 불구하고 하나의 문장으로 잘못 결합될 위험이 있다.

이러한 문제를 방지하기 위해, MessageProcessor는 TextChunkProcessor의 인스턴스 수명 주기를 적극적으로 관리해야 한다. 즉, 의미적으로 연속된 텍스트 블록이 시작될 때마다(예: on\_chat\_model\_start 이벤트 발생 시) *새로운* TextChunkProcessor 인스턴스를 생성해야 한다. 그리고 해당 텍스트 블록이 끝나면(예: on\_chat\_model\_end 이벤트 발생 시) 생성했던 인스턴스의 flush() 메서드를 호출하여 남은 데이터를 처리하고 인스턴스를 폐기해야 한다. 이 방식은 각기 다른 출처의 텍스트 조각들이 서로 섞이는 것을 원천적으로 차단하여 데이터 처리의 정확성을 보장한다.

**API 명세:**

Python

class TextChunkProcessor:
    def \_\_init\_\_(self, terminators: List\[str\] \= \['.', '?', '\!'\]):...
    def process(self, token: str) \-\> Generator\[str, None, None\]:...
    def flush(self) \-\> str | None:...

### **5.2. TTSTextProcessor 상세 명세**

초기 프로토타입의 TTSTextProcessor는 필터링 규칙이 코드에 하드코딩되어 있어 확장성과 유지보수성이 떨어진다. 이를 개선하기 위해 규칙 기반의 설정 가능한(configurable) 설계로 변경해야 한다.

**개선된 설계:**

* 필터링 로직은 정규식(regular expression) 패턴과 그에 대한 대체 문자열의 목록을 기반으로 동작하도록 재설계한다. 이 규칙 목록은 외부 설정 파일(예: YAML, JSON)로부터 로드되어야 한다. 이 접근 방식은 다음과 같은 장점을 가진다.
  * 숫자 정규화(예: '123' \-\> '백이십삼'), 약어 확장(예: 'AI' \-\> '인공지능') 등 더 복잡하고 정교한 규칙을 쉽게 추가할 수 있다.
  * 엔지니어가 아닌 기획자나 언어 전문가도 설정 파일을 직접 수정하여 필터링 동작을 변경할 수 있다.
* **설정 파일 예시 (YAML):**
  YAML
  \- pattern: '\\(웃음\\)'
    replacement: ''
  \- pattern: '음...'
    replacement: ''
  \- pattern: 'AI'
    replacement: '인공지능'

* **상태 비저장(Stateless) 설계:** TextChunkProcessor와 달리, TTSTextProcessor는 상태를 가지지 않는(stateless) 컴포넌트로 설계되어야 한다. process 메서드는 완전한 텍스트 청크 하나를 입력받아, 모든 규칙을 적용한 후 완전히 처리된 청크 하나를 반환해야 한다. 이는 파이프라인 내에서의 통합을 단순화하고 예측 가능성을 높인다.

**API 명세:**

Python

class TTSTextProcessor:
    def \_\_init\_\_(self, rules\_config\_path: str):...
    def process(self, text\_chunk: str) \-\> str:...

### **5.3. 파이프라인 통합 및 역압력(Backpressure)**

MessageProcessor의 소비자 태스크는 정의된 텍스트 처리 파이프라인을 조율하는 역할을 한다. TextChunkProcessor가 청크를 yield하면, 해당 청크는 즉시 TTSTextProcessor.process() 메서드로 전달된다. 그 결과물은 tts\_ready\_chunk WebSocket 이벤트로 포장되어 클라이언트로 전송된다.

**역압력 메커니즘:**

LangGraph 스트림은 네트워크나 클라이언트 처리 속도보다 훨씬 빠르게 토큰을 생성할 수 있다. 프로토타입의 asyncio.Queue는 이러한 속도 차이를 완충하는 역할을 하지만, 만약 큐의 크기에 제한이 없다면 심각한 문제를 야기할 수 있다. 생산자(LangGraph)가 소비자(네트워크 전송)보다 월등히 빠를 경우, 큐에 처리되지 않은 데이터가 무한정 쌓이게 되어 서버의 메모리를 모두 소진시키는 결과를 초래할 수 있다.

이러한 메모리 고갈 문제를 방지하기 위해, 시스템은 반드시 역압력 메커니즘을 구현해야 한다. asyncio.Queue는 이를 위한 간단하고 효과적인 방법을 제공한다.

* **구현:** asyncio.Queue를 초기화할 때 maxsize 매개변수를 설정한다 (예: asyncio.Queue(maxsize=100)).
* **동작:** 큐가 가득 차면(maxsize에 도달하면), 생산자 태스크의 await queue.put(item) 호출은 자동으로 블로킹(blocking)된다. 즉, 큐에 여유 공간이 생길 때까지 더 이상 새로운 아이템을 추가하지 않고 대기하게 된다.
* **효과:** 이 블로킹 동작이 LangGraph의 astream\_events 이터레이터 소비를 자연스럽게 일시 중지시킨다. 결과적으로 LLM이 클라이언트 측의 데이터 소비 속도를 앞질러 너무 멀리 나아가는 것을 방지하고, 전체 시스템의 데이터 흐름 속도를 조절하여 메모리 사용량을 안정적으로 유지한다. 이는 시스템의 안정성을 보장하는 핵심적인 안전장치이다.

## **VI. 시스템 복원력 및 운영 준비성**

이 섹션은 시스템을 작동하는 프로토타입에서 신뢰할 수 있는 프로덕션 서비스로 전환하기 위해 필요한 비기능적 요구사항들을 정의한다.

### **6.1. 포괄적인 오류 처리**

* **WebSocket 계층:** 서버는 클라이언트의 갑작스러운 연결 해제를 정상적으로 처리해야 한다. 연결 종료가 감지되면, 해당 연결과 연관된 MessageProcessor.cleanup() 메서드를 즉시 호출하여 모든 관련 리소스(예: asyncio 태스크)가 깨끗하게 정리되도록 보장해야 한다.
* **LangGraph 계층:**
  * **노드 실패:** 그래프 내의 노드(특히 외부 API를 호출하는 도구)가 실패하면(예: 타임아웃, API 오류), astream\_events는 예외를 발생시킨다. MessageProcessor는 이 예외를 반드시 try...except 블록으로 포착해야 한다.
  * **시스템 응답:** 예외를 포착한 MessageProcessor는 표 1에 정의된 스키마에 따라 구조화된 error 이벤트를 클라이언트에 전송해야 한다. 오류를 전송한 후에는 즉시 모든 내부 리소스를 정리(cleanup)해야 한다. 중요한 것은, 오류가 발생했다고 해서 WebSocket 연결 자체를 끊어서는 안 된다는 점이다. 이를 통해 사용자는 오류를 인지한 후, 다시 메시지를 보내 시도할 수 있는 기회를 갖게 된다.
* **오류 코드:** 시스템은 예측 가능한 오류에 대해 표준화된 코드를 정의해야 한다. (예: 5001: 도구 실행 실패, 5002: LLM 생성 오류, 4001: 잘못된 입력 값)

### **6.2. 구조화된 로깅 및 관측 가능성(Observability)**

* **로깅:** 모든 로그 메시지는 반드시 구조화된 형식(예: JSON)으로 출력되어야 한다. 각 로그 항목에는 conversation\_id와 turn\_id가 포함되어, 특정 요청이 시스템의 여러 컴포넌트를 거치는 전체 과정을 쉽게 추적할 수 있어야 한다.
* **핵심 메트릭:** 시스템의 상태와 성능을 지속적으로 모니터링하기 위해, 다음과 같은 핵심 메트릭들을 Prometheus/Grafana와 같은 모니터링 시스템으로 노출해야 한다.
  * websocket\_active\_connections (Gauge): 현재 활성화된 클라이언트 연결 수.
  * turn\_processing\_latency\_seconds (Histogram): send\_message 수신부터 stream\_end 전송까지 걸린 총 처리 시간 분포.
  * time\_to\_first\_token\_seconds (Histogram): send\_message 수신부터 *첫 번째* stream\_token 전송까지 걸린 시간 분포. 이는 사용자가 인지하는 응답성의 핵심 지표이다.
  * langgraph\_node\_errors\_total (Counter): 그래프 노드에서 발생한 오류 총계. node\_name 레이블을 통해 어떤 노드에서 오류가 자주 발생하는지 식별할 수 있어야 한다.
  * events\_processed\_total (Counter): 클라이언트로 전송된 이벤트 총계. event\_type 레이블을 통해 이벤트 유형별 분포를 파악할 수 있어야 한다.
