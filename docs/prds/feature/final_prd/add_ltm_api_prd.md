# LTM Service API PRD

## Core Guide (Within 200 lines, for immediate action)

### 1.1. Overview

- **Goal:** Expose the existing backend Long-Term Memory (LTM) service to the frontend/clients via a dedicated REST API, enabling external agents or UIs to add and retrieve memories.
- **Non-Goal:**
    - Implementing new storage backends (we utilize the existing `Mem0LTM` implementation).
    - Complex memory management logic (merging, conflict resolution) beyond what the existing `LTMService` provides.
    - Implementing authentication/authorization for these endpoints within this scope. It is assumed that existing application-level security mechanisms will be leveraged, or these endpoints will initially operate within a trusted internal network.

### Detailed Requirements

**Functional Requirements:**

1.  **Add Memory Endpoint** `[Must-have]`
    -   **Method:** `POST`
    -   **Path:** `/v1/ltm/add_memory`
    -   **Input:** JSON object containing `user_id` (str), `agent_id` (str), and `memory_dict` (list[dict] or str).
    -   **Output:** Success status and confirmation message.
    -   **Logic:** Validate input and call `LTMService.add_memory` with the provided data.

2.  **Get/Search Memory Endpoint** `[Must-have]`
    -   **Method:** `GET`
    -   **Path:** `/v1/ltm/get_memory`
    -   **Input:** Query parameters: `user_id` (str), `agent_id` (str), `limit` (int, optional, default=100).
    -   **Output:** List of memory objects matching the criteria.
    -   **Logic:** Call `LTMService.get_all_memories` (or a similar retrieval method) filtering by `user_id` and `agent_id`, applying `limit` if provided.

3.  **Data Validation** `[Must-have]`
    -   Utilize Pydantic models to ensure strict validation of all incoming request bodies and outgoing response structures, enforcing clear API contracts.

**Non-Functional Requirements:**
-   **Performance:** API endpoints should aim for a response time under 500ms under normal load to ensure a responsive user experience.
-   **Consistency:** The API should adhere to established project API guidelines for error handling and response formatting (e.g., standardized `success` boolean field).

### Implementation Plan

1.  **Define Data Models:** Create (or extend existing) Pydantic models in `backend/src/models/ltm.py` for `AddMemoryRequest`, `MemoryItem`, and `GetMemoryResponse`. This ensures clear data contracts.
2.  **Create API Router:** Implement the `APIRouter` in a new file, `backend/src/api/routes/ltm.py`. This router will contain the `add_memory` and `get_memory` endpoint functions.
3.  **Register Router:** Integrate the new `ltm` router into the main API application by updating `backend/src/api/routes/__init__.py`.
4.  **Inject LTMService:** Ensure the `LTMService` dependency is correctly injected into the API endpoint functions, allowing them to interact with the LTM backend.
5.  **Testing:** Develop comprehensive unit and integration tests in `tests/test_ltm_api.py` to verify functionality, error handling, and data validation for both new endpoints.

## Appendix (Detailed Reference)

### A. Detailed API Specifications

**1. POST /v1/ltm/add_memory**

-   **Description:** Adds one or more memories for a specific user and agent.
-   **Request Body (Pydantic Example):**
    ```json
    {
      "user_id": "user_123",
      "agent_id": "agent_007",
      "memory_dict": [
        {"role": "user", "content": "I like apples."},
        {"role": "assistant", "content": "Understood. Apples are a good fruit."}
      ]
    }
    ```
    *Note: `memory_dict` accepts either a list of role-content dictionaries or a single plain string for simpler memories.*

-   **Response (Example):**
    ```json
    {
      "success": true,
      "message": "Memory added successfully."
    }
    ```

**2. GET /v1/ltm/get_memory**

-   **Description:** Retrieves a list of memories associated with a given user and agent, with optional limiting.
-   **Query Params (Example):** `?user_id=user_123&agent_id=agent_007&limit=10`
-   **Response (Example):**
    ```json
    {
      "success": true,
      "memories": [
        {"id": "m1", "text": "I like apples.", "role": "user", "created_at": "2025-12-01T10:00:00Z"},
        {"id": "m2", "text": "Understood. Apples are a good fruit.", "role": "assistant", "created_at": "2025-12-01T10:01:00Z"}
      ]
    }
    ```
    *Note: The exact structure of `MemoryItem` may be refined based on the `LTMService`'s output.*

### B. DB Schema Changes
-   No direct database schema changes are required as the implementation leverages the existing `LTMService`, which manages its own internal data persistence (e.g., Qdrant, Chroma, or Mem0's internal storage).

### C. Technical Dependencies Details
-   **Core Dependency:** `backend/src/services/ltm_service/service.py` (abstract base class `LTMService`) and its concrete implementations (e.g., `Mem0LTM` in `backend/src/services/ltm_service/mem0_ltm.py`). The API layer will interact with this interface.
-   **FastAPI:** The primary framework for building the API endpoints and handling routing and dependency injection.
-   **Pydantic:** Used for defining clear and validated data models for requests and responses, ensuring type safety and robust API contracts.

### D. Test Scenarios Details
1.  **Scenario: Successful Memory Addition**
    -   **Input:** A valid `POST` request to `/v1/ltm/add_memory` with `user_id`, `agent_id`, and a `memory_dict` (list of dicts or string).
    -   **Expected Outcome:** HTTP 200 OK, response with `{"success": true, "message": "Memory added successfully."}`. Subsequently, a `GET` request for the same user/agent should return the added memory.
2.  **Scenario: Successful Memory Retrieval**
    -   **Precondition:** Memories have been added for a specific `user_id` and `agent_id`.
    -   **Input:** A valid `GET` request to `/v1/ltm/get_memory` with `user_id` and `agent_id`.
    -   **Expected Outcome:** HTTP 200 OK, response with `{"success": true, "memories": [...]}` containing the expected memories.
3.  **Scenario: Memory Retrieval with Limit**
    -   **Precondition:** More memories exist than the specified limit for a user/agent.
    -   **Input:** A valid `GET` request to `/v1/ltm/get_memory` with `user_id`, `agent_id`, and `limit=<N>`.
    -   **Expected Outcome:** HTTP 200 OK, response with `{"success": true, "memories": [...]}` containing exactly `N` memories (or fewer if fewer exist).
4.  **Scenario: Invalid Request Body for Add Memory**
    -   **Input:** A `POST` request to `/v1/ltm/add_memory` with a malformed or incomplete request body (e.g., missing `user_id`, `agent_id`, or `memory_dict`).
    -   **Expected Outcome:** HTTP 422 Unprocessable Entity, with a clear error message from Pydantic/FastAPI validation.
5.  **Scenario: No Memories Found for User/Agent**
    -   **Input:** A `GET` request to `/v1/ltm/get_memory` for a `user_id` and `agent_id` combination that has no stored memories.
    -   **Expected Outcome:** HTTP 200 OK, response with `{"success": true, "memories": []}`.

## Related Documents

- [API_GUIDE](../../../api/REST_API_GUIDE.md)
- [LTM_SERVICE_GUIDE](../../../feature/service/LTM_Service.md)
- [SERVICE_GUIDE](../../../feature/service/README.md)
- [Config Guide](../../../feature/config/README.md)

## Virtual FGI Reflection & Intent Notes

-   **Core Guide Length (Developer Concern):** The "Core Guide" remains concise, under 200 lines, ensuring developers can quickly grasp the essential features and immediate actions without getting bogged down in details. The detailed specifications are appropriately delegated to the Appendix.
-   **Context Reset (PM Concern):** The "Implementation Plan" breaks down the work into logically independent steps (data models, router creation, registration, testing). Each step can be completed and understood in isolation, facilitating an agile development process.
-   **UX Complexity (Designer Concern):** As this PRD defines a backend API, "UX" primarily refers to the developer experience. The API design follows standard RESTful conventions with clear inputs/outputs and Pydantic validation, minimizing complexity for developers integrating with this service. The flexible `memory_dict` input for `add_memory` (list of dicts or string) is a pragmatic choice to support both structured and unstructured memory additions, balancing strictness with ease of use.
-   **KPI Contribution (Business Team Leader Concern):** Exposing the LTM service via a well-defined API directly enables the development of new, intelligent features that can leverage long-term memory for more personalized and effective interactions. This is a foundational step to improve agent capabilities, ultimately driving user engagement and product value.
-   **Authentication/Authorization Scope (Self-Correction):** Explicitly clarifying that authentication/authorization is a non-goal for *this specific PRD* helps manage developer expectations and prevents scope creep. It acknowledges that security is important but handled at a higher architectural layer or in a separate feature.
