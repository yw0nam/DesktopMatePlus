

# **프로젝트 청사진: LangGraph, Fish Speech, 컨텍스트 인지 기능을 탑재한 지능형 데스크톱 컴패니언**

## **Part I: 제품 요구사항 문서 (PRD)**

### **섹션 1: 제품 비전 및 핵심 원칙**

#### **1.1. 개요**

본 문서는 "DesktopMate-Plus"(가칭)로 명명된 지능형, 컨텍스트 인지 데스크톱 컴패니언의 기술 및 제품 사양을 정의합니다. 이 프로젝트는 단순히 애니메이션 마스코트를 넘어, 상태 기반 대화형 에이전트(LangGraph) 1, 로컬 기반의 표현력 풍부한 텍스트 음성 변환(TTS) 2, 그리고 사용자의 디지털 환경을 이해하기 위한 혁신적인 디스플레이 인식 모듈을 통합하여, 능동적이고 개인화된 사용자 보조 장치를 만드는 것을 목표로 합니다.3

#### **1.2. 제품 비전**

단순히 반응하는 것을 넘어 *능동적으로* 행동하는 데스크톱 컴패니언을 창조하는 것이 본 프로젝트의 비전입니다. 사용자가 현재 사용 중인 애플리케이션, 읽고 있는 텍스트, 수행 중인 작업 등 현재의 컨텍스트를 이해하고, 이를 바탕으로 의미 있는 지원, 교감, 정보를 제공할 수 있는 AI 개체를 구현하고자 합니다.

#### **1.3. 핵심 원칙**

* **개인정보 보호 우선 아키텍처 (Privacy-First Architecture):** LLM 추론(LangGraph) 및 TTS(Fish Speech)를 포함한 모든 핵심 AI 처리는 로컬에서 수행됩니다. 이는 사용자 데이터가 사용자의 기기 내에만 머무르도록 보장하기 위한 근본적인 설계 원칙입니다.5  
* **저지연 상호작용 (Low-Latency Interaction):** 아키텍처는 실시간 상호작용에 최적화되어야 합니다. 경량 프레임워크와 로컬 모델을 선택하는 것은 음성 및 채팅 응답 시간을 최소화하는 데 핵심적인 역할을 합니다.  
* **심층 개인화 (Deep Personalization):** 컴패니언은 외형(Mate Engine과 같이 커스텀 VRM 모델 지원) 7, 목소리(Fish Speech의 음성 복제 기능 활용) 8, 나아가 성격 및 지식 기반에 이르기까지 고도로 맞춤화할 수 있어야 합니다.  
* **컨텍스트 인지 (Contextual Awareness):** 기존 데스크톱 마스코트에서는 불가능했던 새로운 차원의 상호작용을 가능하게 하는, 사용자의 디지털 환경을 인식하고 이해하는 능력이 이 제품의 핵심 차별점입니다.

#### **1.4. 목표 고객**

개인정보 보호, 성능, 그리고 최첨단 기능을 중시하는 기술에 정통한 사용자, 개발자, 콘텐츠 제작자 및 AI 애호가를 주요 목표 고객으로 설정합니다.

### **섹션 2: 기반 아키텍처 및 기술 스택**

#### **2.1. 아키텍처 개요**

애플리케이션은 렌더링과 사용자 입력을 담당하는 경량 프론트엔드 셸과 모든 AI/ML 연산을 관리하는 강력한 백엔드 "사이드카(Sidecar)" 프로세스로 구성된 분리된 2-프로세스 모델을 기반으로 합니다. 이러한 관심사의 분리는 성능, 안정성 및 모듈식 개발에 매우 중요합니다.

#### **2.2. GUI 프레임워크 선택: Tauri**

Tauri는 Electron과 같은 대안에 비해 훨씬 작은 번들 크기(약 2.5MB 대 85MB), 더 빠른 시작 시간, 낮은 RAM 사용량, 그리고 강화된 보안 모델을 제공하므로 GUI 프레임워크로 채택합니다.9 Tauri는 OS의 네이티브 웹뷰를 활용하여 전체 크로미움 인스턴스를 번들에 포함할 필요가 없습니다.10 이로 인해 플랫폼 간 렌더링에 사소한 불일치가 발생할 수 있지만, 지속적으로 실행되는 경량 컴패니언 앱의 경우 성능 및 보안상의 이점이 훨씬 더 중요합니다. 프론트엔드는 Tauri의 개발 환경과 호환되는 최신 JavaScript 프레임워크(예: React, Vue, Svelte)를 사용하여 구축될 것이며, Tauri는 프레임워크에 구애받지 않으므로 선택의 유연성이 있습니다.9

#### **2.3. 백엔드 통합: Python 사이드카**

핵심 AI 로직(LangGraph, Fish Speech API 서버, 디스플레이 인식)은 Python 기반입니다. 이를 Rust 기반의 Tauri 셸과 통합하는 가장 효과적인 방법은 "사이드카" 패턴을 사용하는 것입니다.12 이 방식은 PyInstaller와 같은 도구를 사용하여 종속성과 로컬 API 서버(예: FastAPI)를 포함한 전체 Python 백엔드를 단일 실행 파일로 패키징하는 것을 포함합니다.12

메인 Tauri(Rust) 애플리케이션은 애플리케이션 시작 및 종료 시 Python 사이드카 프로세스를 생성, 모니터링 및 종료하는 역할을 담당합니다.12 이를 통해 백엔드는 메인 애플리케이션이 활성화되어 있을 때만 실행되어 고아 프로세스(orphan process) 발생을 방지합니다. 컴파일된 Python 실행 파일의 경로는 tauri.conf.json 파일의 tauri.bundle.externalBin에 명시되며, Rust 백엔드는 Command::new\_sidecar를 사용하여 여러 플랫폼에서 안정적으로 이 바이너리를 찾아 실행합니다.13

#### **2.4. 프로세스 간 통신 (IPC)**

* **프론트엔드 → 백엔드:** JavaScript 프론트엔드는 Tauri Rust 코어를 통해 Python 백엔드와 통신합니다. 프론트엔드는 Tauri의 invoke API를 사용하여 Rust 함수에 요청을 보냅니다.12  
* **Rust → Python:** Rust 레이어는 이 요청을 Python 사이드카로 전달합니다. 권장되는 통신 프로토콜은 Python 프로세스 내에서 실행되는 로컬 HTTP 서버(예: FastAPI 사용)입니다.14 Rust는 미리 정해진 포트의 localhost로 HTTP 요청을 보낼 수 있으며, 이는 복잡한 데이터 구조를 처리하는 데 있어 직접적인 표준 입출력(stdin/stdout) 통신보다 더 안정적이고 유지보수가 용이합니다.  
* **Python → 프론트엔드 (이벤트):** 컴패니언이 스스로 말하기로 결정하는 등 능동적인 이벤트의 경우, Python 백엔드는 HTTP를 통해 Rust 코어에 메시지를 보낼 수 있으며, Rust는 Tauri의 emit 함수를 사용하여 JavaScript 프론트엔드로 이벤트를 전송합니다.13

이 Tauri와 Python 사이드카 패턴의 조합은 단순히 기술적인 선택을 넘어, 전체 프로젝트를 실현 가능하고 견고하게 만드는 핵심적인 아키텍처 결정입니다. 이는 무거운 Python 기반 AI 스택을 현대적이고 고성능인 데스크톱 UI 프레임워크와 통합하는 어려운 과제를 우아하게 해결합니다. 이 아키텍처는 완벽한 격리를 제공하여 UI가 AI를 충돌시키거나 AI의 무거운 처리가 UI 스레드를 차단하는 것을 방지하며, 프론트엔드와 백엔드 구성 요소의 독립적인 개발 및 테스트를 가능하게 합니다.

#### **2.5. 백엔드 연동 원칙(참고)**

앱이 백엔드와 상호작용할 때 따라야 할 제약과 기대치를 정리합니다(Develop/backend의 개발 패턴 반영).

* **Stateless 호출:** 모든 HTTP 호출은 무상태로 설계되며, 대화 상태는 thread_id로만 식별됩니다. 대화 맥락 자체를 앱에서 전달하려 하지 않습니다.  
* **Search-Before-Act:** 백엔드는 응답 생성 전에 항상 메모리를 검색합니다. 동일 사용자 요청을 빠르게 연속 호출할 경우에도 이 정책이 유지됨을 전제로 UX를 설계합니다.  
* **Read-then-Write:** 사용자가 기존 정보 변경/삭제를 요구하는 UX가 있다면, 백엔드는 먼저 검색으로 대상 메모리를 식별한 뒤 갱신/삭제합니다. 앱은 식별자 직접 편집을 노출하지 않습니다.  
* **리소스 경계:** GPU가 필요한 모델은 별도 로컬 서버로 동작하며, 앱은 서버 준비 시간(초기 로딩)을 고려한 로딩 UI를 제공합니다.  

#### **표 2.1: 데스크톱 애플리케이션 프레임워크 비교**

| 기능 | Tauri | Electron | PyQt |
| :---- | :---- | :---- | :---- |
| **번들 크기** | 매우 작음 (약 2-5 MB) 9 | 큼 (약 80-120 MB 이상) 9 | 중간 |
| **메모리 사용량** | 낮음 9 | 높음 11 | 중간 |
| **성능** | 우수 (네이티브 웹뷰 사용) 9 | 보통 (Chromium 번들) 11 | 우수 (네이티브 컴파일) |
| **보안** | 우수 (기본적으로 API 제한) 9 | 보통 (Node.js API 전체 접근) 9 | 우수 |
| **백엔드 언어** | Rust 9 | JavaScript (Node.js) 9 | Python |
| **Python 통합** | 사이드카 패턴으로 우수 12 | 프로세스 생성 또는 API 통신 필요 | 네이티브 |
| **커뮤니티/생태계** | 성장 중 10 | 매우 큼 11 | 큼 |
| **UI 일관성** | OS에 따라 약간의 차이 발생 가능 10 | 매우 높음 (Chromium 기반) 17 | OS 네이티브 룩앤필 제공 11 |

### **섹션 3: 컴패니언 개체: 핵심 기능 및 상호작용**

#### **3.1. 캐릭터 렌더링**

애플리케이션은 가상 아바타의 표준 형식인 .VRM 형식의 3D 캐릭터 모델을 로드하고 렌더링할 수 있어야 합니다. 이는 Mate Engine과 같은 오픈소스 대안에서도 지원되며, 사용자에게 높은 수준의 커스터마이징을 제공합니다.4 렌더링은 프론트엔드에서 Three.js나 Babylon.js와 같은 WebGL 기반 라이브러리를 사용하여 처리됩니다.

#### **3.2. 애니메이션 및 행동 시스템**

컴패니언은 다음과 같은 상태를 포함하는 애니메이션 상태 머신을 가집니다: 유휴 애니메이션, 사용자 입력(예: 마우스 오버, 클릭)에 대한 반응, 특정 작업(예: LangGraph 처리 중 '생각하는' 애니메이션)을 위한 스크립트 애니메이션. 이는 마우스 커서와 상호작용하거나 창 위에 앉는 등의 기능을 포함하는 Desktop Mate의 기능 세트를 기반으로 하며 3, 음악에 맞춰 춤을 추거나 더 복잡한 추적 기능을 제공하는 Mate Engine의 고급 기능을 향후 버전에서 고려할 수 있습니다.7

#### **3.3. 데스크톱 상호작용 로직**

컴패니언은 데스크톱 환경을 인식하고 상호작용할 수 있어야 합니다.

* **창 인지:** 캐릭터는 열려 있는 창의 경계를 식별하고 창 상단에 앉는 등 창과 관련된 동작을 수행할 수 있습니다.3 이는 디스플레이 인식 모듈(섹션 6)에서 창 좌표를 가져와 구현됩니다.  
* **커서 추적:** 캐릭터의 머리와 눈은 사용자의 마우스 커서를 따라 움직여야 하며, 이는 Desktop Mate와 Mate Engine 모두에 있는 기능입니다.3

### **섹션 4: 대화 엔진: LangGraph 에이전트 아키텍처**

#### **4.1. LangGraph 채택의 논리**

사용자가 LangGraph를 선택한 것은 현명한 결정입니다. LangGraph는 상태 기반의 순환적이고 제어 가능한 AI 에이전트를 생성할 수 있게 해주며, 이는 단순한 질의응답을 넘어 환경을 인식하고, 추론하며, 행동해야 하는 컴패니언에게 필수적입니다.1

#### **4.2. 제안된 상태 그래프: "인지 사이클"**

에이전트의 핵심 로직은 인지 루프를 나타내는 그래프가 될 것입니다.

* **노드 (Nodes):**  
  * WaitForTrigger: 사용자 발화, 예약된 이벤트 또는 상황적 신호를 기다리는 기본 유휴 상태입니다.  
  * PerceiveEnvironment: 사용자의 데스크톱 현재 상태를 이해하기 위해 get\_screen\_context 도구(섹션 6)를 호출합니다.  
  * UpdateMemory: 새로운 인식 정보를 기존 대화 기록 및 사용자 프로필과 통합합니다.  
  * ReasonAndPlan: 핵심 LLM 노드입니다. 현재 상태와 인식 정보를 입력으로 받아 다음 행동(예: 응답 생성, 명확화 질문, 무반응)을 결정합니다.  
  * GenerateResponse: 계획이 '말하기'일 경우, 이 노드는 TTS 엔진을 위한 텍스트를 생성합니다.  
  * ExecuteAction: 향후 기능(예: UI 조작 수행)을 위한 라우터 노드입니다.  
* **엣지 (Edges):**  
  * 조건부 엣지가 광범위하게 사용됩니다. 예를 들어, ReasonAndPlan 이후, 발화가 필요하면 GenerateResponse로 라우팅되고, 에이전트가 침묵하기로 결정하면 WaitForTrigger로 다시 돌아갑니다.1

#### **4.3. 도구 통합**

MVP의 주요 도구는 get\_screen\_context가 될 것입니다. 이 도구는 Python 백엔드에서 구현되어 LangGraph 에이전트에게 제공됩니다.19 이 도구는 에이전트의 "정신"과 "감각"을 연결하는 다리 역할을 하며, 모든 컨텍스트 인지 기능을 가능하게 합니다.

#### **4.4. 메모리 관리**

* **단기 기억:** LangGraph의 GraphState가 현재 대화 기록을 유지합니다.18  
* **장기 기억:** 벡터 데이터베이스를 사용하여 사용자 선호도, 과거 대화의 핵심 사실, 사용자 활동 요약 등을 저장하여, 컴패니언이 시간에 따라 사용자에 대한 지속적인 이해를 구축할 수 있도록 합니다.

LangGraph를 요구한 것은 단순한 "채팅 기능" 이상의 의미를 가집니다. LangGraph의 아키텍처는 공식적인 인지 사이클(예: 관찰-판단-결정-행동, OODA 루프)을 구현하는 데 완벽하게 적합합니다. 이는 프로젝트를 단순한 챗봇에서 진정한 자율 에이전트로 격상시킵니다. PerceiveEnvironment 노드는 "관찰"에, ReasonAndPlan 노드는 "판단"과 "결정"에, GenerateResponse 노드는 "행동"에 해당합니다. 따라서 구현은 단순한 "채팅 루프" 그래프가 아니라, 에이전트가 지속적으로 환경을 인식하고 행동 여부를 결정하는 인지 아키텍처로 설계되어야 합니다. 이 프레임워크는 향후 개발을 위한 훨씬 더 강력하고 확장 가능한 기반을 제공합니다.

### **섹션 5: 컴패니언의 목소리: 로컬 TTS 통합**

#### **5.1. 기술 선택: Fish Speech (OpenAudio)**

사용자가 지정한 Fish Speech는 로컬에서 실행할 수 있는 강력한 다국어 TTS 모델입니다.2 이는 개인정보 보호 우선 원칙과 일치합니다. 프로젝트는 낮은 리소스 요구 사항을 고려하여 OpenAudio S1-mini 모델(0.5B 파라미터)을 시작점으로 사용하되, 고사양 하드웨어를 가진 사용자를 위해 전체 4B 파라미터 모델도 지원할 것입니다.2

#### **5.2. 로컬 API 서버 구현**

Python 사이드카는 Fish Speech HTTP API 서버를 실행하는 역할을 담당합니다.2 문서는 로컬 포트(예: 8080)에서 수신 대기하는 서버를 시작하는 명확한 지침을 제공합니다.2 LangGraph 에이전트는 발화하기로 결정하면 생성된 텍스트와 함께 이 로컬 API 엔드포인트에 POST 요청을 보냅니다.

#### **5.3. 동적이고 표현력 있는 음성**

Fish Speech의 핵심 기능 중 하나는 감정 및 톤 마커(예: (whispering), (excited), (sarcastic))를 지원하는 것입니다.2 ReasonAndPlan 노드의 LLM은 이러한 마커를 텍스트 출력에 포함하도록 프롬프트되어, 컴패니언의 음성 전달이 메시지 내용과 일치하도록 합니다.

#### **5.4. 주요 기능: 제로샷 음성 복제를 통한 개인화**

Fish Speech는 10-30초의 짧은 오디오 샘플로 맞춤형 음성을 생성하는 기능을 지원합니다.2 애플리케이션은 이 프로세스를 위한 사용자 친화적인 인터페이스를 포함할 것입니다. "음성 설정" 패널에서 사용자는 짧은 오디오 클립을 녹음할 수 있으며, 이 클립은 로컬 Fish Speech API로 전송되어 이후 모든 TTS 생성의 참조로 사용됩니다.

Fish Speech의 음성 복제 기능은 단순한 기믹이 아닙니다. 사용자에게 깊은 개인화와 정서적 유대감을 형성할 수 있는 혁신적인 기능입니다. 이는 컴패니언을 도구에서 사용자 정의된 고유한 정체성을 가진 진정한 디지털 개체로 격상시킵니다. 사용자가 자신의 목소리, 친구의 목소리 또는 가상 캐릭터의 목소리를 컴패니언에게 부여할 수 있게 함으로써, 이는 친숙함과 연결에 대한 인간의 근본적인 욕구를 직접적으로 충족시킵니다. 따라서 음성 복제 워크플로우는 숨겨진 기능이 아니라, 애플리케이션의 온보딩 및 개인화 설정의 핵심 부분으로, 주요 차별점으로 마케팅되어야 합니다.

### **섹션 6: 환경 인지: 디스플레이 인식 모듈**

#### **6.1. 문제 정의**

컴패니언은 관련성 있고 능동적인 상호작용을 위해 사용자의 현재 화면의 시각적 컨텍스트를 비침입적으로 인식할 수 있어야 합니다. 이는 게임 화면, 비디오, 디자인 소프트웨어 등 기존 UI 요소 추출 방식으로는 파악하기 어려운 일반적인 시각 정보를 포함합니다.

#### **6.2. 접근 방식 분석**

* **방법 고성능 화면 캡처 \+ 로컬 VLM(Vision Language Model).** 주기적으로 화면을 캡처하여 로컬에서 실행되는 VLM에 이미지를 직접 전달하여 시각적 컨텍스트에 대한 자연어 설명을 얻는 방식입니다.  
  * *장점:* 매우 일반적이고 강력합니다. 텍스트, UI 요소뿐만 아니라 게임 상황, 이미지, 비디오 등 화면의 모든 시각적 내용을 이해할 수 있습니다. 이는 프로젝트의 '컴패니언' 비전을 실현하는 데 필수적입니다.  
  * *단점:* 높은 리소스(특히 VRAM)를 요구하며, VLM 추론으로 인한 지연 시간이 발생할 수 있습니다.

#### **6.3. 권장 구현: 고성능 캡처 및 경량 VLM 파이프라인**

Python 백엔드는 화면의 시각적 정보를 실시간에 가깝게 처리하기 위한 최적화된 파이프라인을 구현합니다.

* **고성능 화면 캡처:** 지연 시간을 최소화하기 위해 가장 빠른 화면 캡처 라이브러리를 사용합니다.  
  * **Windows:** DXcam은 GPU를 직접 활용하여 기존 방식보다 월등히 빠른 캡처 속도(중급 PC에서 약 100 FPS)를 제공하므로 Windows 환경의 기본 선택지가 됩니다.25  
  * **macOS/Linux:** MSS는 여러 플랫폼에서 안정적으로 우수한 성능을 보여주는 검증된 라이브러리입니다.25  
* **로컬 VLM 선택 및 서빙:** 개인정보 보호 및 저지연 원칙을 위해, 경량화된 오픈소스 VLM을 외부서버에서 실행하거나 OpenAI같은 provider에게 요청합니다.
  * **서빙 프레임워크:** 외부 서버에서 API를 통해 통신하며, OpenAI와 호환되는 API 엔드포인트를 제공하여 LangGraph 에이전트가 VLM을 도구로 쉽게 호출할 수 있도록 합니다.

#### **6.4. 컨텍스트 데이터 구조**

get\_screen\_context 도구는 LangGraph 에이전트에게 VLM이 생성한 시각적 분석 결과를 포함하는 다음과 같은 구조화된 JSON 객체를 반환합니다:

JSON

{  
  "active\_app\_name": "League of Legends",  
  "active\_window\_title": "League of Legends",  
  "visual\_description": "A team fight is happening in the mid-lane near the river. The user's champion, Lux, is low on health and is positioned behind their tank. The enemy team is pushing aggressively."  
}

**설계 결정의 근거: "도구"에서 "동반자"로의 전환**

사용자의 통찰력 있는 제안에 따라, 디스플레이 인식 방식을 접근성 API에서 VLM으로 전환하는 것은 이 프로젝트의 방향성을 '유용한 도구'에서 진정한 '지능형 동반자'로 격상시키는 핵심적인 전략적 결정입니다. 접근성 API는 구조화된 데이터를 효율적으로 추출하는 데 뛰어나지만, 게임, 동영상, 그래픽 편집 등 현대 컴퓨팅 환경의 대부분을 차지하는 비정형 시각 정보 앞에서는 무력합니다.

VLM을 채택함으로써, 우리는 컴패니언에게 '눈'을 제공하여 화면의 의미론적, 상황적 맥락을 이해할 수 있게 합니다. 이는 단순히 "오류 메시지를 읽어줘"라는 요청을 넘어, "게임 상황이 불리해 보이는데, 후퇴하는 게 어때?"와 같은 능동적이고 깊이 있는 상호작용을 가능하게 합니다. DXcam과 같은 고속 캡처 기술과 양자화된 경량 VLM의 발전은 과거에는 불가능했던 로컬 기반의 실시간 시각 인지를 현실적인 목표로 만들었습니다.25 이 접근 방식은 더 많은 기술적 과제를 수반하지만, 프로젝트의 비전을 달성하고 사용자에게 전례 없는 경험을 제공하기 위한 필수적인 진화입니다.

#### **표 6.2: 디스플레이 인식 방법 비교**

| 지표 | 접근성 API | 화면 캡처 \+ VLM |
| :---- | :---- | :---- |
| **성능 (CPU/RAM)** | 매우 낮음, 효율적 20 | 중간 (캡처 오버헤드) |
| **VRAM 사용량** | 거의 없음 | 높음 (모델 로딩 필요) 30 |
| **지연 시간** | 거의 즉시 | 중간 (VLM 추론 시간) |
| **데이터 품질** | 구조화된 데이터 (유형, 상태) 23 | 비구조화된 자연어 설명 |
| **다용도성/일반성** | 낮음 (표준 UI에 제한됨) | 매우 높음 (게임, 비디오 등 모두 인식) |
| **구현 복잡성** | 중간 (플랫폼별 래퍼 필요) | 높음 (VLM 서빙 및 최적화 필요) |

### **섹션 7: 종합 기능 목록 및 사용자 스토리**

#### **7.1. 기능 목록 (MVP → V1)**

* **코어:** Tauri 기반 데스크톱 애플리케이션, Python 사이드카 프로세스 관리.  
* **컴패니언:** 커스텀 VRM 모델 로드, 유휴 애니메이션, 커서 추적, 창 위에 앉기.  
* **대화:** 실시간 채팅 인터페이스, LangGraph 기반 대화 루프.  
* **음성:** Fish Speech API를 통한 로컬 TTS, 감정 마커를 사용한 표현력 있는 음성.  
* **컨텍스트:** 활성 애플리케이션 및 창 제목 식별, 화면의 시각적 내용에 대한 VLM 기반 설명 생성.

#### **7.2. 사용자 스토리**

* **코드를 디버깅하는 개발자로서,** 복사할 수 없는 오류 대화 상자의 텍스트를 읽어주도록 "이 오류 메시지가 뭐라고 해?"라고 컴패니언에게 물어보고 싶다.  
* **문서 작업을 하는 작가로서,** 내가 10분 동안 아무 활동이 없으면 컴패니언이 이를 인지하고 "휴식 중이신 것 같네요. 집중력을 높이는 음악을 틀어드릴까요?"라고 능동적으로 물어봐 주었으면 한다.  
* **사용자로서,** 내 목소리가 담긴 15초짜리 오디오 클립을 제공하여 컴패니언이 친숙하고 개인적인 목소리로 나에게 말하게 하고 싶다.  
* **연구 논문을 읽는 학생으로서,** 단락을 강조 표시하고 컴패니언에게 "이거 간단하게 설명해 줘"라고 요청하여 화면의 텍스트를 설명의 맥락으로 사용하게 하고 싶다.  
* **게임을 플레이하는 사용자로서,** 내 캐릭터가 위험한 상황에 처했을 때 컴패니언이 화면을 보고 "뒤에 적이 나타났어요\! 조심하세요\!"라고 능동적으로 경고해주었으면 한다.

---

## **Part II: 개발 로드맵**

### **섹션 8: 1단계 \- 기반 구축 및 최소 기능 제품(MVP) (예상 4-6 스프린트)**

* **목표:** 핵심 아키텍처 파이프라인을 구축하고 기본적인 상호작용이 가능한 컴패니언을 제공합니다. Tauri/사이드카 아키텍처와 핵심 AI 통합을 검증하는 데 중점을 둡니다.  
* **8.1. 작업 내용:**  
  * **환경 설정:** 선택한 JS 프레임워크로 Tauri 개발 환경을 설정하고, 백엔드를 위한 Python 환경을 구성합니다.  
  * **Tauri 셸:** 캐릭터와 간단한 채팅 입력 상자를 표시하기 위한 기본 애플리케이션 창과 UI를 생성합니다.  
  * **Python 사이드카:** FastAPI 서버를 포함한 초기 Python 백엔드를 개발하고, PyInstaller를 사용하여 실행 파일로 번들링합니다.  
  * **핵심 통합:** 사이드카 프로세스를 생성하고 관리하는 Rust 로직을 구현합니다.12 Rust와 Python 간의 기본 HTTP IPC를 설정합니다.  
  * **캐릭터 렌더링:** WebGL 라이브러리를 통합하여 기본 VRM 캐릭터 모델을 로드하고 표시하며, 기본적인 커서 추적 기능을 구현합니다.  
  * **기본 LangGraph:** 사용자 텍스트 입력을 받아 LLM 생성 응답을 반환하는 간단한 LangGraph 그래프를 생성합니다. 아직 도구는 사용하지 않습니다.  
  * **기본 TTS:** 로컬 Fish Speech API 서버를 설정하고 2, 컴패니언이 LLM 응답을 기본 목소리로 말하도록 TTS 호출을 통합합니다.  
* **1단계 결과물:** 텍스트로 대화하고 합성된 음성으로 응답하는 3D 캐릭터가 포함된 기능적인 애플리케이션. 핵심 아키텍처가 검증됩니다.

### **섹션 9: 2단계 \- 컨텍스트 인지 기능 구현 (예상 3-4 스프린트)**

* **목표:** 컴패니언에게 "감각"을 부여합니다. 디스플레이 인식 모듈을 구현합니다.  
* **9.1. 작업 내용:**  
  * **고성능 캡처 모듈 개발:** 각 OS에 맞는 고성능 화면 캡처 기능을 구현합니다 (DXcam for Windows, MSS for macOS/Linux).25  
  * **컨텍스트 함수:** 주기적으로 화면을 캡처하고, 이미지를 Base64로 인코딩하여 VLM API에 전송한 후, 반환된 자연어 설명을 파싱하여 섹션 6.4에서 정의된 JSON 객체를 생성하는 get\_screen\_context() 함수를 구현합니다.  
  * **API 엔드포인트:** FastAPI 서버의 새로운 엔드포인트를 통해 이 함수를 노출합니다.  
* **2단계 결과물:** Python 백엔드는 이제 요청 시 사용자의 현재 화면에 대한 시각적, 상황적 설명을 제공할 수 있습니다.

### **섹션 10: 3단계 \- 지능형 에이전트 통합 (예상 4-5 스프린트)**

* **목표:** 컴패니언의 "두뇌"를 "눈"에 연결합니다. 에이전트를 진정으로 컨텍스트를 인지하도록 만듭니다.  
* **10.1. 작업 내용:**  
  * **LangGraph 도구화:** get\_screen\_context 함수를 LangGraph 에이전트 내의 공식적인 도구로 통합합니다.19  
  * **인지 사이클 구현:** 기본 채팅 그래프를 섹션 4.2에서 설명한 전체 "인지 사이클" 그래프로 리팩토링합니다.  
  * **프롬프트 엔지니어링:** LLM에게 화면 컨텍스트를 사용하는 방법을 지시하는 정교한 메타 프롬프트를 개발합니다. 예: "당신은 도움이 되는 데스크톱 컴패니언입니다. 다음은 사용자의 현재 화면에 대한 시각적 설명입니다: \[VLM 설명 삽입\]. 이를 바탕으로 능동적인 제안이나 도움이 필요한지 결정하세요."  
  * **컨텍스트 기반 대화:** 게임 화면을 보고 조언을 하거나, 이미지의 내용을 설명하는 등 첫 번째 시각 인지 기반 사용자 스토리를 구현합니다.  
* **3단계 결과물:** 컴패니언은 이제 사용자가 컴퓨터에서 하는 일과 직접적으로 관련된 대화를 할 수 있습니다. 화면 내용에 대한 질문에 답할 수 있으며 능동적인 행동의 징후를 보이기 시작합니다.

### **섹션 11: 4단계 \- 개인화 및 고급 기능 (예상 4-6 스프린트)**

* **목표:** 애플리케이션에 "영혼"을 불어넣습니다. 깊은 사용자 연결을 생성하고 경험을 다듬는 기능에 집중합니다.  
* **11.1. 작업 내용:**  
  * **음성 복제 UI:** 사용자가 자신의 목소리를 녹음할 수 있는 프론트엔드 설정 패널을 구축합니다. 오디오 파일을 처리하고 Fish Speech가 이를 참조로 사용하도록 구성하는 백엔드 로직을 구현합니다.2  
  * **고급 애니메이션:** 에이전트의 상태를 애니메이션 시스템과 연결합니다. "생각 중", "듣는 중", "화면 보는 중"에 대한 특정 애니메이션을 제작합니다.  
  * **장기 기억:** 컴패니언이 과거 상호작용과 선호도를 기억할 수 있도록 사용자별 정보를 저장하고 검색하기 위한 벡터 데이터베이스를 구현합니다.  
  * **능동적 트리거:** 타이머나 이벤트 리스너(예: 새 애플리케이션 실행 감지)와 같이 에이전트의 인지 사이클을 촉발할 수 있는 능동적 상호작용 시스템을 개발합니다.  
* **4단계 결과물:** 사용자를 기억하고, 사용자가 선택한 목소리로 말하며, 능동적으로 도움을 제공할 수 있는 고도로 세련되고 개인화된 컴패니언. 진정한 차세대 데스크톱 보조 장치가 완성됩니다.

### **결론 및 권장 사항**

본 문서는 기존 데스크톱 마스코트의 개념을 뛰어넘어, 강력한 로컬 AI 기술을 통합한 차세대 지능형 데스크톱 컴패니언 "DesktopMate-Plus"의 개발을 위한 종합적인 청사진을 제시합니다. 제안된 아키텍처와 기술 스택은 성능, 개인정보 보호, 확장성이라는 핵심 원칙을 중심으로 신중하게 선택되었습니다.

**핵심 권장 사항은 다음과 같습니다:**

1. **Tauri 및 Python 사이드카 아키텍처 채택:** 이 아키텍처는 경량의 고성능 UI와 강력한 Python 기반 AI 백엔드를 효과적으로 결합하는 가장 실용적이고 견고한 솔루션입니다. 이는 프로젝트의 기술적 기반이 되어야 합니다.  
2. **디스플레이 인식을 위한 화면 캡처 및 VLM 우선 사용:** 사용자의 비전과 같이 게임 플레이 분석 등 일반적이고 동적인 상호작용을 위해서는 화면의 시각적 컨텍스트를 직접 이해하는 VLM 기반 접근 방식이 필수적입니다. 이는 프로젝트의 핵심 차별성을 확보하고 진정한 '컴패니언' 경험을 제공하는 결정적인 기술 선택입니다. DXcam과 같은 고성능 캡처 라이브러리와 양자화된 경량 VLM을 통해 성능 문제를 완화할 수 있습니다.  
3. **LangGraph를 인지 아키텍처로 설계:** 대화 기능을 단순한 챗봇으로 구현하는 대신, LangGraph의 상태 기반 및 순환적 특성을 활용하여 '관찰-판단-결정-행동'의 인지 사이클을 모델링해야 합니다. 이는 컴패니언의 지능을 한 차원 높이고 미래의 복잡한 행동 패턴을 위한 확장 가능한 기반을 마련할 것입니다.  
4. **음성 복제 기능을 핵심 개인화 요소로 강조:** Fish Speech의 제로샷 음성 복제 기능은 기술적 성과를 넘어 사용자와 컴패니언 간의 깊은 정서적 유대를 형성하는 강력한 도구입니다. 이 기능은 애플리케이션의 주요 마케팅 포인트이자 핵심 사용자 경험으로 전면에 내세워야 합니다.

제시된 4단계 개발 로드맵을 따름으로써, 프로젝트는 체계적으로 핵심 아키텍처를 검증하고, 점진적으로 지능과 개인화 기능을 추가하여 최종적으로 비전에 부합하는 혁신적인 제품을 완성할 수 있을 것입니다. 성공적인 개발을 위해서는 각 단계별 목표에 집중하고, 특히 2단계에서 제안된 VLM 기반의 시각 인지 모듈을 성공적으로 구현하는 것이 매우 중요합니다.

#### **참고 자료**

1. LangGraph: Build Stateful AI Agents in Python \- Real Python, 10월 15, 2025에 액세스, [https://realpython.com/langgraph-python/](https://realpython.com/langgraph-python/)  
2. OpenAudio, 10월 15, 2025에 액세스, [https://speech.fish.audio/](https://speech.fish.audio/)  
3. Desktop Mate on Steam, 10월 15, 2025에 액세스, [https://store.steampowered.com/app/3301060/Desktop\_Mate/](https://store.steampowered.com/app/3301060/Desktop_Mate/)  
4. Desktop Agents/Pets (Alternative to Desktop Mate) : r/linux\_gaming \- Reddit, 10월 15, 2025에 액세스, [https://www.reddit.com/r/linux\_gaming/comments/1hztyma/desktop\_agentspets\_alternative\_to\_desktop\_mate/](https://www.reddit.com/r/linux_gaming/comments/1hztyma/desktop_agentspets_alternative_to_desktop_mate/)  
5. fishaudio/fish-speech-1.5 \- Hugging Face, 10월 15, 2025에 액세스, [https://huggingface.co/fishaudio/fish-speech-1.5](https://huggingface.co/fishaudio/fish-speech-1.5)  
6. Fish Audio: Home, 10월 15, 2025에 액세스, [https://docs.fish.audio/](https://docs.fish.audio/)  
7. GitHub \- GitHub, 10월 15, 2025에 액세스, [https://github.com/shinyflvre/Mate-Engine](https://github.com/shinyflvre/Mate-Engine)  
8. Fish Speech: An Efficient Low-Memory Voice Cloning Open Source Tool | by Gen. Devin DL., 10월 15, 2025에 액세스, [https://medium.com/@tubelwj/fish-speech-an-efficient-low-memory-voice-cloning-open-source-tool-7abb935b521f](https://medium.com/@tubelwj/fish-speech-an-efficient-low-memory-voice-cloning-open-source-tool-7abb935b521f)  
9. Tauri VS. Electron \- Real world application, 10월 15, 2025에 액세스, [https://www.levminer.com/blog/tauri-vs-electron](https://www.levminer.com/blog/tauri-vs-electron)  
10. The only 4 real alternatives to Electron | Astrolytics, 10월 15, 2025에 액세스, [https://www.astrolytics.io/blog/electron-alternatives](https://www.astrolytics.io/blog/electron-alternatives)  
11. Comparing Desktop Application Development Frameworks: Electron, Flutter, Tauri, React Native, and Qt | by Wassim | Medium, 10월 15, 2025에 액세스, [https://medium.com/@maxel333/comparing-desktop-application-development-frameworks-electron-flutter-tauri-react-native-and-fd2712765377](https://medium.com/@maxel333/comparing-desktop-application-development-frameworks-electron-flutter-tauri-react-native-and-fd2712765377)  
12. How to write and package desktop apps with Tauri \+ Vue \+ Python \- Senhaji Rhazi hamza, 10월 15, 2025에 액세스, [https://hamza-senhajirhazi.medium.com/how-to-write-and-package-desktop-apps-with-tauri-vue-python-ecc08e1e9f2a](https://hamza-senhajirhazi.medium.com/how-to-write-and-package-desktop-apps-with-tauri-vue-python-ecc08e1e9f2a)  
13. Sidecar \- The Tauri Documentation WIP, 10월 15, 2025에 액세스, [https://jonaskruckenberg.github.io/tauri-docs-wip/examples/sidecar.html](https://jonaskruckenberg.github.io/tauri-docs-wip/examples/sidecar.html)  
14. dieharders/example-tauri-python-server-sidecar: An ... \- GitHub, 10월 15, 2025에 액세스, [https://github.com/dieharders/example-tauri-python-server-sidecar](https://github.com/dieharders/example-tauri-python-server-sidecar)  
15. Embedding External Binaries \- Tauri, 10월 15, 2025에 액세스, [https://v2.tauri.app/develop/sidecar/](https://v2.tauri.app/develop/sidecar/)  
16. Python as Tauri sidecar \- Reddit, 10월 15, 2025에 액세스, [https://www.reddit.com/r/tauri/comments/1clkf1j/python\_as\_tauri\_sidecar/](https://www.reddit.com/r/tauri/comments/1clkf1j/python_as_tauri_sidecar/)  
17. \[AskJS\] Tauri or electron? Which one is suitable for a small app? : r/javascript \- Reddit, 10월 15, 2025에 액세스, [https://www.reddit.com/r/javascript/comments/1cxsbvz/askjs\_tauri\_or\_electron\_which\_one\_is\_suitable\_for/](https://www.reddit.com/r/javascript/comments/1cxsbvz/askjs_tauri_or_electron_which_one_is_suitable_for/)  
18. LangGraph Tutorial: Complete Beginner's Guide to Getting Started \- Latenode, 10월 15, 2025에 액세스, [https://latenode.com/blog/langgraph-tutorial-complete-beginners-guide-to-getting-started](https://latenode.com/blog/langgraph-tutorial-complete-beginners-guide-to-getting-started)  
19. Learn LangGraph basics \- Overview, 10월 15, 2025에 액세스, [https://langchain-ai.github.io/langgraph/concepts/why-langgraph/](https://langchain-ai.github.io/langgraph/concepts/why-langgraph/)  
20. What is pywinauto — pywinauto 0.6.8 documentation, 10월 15, 2025에 액세스, [https://pywinauto.readthedocs.io/en/latest/](https://pywinauto.readthedocs.io/en/latest/)  
21. pyatomac \- PyPI, 10월 15, 2025에 액세스, [https://pypi.org/project/pyatomac/](https://pypi.org/project/pyatomac/)  
22. GNOME / pyatspi2 · GitLab, 10월 15, 2025에 액세스, [https://gitlab.gnome.org/GNOME/pyatspi2](https://gitlab.gnome.org/GNOME/pyatspi2)  
23. pywinauto/pywinauto: Windows GUI Automation with Python (based on text properties) \- GitHub, 10월 15, 2025에 액세스, [https://github.com/pywinauto/pywinauto](https://github.com/pywinauto/pywinauto)  
24. MacPaw/macapptree: Repository for macos accessibility parser \- GitHub, 10월 15, 2025에 액세스, [https://github.com/MacPaw/macapptree](https://github.com/MacPaw/macapptree)  
25. Python \- Fast Screen Capture | Kyle Fu, 10월 16, 2025에 액세스, [https://kylefu.me/2023/02/18/python-fast-screen-capture.html](https://kylefu.me/2023/02/18/python-fast-screen-capture.html)  
26. How to Capture Screen using Python with better frame rate \- Stack Overflow, 10월 16, 2025에 액세스, [https://stackoverflow.com/questions/50310613/how-to-capture-screen-using-python-with-better-frame-rate](https://stackoverflow.com/questions/50310613/how-to-capture-screen-using-python-with-better-frame-rate)  
27. Best Open-Source Vision Language Models of 2025 \- Labellerr, 10월 16, 2025에 액세스, [https://www.labellerr.com/blog/top-open-source-vision-language-models/](https://www.labellerr.com/blog/top-open-source-vision-language-models/)  
28. General recommended VRAM Guidelines for LLMs \- DEV Community, 10월 16, 2025에 액세스, [https://dev.to/simplr\_sh/general-recommended-vram-guidelines-for-llms-4ef3](https://dev.to/simplr_sh/general-recommended-vram-guidelines-for-llms-4ef3)  
29. Best Local Vision-Language Models for Offline AI \- Roboflow Blog, 10월 16, 2025에 액세스, [https://blog.roboflow.com/local-vision-language-models/](https://blog.roboflow.com/local-vision-language-models/)  
30. LM Studio VRAM Requirements for Local LLMs | LocalLLM.in, 10월 16, 2025에 액세스, [https://localllm.in/blog/lm-studio-vram-requirements-for-local-llms](https://localllm.in/blog/lm-studio-vram-requirements-for-local-llms)  
31. Quickstart \- vLLM, 10월 16, 2025에 액세스, [https://docs.vllm.ai/en/stable/getting\_started/quickstart.html](https://docs.vllm.ai/en/stable/getting_started/quickstart.html)  
32. Setting Up LLaVA/BakLLaVA with vLLM: Backend and API ..., 10월 16, 2025에 액세스, [https://pyimagesearch.com/2025/09/22/setting-up-llava-bakllava-with-vllm-backend-and-api-integration/](https://pyimagesearch.com/2025/09/22/setting-up-llava-bakllava-with-vllm-backend-and-api-integration/)