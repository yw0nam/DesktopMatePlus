# Add Long-Term Memory(LTM) service API

Add a new API endpoint to support long-term services in the backend.

## Background & Context

Currently, LTM service is implemented in the backend only, and not exposed to the frontend. To enable users to interact with LTM features, we need to create a dedicated API endpoint.

## Proposed Solution

1. **Add a new API endpoint to handle LTM-related requests**
    - `v1/ltm/add_memory` - POST: Add new memory to LTM.
        - Request Body: `{ "user_id": string, "agent_id'": string, "memory_dict": list[dict] || string }`
        - memory_dict example:
            ```json
                [
                    {
                        "role": "user" || "assistant" || "system",
                        "content": "string"
                    }
                ]
            ```
            or a plain string.
            ```
                "This is a memory string."
            ```
        - Response: `{ "success": boolean, "message": dict }`
    - `v1/ltm/get_memory` - GET: Retrieve memory from LTM
        - Query Parameters: `user_id`, `agent_id`, `limit` (optional)
        - Response: `{ "success": boolean, "memories": list[dict] }`

2. **Update the API documentation to include LTM endpoints**

## Constraints

1. **Tech Stack:** React, TypeScript (Frontend), Python (Backend).
2. **Run and test:** Running and testing the python code, use uv run. And all test code should be placed in the tests/ directory.
3. **Documentation:** Update relevant API documentation to reflect new endpoints.
4. **Code Quality:** linting and formatting using `sh scripts/lint.sh`

## Relate Documents

- [API_GUIDE](../../../api/REST_API_GUIDE.md)
- [LTM_SERVICE_GUIDE](../../../feature/service/LTM_Service.md)
- [SERVICE_GUIDE](../../../feature/service/README.md)
