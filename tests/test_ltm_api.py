"""Tests for LTM API routes."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_ltm_service():
    """Create a mock LTM service."""
    with patch("src.api.routes.ltm.get_ltm_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


class TestAddMemory:
    """Test cases for add_memory endpoint."""

    def test_add_memory_success_with_list(self, mock_ltm_service, client):
        """Test successful memory addition with list of messages."""
        mock_ltm_service.add_memory.return_value = {
            "results": [{"id": "mem_123", "memory": "User likes apples"}],
            "relations": [
                {"source": "user", "relationship": "likes", "destination": "apples"}
            ],
        }

        response = client.post(
            "/v1/ltm/add_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
                "memory_dict": [
                    {"role": "user", "content": "I like apples."},
                    {
                        "role": "assistant",
                        "content": "Understood. Apples are a good fruit.",
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Memory added successfully."
        assert "result" in data
        assert data["result"]["results"][0]["id"] == "mem_123"

    def test_add_memory_success_with_string(self, mock_ltm_service, client):
        """Test successful memory addition with plain string."""
        mock_ltm_service.add_memory.return_value = {
            "results": [{"id": "mem_124", "memory": "User prefers dark mode"}],
            "relations": [],
        }

        response = client.post(
            "/v1/ltm/add_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
                "memory_dict": "User prefers dark mode for the interface.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Memory added successfully."
        assert "result" in data

    def test_add_memory_service_not_initialized(self, client):
        """Test adding memory when service is not initialized."""
        with patch("src.api.routes.ltm.get_ltm_service", return_value=None):
            response = client.post(
                "/v1/ltm/add_memory",
                json={
                    "user_id": "user_123",
                    "agent_id": "agent_007",
                    "memory_dict": "Some memory",
                },
            )

        assert response.status_code == 503
        assert "LTM service not initialized" in response.json()["detail"]

    def test_add_memory_missing_user_id(self, mock_ltm_service, client):
        """Test adding memory with missing user_id."""
        response = client.post(
            "/v1/ltm/add_memory",
            json={
                "agent_id": "agent_007",
                "memory_dict": "Some memory",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_add_memory_missing_agent_id(self, mock_ltm_service, client):
        """Test adding memory with missing agent_id."""
        response = client.post(
            "/v1/ltm/add_memory",
            json={
                "user_id": "user_123",
                "memory_dict": "Some memory",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_add_memory_service_error(self, mock_ltm_service, client):
        """Test adding memory when service returns an error."""
        mock_ltm_service.add_memory.return_value = {
            "error": "Database connection failed"
        }

        response = client.post(
            "/v1/ltm/add_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
                "memory_dict": "Some memory",
            },
        )

        assert response.status_code == 500
        assert "Error adding memory" in response.json()["detail"]


class TestSearchMemory:
    """Test cases for search_memory endpoint."""

    def test_search_memory_success(self, mock_ltm_service, client):
        """Test successful memory search."""
        mock_ltm_service.search_memory.return_value = {
            "results": [
                {
                    "id": "mem_123",
                    "memory": "User likes apples",
                    "user_id": "user_123",
                    "agent_id": "agent_007",
                    "score": 0.85,
                },
            ],
            "relations": [
                {"source": "user", "relationship": "likes", "destination": "apples"}
            ],
        }

        response = client.post(
            "/v1/ltm/search_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
                "query": "apple",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "result" in data
        assert len(data["result"]["results"]) == 1
        assert "apples" in data["result"]["results"][0]["memory"]

    def test_search_memory_no_results(self, mock_ltm_service, client):
        """Test memory search with no results."""
        mock_ltm_service.search_memory.return_value = {"results": [], "relations": []}

        response = client.post(
            "/v1/ltm/search_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
                "query": "nonexistent",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"]["results"] == []

    def test_search_memory_service_not_initialized(self, client):
        """Test searching memory when service is not initialized."""
        with patch("src.api.routes.ltm.get_ltm_service", return_value=None):
            response = client.post(
                "/v1/ltm/search_memory",
                json={
                    "user_id": "user_123",
                    "agent_id": "agent_007",
                    "query": "apple",
                },
            )

        assert response.status_code == 503
        assert "LTM service not initialized" in response.json()["detail"]

    def test_search_memory_service_error(self, mock_ltm_service, client):
        """Test searching memory when service returns an error."""
        mock_ltm_service.search_memory.return_value = {"error": "Search failed"}

        response = client.post(
            "/v1/ltm/search_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
                "query": "apple",
            },
        )

        assert response.status_code == 500
        assert "Error searching memories" in response.json()["detail"]


class TestDeleteMemory:
    """Test cases for delete_memory endpoint."""

    def test_delete_memory_success(self, mock_ltm_service, client):
        """Test successful memory deletion."""
        mock_ltm_service.delete_memory.return_value = {"message": "Memory deleted"}

        response = client.request(
            "DELETE",
            "/v1/ltm/delete_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
                "memory_id": "mem_123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Memory deleted successfully."
        assert "result" in data

    def test_delete_memory_service_not_initialized(self, client):
        """Test deleting memory when service is not initialized."""
        with patch("src.api.routes.ltm.get_ltm_service", return_value=None):
            response = client.request(
                "DELETE",
                "/v1/ltm/delete_memory",
                json={
                    "user_id": "user_123",
                    "agent_id": "agent_007",
                    "memory_id": "mem_123",
                },
            )

        assert response.status_code == 503
        assert "LTM service not initialized" in response.json()["detail"]

    def test_delete_memory_service_error(self, mock_ltm_service, client):
        """Test deleting memory when service returns an error."""
        mock_ltm_service.delete_memory.return_value = {"error": "Memory not found"}

        response = client.request(
            "DELETE",
            "/v1/ltm/delete_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
                "memory_id": "nonexistent_mem",
            },
        )

        assert response.status_code == 500
        assert "Error deleting memory" in response.json()["detail"]

    def test_delete_memory_missing_memory_id(self, mock_ltm_service, client):
        """Test deleting memory with missing memory_id."""
        response = client.request(
            "DELETE",
            "/v1/ltm/delete_memory",
            json={
                "user_id": "user_123",
                "agent_id": "agent_007",
            },
        )

        assert response.status_code == 422  # Validation error
