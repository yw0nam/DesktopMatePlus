제시해주신 로그는 `loguru`와 같은 라이브러리의 **Serialize(JSON)** 옵션이 켜져 있고, 불필요한 메타데이터(전체 파일 경로, 스레드 정보, 프로세스 정보 등)가 모두 포함되어 있어 가독성이 매우 떨어지는 상태입니다.

말씀하신 4가지 요구사항(Data Flow 파악, API 식별, 간결성, 일별 로테이션)을 충족하면서, Python 업계 표준을 반영한 **Logging Guideline**을 제안합니다.

-----

# 📋 Python Logging Guideline (Proposed)

## 1\. 로그 포맷 정의 (Conciseness)

가장 먼저 **"사람이 읽을 수 있는(Human-readable)"** 포맷으로 변경해야 합니다. JSON 형식은 ELK 스택 등으로 보낼 때만 사용하고, 로컬 파일이나 콘솔 확인용으로는 아래 포맷을 따릅니다.

### 추천 포맷 (Format String)

불필요한 전체 경로(`path`)나 절대 시간(`timestamp`) 등을 제거하고, 핵심 정보만 남깁니다.

> **`[시간] | [레벨] | [모듈:라인] | [RequestID] - [메시지]`**

  * **시간:** 밀리초까지만 포함 (`HH:mm:ss.SSS`)
  * **레벨:** 5글자 고정 (` INFO  `, `ERROR`)
  * **위치:** 패키지 전체 경로 대신 `모듈명:줄번호`만 표기
  * **RequestID (중요):** Data Flow 추적을 위한 고유 식별자 (없으면 공란)

### Before (현재)

```json
{"text": "...", "record": {"file": {"path": "/home/spow12/.../handlers.py"}, "process": ...}}
```

### After (개선)

```text
11:29:24.548 | INFO  | handlers:551 | [req_x9z1] - Sent turn_end event to connection 4074d (turn 5)
11:33:01.364 | INFO  | websocket:64 | [req_x9z1] - ⚡ WebSocket disconnected: 4074d
```

-----

## 2\. Data Flow 및 API 추적 전략

### A. Context ID (Request ID) 도입

Data Flow를 파악하기 위해서는 **"누가(Who)"** 혹은 \*\*"어떤 요청(Which Request)"\*\*에서 발생한 로그인지 연결 고리가 필요합니다.

  * **API 진입 시점**에 `Request ID` (UUID 등)를 생성하고, 해당 요청이 끝날 때까지 모든 로그에 이 ID를 함께 찍습니다.
  * Python의 `contextvars`나 로깅 라이브러리의 `bind()` 기능을 사용합니다.

### B. API 호출 식별 (Visibility)

API 호출 여부를 바로 파악하기 위해 \*\*진입(Entry)\*\*과 **종료(Exit)** 로그에 명확한 접두사나 이모지를 사용합니다.

  * **Request:** `➡️ [METHOD] URI`
  * **Response:** `⬅️ [METHOD] URI (Status Code) - Duration`

-----

## 3\. 로깅 레벨 및 내용 규칙 (Rules)

무의미한 정보를 줄이기 위해 레벨별 기록 대상을 엄격히 제한합니다.

| Level | 사용 기준 | 예시 |
| :--- | :--- | :--- |
| **ERROR** | 즉각적인 조치가 필요한 예외, 기능 실패 | DB 연결 실패, 500 에러 발생 |
| **WARN** | 예상치 못했으나 프로세스는 계속됨, 잠재적 문제 | 핑 타임아웃, 재시도 발생, deprecated API 사용 |
| **INFO** | **(중요)** 주요 비즈니스 흐름, 상태 변경, API 호출 | `User A logged in`, `Job started`, `API /chat call` |
| **DEBUG** | 개발 단계 상세 데이터 (변수 값, 쿼리문 등) | `payload={"key": "val"}`, `SQL: SELECT * ...` |

> **Rule:** 운영(Production) 환경에서는 `INFO` 이상만 남깁니다. 단순 변수 확인용 로그는 `DEBUG`로 작성하거나 삭제합니다.

-----

## 4\. 파일 저장 및 로테이션 (Daily Rotation)

파일이 비대해지는 것을 막고 관리를 용이하게 하기 위해 매일 새로운 파일로 저장합니다.

  * **파일명:** `logs/app_YYYY-MM-DD.log`
  * **Rotation:** 매일 자정 (`00:00`)
  * **Retention:** 14일 \~ 30일 (오래된 로그 자동 삭제)

-----

## 5\. Implementation Example (구현 예시)

가장 많이 사용하시는 `loguru`를 기준으로, 위 가이드라인을 코드로 구현하면 다음과 같습니다. (`logging` 모듈로도 비슷하게 구현 가능)

```python
import sys
from loguru import logger

# 1. 기존 핸들러 제거 (기본 설정을 초기화)
logger.remove()

# 2. 포맷 정의 (Concise & Readable)
# {extra[request_id]}는 request middleware에서 주입한다고 가정
log_format = (
    "<green>{time:HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
    "<magenta>{extra[request_id]}</magenta> - "
    "<level>{message}</level>"
)

# 3. 콘솔 출력 핸들러 (개발용)
logger.add(sys.stderr, format=log_format, level="DEBUG")

# 4. 파일 저장 핸들러 (매일 로테이션 + 간결한 포맷)
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",  # 일별 파일 생성
    rotation="00:00",                   # 매일 자정에 로테이션
    retention="30 days",                # 30일치 보관
    format=log_format,                  # JSON 대신 포맷 스트링 사용
    level="INFO",                       # 파일에는 INFO 이상만
    encoding="utf-8"
)

# --- 사용 예시 ---

# 1. Request ID 바인딩 (보통 미들웨어에서 처리)
context_logger = logger.bind(request_id="req_12345")

# 2. API Call Logging
context_logger.info("➡️ POST /api/chat/start")

# 3. Logic Flow
try:
    # 비즈니스 로직 수행
    context_logger.info("Processing turn 5 for connection 4074d")
    # ... code ...
    context_logger.info("⬅️ POST /api/chat/start (200 OK) - 150ms")
except Exception as e:
    context_logger.error(f"Failed to process chat: {e}")

```

### 실제 출력 결과 미리보기

```text
11:29:24.548 | INFO     | handlers:551 | req_12345 - ➡️ POST /api/chat/start
11:29:24.600 | INFO     | handlers:560 | req_12345 - Processing turn 5 for connection 4074d
11:29:24.750 | INFO     | handlers:580 | req_12345 - ⬅️ POST /api/chat/start (200 OK) - 150ms
```

### 요약

1.  **JSON 포맷 제거:** `format="..."`을 사용하여 사람이 읽기 편한 문자열로 변경하세요.
2.  **Context 바인딩:** `logger.bind(request_id=...)`를 활용해 로그 간의 연관성을 만드세요.
3.  **Rotation 설정:** `rotation="00:00"`을 추가하여 일별 로그 파일을 생성하세요.

이 가이드라인을 적용하시면 현재의 복잡한 JSON 로그 더미에서 벗어나, 흐름이 보이는 깔끔한 로그를 확보하실 수 있습니다.
