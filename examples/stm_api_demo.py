import json
import uuid

import httpx

# Configuration
BASE_URL = "http://127.0.0.1:5000/v1"
USER_ID = "demo-user-001"
AGENT_ID = "demo-agent-001"


def print_separator(title):
    print(f"\n{'='*20} {title} {'='*20}")


def print_response(response):
    try:
        print(f"Status Code: {response.status_code}")
        print("Response Body:")
        print(json.dumps(response.json(), indent=2))
    except json.JSONDecodeError:
        print("Response Body (Raw):")
        print(response.text)


def add_chat_history(session_id=None):
    print_separator("1. Add Chat History")
    url = f"{BASE_URL}/stm/add-chat-history"

    # We create a new session by not providing session_id (or providing a new one if we wanted to enforce it)
    # But usually the API creates one if missing. Let's see the docs...
    # Docs say: "session_id (new session created if omitted)"

    payload = {
        "user_id": USER_ID,
        "agent_id": AGENT_ID,
        "messages": [
            {
                "role": "user",
                "content": "Hello, this is a test message from the demo script.",
            },
            {"role": "assistant", "content": "Hello! I am ready to help you."},
        ],
    }
    if session_id:
        payload["session_id"] = session_id

    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = httpx.post(url, json=payload)
        print_response(response)
        if response.status_code == 201:
            return response.json().get("session_id")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_chat_history(session_id):
    print_separator("2. Get Chat History")
    if not session_id:
        print("Skipping: No session ID available.")
        return

    url = f"{BASE_URL}/stm/get-chat-history"
    params = {"user_id": USER_ID, "agent_id": AGENT_ID, "session_id": session_id}

    print(f"GET {url}")
    print(f"Params: {params}")

    try:
        response = httpx.get(url, params=params)
        print_response(response)
    except Exception as e:
        print(f"Error: {e}")


def list_sessions():
    print_separator("3. List Sessions")
    url = f"{BASE_URL}/stm/sessions"
    params = {"user_id": USER_ID, "agent_id": AGENT_ID}

    print(f"GET {url}")
    print(f"Params: {params}")

    try:
        response = httpx.get(url, params=params)
        print_response(response)
    except Exception as e:
        print(f"Error: {e}")


def update_session_metadata(session_id):
    print_separator("4. Update Session Metadata")
    if not session_id:
        print("Skipping: No session ID available.")
        return

    url = f"{BASE_URL}/stm/sessions/{session_id}/metadata"
    payload = {
        "metadata": {
            "title": "STM Demo Session",
            "tags": ["demo", "test", "python-script"],
        }
    }

    print(f"PATCH {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = httpx.patch(url, json=payload)
        print_response(response)
    except Exception as e:
        print(f"Error: {e}")


def delete_session(session_id):
    print_separator("5. Delete Session")
    if not session_id:
        print("Skipping: No session ID available.")
        return

    url = f"{BASE_URL}/stm/sessions/{session_id}"
    params = {"user_id": USER_ID, "agent_id": AGENT_ID}

    print(f"DELETE {url}")
    print(f"Params: {params}")

    try:
        response = httpx.delete(url, params=params)
        print_response(response)
    except Exception as e:
        print(f"Error: {e}")


def main():
    print("Starting STM API Demo...")
    print(f"Base URL: {BASE_URL}")
    print(f"User ID: {USER_ID}")
    print(f"Agent ID: {AGENT_ID}")

    # Check health (optional, but good practice if health endpoint exists)
    # response = httpx.get(f"{BASE_URL}/health") # Assuming health check exists

    # 1. Add Chat History (Create Session)
    session_id = str(uuid.uuid4())
    session_id = add_chat_history(session_id=session_id)
    session_id = add_chat_history(
        session_id=session_id
    )  # Call twice to show multiple messages in history
    if session_id:
        print(f"\nCreated Session ID: {session_id}")

        # 2. Get Chat History
        get_chat_history(session_id)

        # 3. List Sessions
        list_sessions()

        # 4. Update Metadata
        update_session_metadata(session_id)

        # Verify metadata update by listing again (optional)
        # list_sessions()

        # 5. Delete Session
        # Input to confirm deletion to avoid accidental data loss during repeated runs?
        # For a demo script, we usually want it to clean up after itself, so we'll delete.
        delete_session(session_id)

        # Verify deletion
        list_sessions()

    else:
        print("\nFailed to create session. Stopping demo.")


if __name__ == "__main__":
    main()
