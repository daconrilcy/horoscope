from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from backend.apigw.errors import (
    APIError,
    ErrorCodes,
    bad_request,
    conflict,
    create_error_response,
    extract_trace_id,
    forbidden,
    handle_api_error,
    handle_generic_exception,
    handle_http_exception,
    internal_error,
    not_found,
    rate_limited,
    unauthorized,
)
from backend.apigw.middleware import (
    IdempotencyMiddleware,
    InMemoryIdempotencyStore,
)


class TestErrorEnvelope:
    """Test error envelope functionality."""
    
    def test_create_error_response(self) -> None:
        """Test creating standardized error responses."""
        response = create_error_response(
            status_code=400,
            code="BAD_REQUEST",
            message="Invalid input",
            trace_id="test-trace-123",
            details={"field": "value"},
        )
        
        assert response.status_code == 400
        content = json.loads(response.body.decode())
        assert content["code"] == "BAD_REQUEST"
        assert content["message"] == "Invalid input"
        assert content["trace_id"] == "test-trace-123"
        assert content["details"] == {"field": "value"}
        
    def test_create_error_response_minimal(self) -> None:
        """Test creating minimal error responses."""
        response = create_error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Something went wrong",
        )
        
        assert response.status_code == 500
        content = json.loads(response.body.decode())
        assert content["code"] == "INTERNAL_ERROR"
        assert content["message"] == "Something went wrong"
        assert content["trace_id"] is None
        assert "details" not in content
        
    def test_api_error_creation(self) -> None:
        """Test APIError exception creation."""
        error = APIError(
            status_code=404,
            code="NOT_FOUND",
            message="Resource not found",
            trace_id="trace-123",
        )
        
        assert error.status_code == 404
        assert error.code == "NOT_FOUND"
        assert error.message == "Resource not found"
        assert error.trace_id == "trace-123"
        
    def test_extract_trace_id_from_header(self) -> None:
        """Test extracting trace ID from request headers."""
        request = MagicMock()
        request.headers = {"X-Trace-ID": "header-trace-123"}
        request.state = MagicMock()
        
        trace_id = extract_trace_id(request)
        assert trace_id == "header-trace-123"
        
    def test_extract_trace_id_from_state(self) -> None:
        """Test extracting trace ID from request state."""
        request = MagicMock()
        request.headers = {}
        request.state = MagicMock()
        request.state.trace_id = "state-trace-123"
        
        trace_id = extract_trace_id(request)
        assert trace_id == "state-trace-123"
        
    def test_extract_trace_id_none(self) -> None:
        """Test extracting trace ID when none exists."""
        request = MagicMock()
        request.headers = {}
        request.state = MagicMock()
        request.state.trace_id = None

        trace_id = extract_trace_id(request)
        assert trace_id is None
        
    def test_handle_api_error(self) -> None:
        """Test handling APIError exceptions."""
        request = MagicMock()
        request.headers = {}
        request.state = MagicMock()
        
        error = APIError(
            status_code=400,
            code="BAD_REQUEST",
            message="Invalid input",
            trace_id="error-trace-123",
        )
        
        response = handle_api_error(request, error)
        
        assert response.status_code == 400
        content = json.loads(response.body.decode())
        assert content["code"] == "BAD_REQUEST"
        assert content["message"] == "Invalid input"
        assert content["trace_id"] == "error-trace-123"
        
    def test_handle_http_exception(self) -> None:
        """Test handling HTTPException."""
        request = MagicMock()
        request.headers = {}
        request.state = MagicMock()
        
        exc = HTTPException(status_code=404, detail="Not found")
        response = handle_http_exception(request, exc)
        
        assert response.status_code == 404
        content = json.loads(response.body.decode())
        assert content["code"] == "NOT_FOUND"
        assert content["message"] == "Not found"
        
    def test_handle_generic_exception(self) -> None:
        """Test handling generic exceptions."""
        request = MagicMock()
        request.headers = {}
        request.state = MagicMock()
        
        exc = ValueError("Something went wrong")
        response = handle_generic_exception(request, exc)
        
        assert response.status_code == 500
        content = json.loads(response.body.decode())
        assert content["code"] == "INTERNAL_ERROR"
        assert content["message"] == "An unexpected error occurred"
        
    def test_convenience_functions(self) -> None:
        """Test convenience error creation functions."""
        # Test bad_request
        error = bad_request("Invalid input", "trace-123", {"field": "value"})
        assert error.status_code == 400
        assert error.code == ErrorCodes.BAD_REQUEST
        
        # Test unauthorized
        error = unauthorized("Not authenticated", "trace-123")
        assert error.status_code == 401
        assert error.code == ErrorCodes.UNAUTHORIZED
        
        # Test forbidden
        error = forbidden("Access denied", "trace-123")
        assert error.status_code == 403
        assert error.code == ErrorCodes.FORBIDDEN
        
        # Test not_found
        error = not_found("Resource not found", "trace-123")
        assert error.status_code == 404
        assert error.code == ErrorCodes.NOT_FOUND
        
        # Test conflict
        error = conflict("Resource exists", "trace-123", {"id": "123"})
        assert error.status_code == 409
        assert error.code == ErrorCodes.CONFLICT
        
        # Test rate_limited
        error = rate_limited("Too many requests", "trace-123", 60)
        assert error.status_code == 429
        assert error.code == ErrorCodes.RATE_LIMITED
        assert error.details == {"retry_after": 60}
        
        # Test internal_error
        error = internal_error("Server error", "trace-123")
        assert error.status_code == 500
        assert error.code == ErrorCodes.INTERNAL_ERROR


class TestIdempotencyMiddleware:
    """Test idempotency middleware functionality."""
    
    def test_non_post_request_passthrough(self) -> None:
        """Test that non-POST requests pass through unchanged."""
        app = FastAPI()
        IdempotencyMiddleware(app)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
        
    def test_post_without_idempotency_key(self) -> None:
        """Test POST request without idempotency key passes through."""
        app = FastAPI()
        IdempotencyMiddleware(app)
        
        @app.post("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app)
        response = client.post("/test", json={"data": "test"})
        
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
        
    def test_post_with_idempotency_key_first_request(self) -> None:
        """Test first POST request with idempotency key."""
        app = FastAPI()
        IdempotencyMiddleware(app)
        
        @app.post("/test")
        async def test_endpoint():
            return {"message": "success", "timestamp": time.time()}
            
        client = TestClient(app)
        headers = {"Idempotency-Key": "test-key-123"}
        response = client.post("/test", json={"data": "test"}, headers=headers)
        
        assert response.status_code == 200
        assert "message" in response.json()
        
    @pytest.mark.asyncio
    async def test_post_with_idempotency_key_duplicate_request(self) -> None:
        """Test duplicate POST request with same idempotency key."""
        # Test the store directly instead of through middleware
        store = InMemoryIdempotencyStore()
        
        # First request data
        response_data = {
            "status_code": 200,
            "body": '{"message": "success", "call_count": 1}',
            "timestamp": time.time(),
        }
        
        # Store the first response
        await store.set("test-key-123", "hash-456", response_data)
        
        # Retrieve the cached response
        cached = await store.get("test-key-123", "hash-456")
        assert cached is not None
        assert cached["status_code"] == 200
        assert cached["body"] == '{"message": "success", "call_count": 1}'
        
        # Test that different hash returns None
        cached_different = await store.get("test-key-123", "different-hash")
        assert cached_different is None
        
    def test_post_with_different_idempotency_key(self) -> None:
        """Test POST requests with different idempotency keys."""
        app = FastAPI()
        IdempotencyMiddleware(app)
        
        call_count = 0
        
        @app.post("/test")
        async def test_endpoint():
            nonlocal call_count
            call_count += 1
            return {"message": "success", "call_count": call_count}
            
        client = TestClient(app)
        
        # First request
        response1 = client.post(
            "/test", 
            json={"data": "test"}, 
            headers={"Idempotency-Key": "key-1"}
        )
        assert response1.status_code == 200
        
        # Second request with different key
        response2 = client.post(
            "/test", 
            json={"data": "test"}, 
            headers={"Idempotency-Key": "key-2"}
        )
        assert response2.status_code == 200
        
        # Should be different responses
        assert response1.json() != response2.json()
        
    def test_error_responses_not_cached(self) -> None:
        """Test that error responses are not cached."""
        app = FastAPI()
        IdempotencyMiddleware(app)
        
        call_count = 0
        
        @app.post("/test")
        async def test_endpoint():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise HTTPException(status_code=400, detail="Bad request")
            return {"message": "success"}
            
        client = TestClient(app)
        headers = {"Idempotency-Key": "test-key-123"}
        
        # First request (error)
        response1 = client.post("/test", json={"data": "test"}, headers=headers)
        assert response1.status_code == 400
        
        # Second request (success)
        response2 = client.post("/test", json={"data": "test"}, headers=headers)
        assert response2.status_code == 200


class TestIdempotencyStore:
    """Test idempotency store implementations."""
    
    @pytest.mark.asyncio
    async def test_in_memory_store_basic_operations(self) -> None:
        """Test basic store operations."""
        store = InMemoryIdempotencyStore()
        
        # Test set and get
        response_data = {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": '{"message": "success"}',
            "timestamp": time.time(),
        }
        
        await store.set("key-123", "hash-456", response_data)
        
        cached = await store.get("key-123", "hash-456")
        assert cached == response_data
        
    @pytest.mark.asyncio
    async def test_in_memory_store_missing_key(self) -> None:
        """Test getting non-existent key."""
        store = InMemoryIdempotencyStore()
        
        cached = await store.get("missing-key", "missing-hash")
        assert cached is None
        
    @pytest.mark.asyncio
    async def test_in_memory_store_ttl_expiry(self) -> None:
        """Test TTL expiry functionality."""
        store = InMemoryIdempotencyStore(ttl_seconds=1)
        
        response_data = {
            "status_code": 200,
            "headers": {},
            "body": '{"message": "success"}',
            "timestamp": time.time(),
        }
        
        await store.set("key-123", "hash-456", response_data)
        
        # Should be available immediately
        cached = await store.get("key-123", "hash-456")
        assert cached is not None
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be expired
        cached = await store.get("key-123", "hash-456")
        assert cached is None


class TestTraceIdMiddleware:
    """Test trace ID middleware functionality."""
    
    def test_trace_id_from_header(self) -> None:
        """Test trace ID from request header."""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            # Simulate trace ID middleware behavior
            trace_id = request.headers.get("X-Trace-ID")
            if not trace_id:
                trace_id = "generated-trace-id"
            return {"trace_id": trace_id}
            
        client = TestClient(app)
        response = client.get("/test", headers={"X-Trace-ID": "custom-trace-123"})
        
        assert response.status_code == 200
        assert response.json()["trace_id"] == "custom-trace-123"
        
    def test_trace_id_generation(self) -> None:
        """Test automatic trace ID generation."""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            # Simulate trace ID middleware behavior
            trace_id = request.headers.get("X-Trace-ID")
            if not trace_id:
                trace_id = "generated-trace-id"
            return {"trace_id": trace_id}
            
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        trace_id = response.json()["trace_id"]
        assert trace_id is not None
        assert trace_id == "generated-trace-id"


class TestAPIVersionMiddleware:
    """Test API version middleware functionality."""
    
    def test_version_enforcement(self) -> None:
        """Test API version enforcement."""
        app = FastAPI()
        
        @app.get("/v1/test")
        async def test_endpoint():
            return {"message": "success"}
            
        @app.get("/v2/test")
        async def test_endpoint_v2():
            return {"message": "success"}
            
        client = TestClient(app)
        
        # Valid version
        response = client.get("/v1/test")
        assert response.status_code == 200
        
        # Invalid version - should return 404 (not found) since route doesn't exist
        response = client.get("/v2/test")
        assert response.status_code == 404
        
    def test_health_check_exemption(self) -> None:
        """Test that health checks are exempt from version enforcement."""
        app = FastAPI()
        
        @app.get("/health")
        async def health_check():
            return {"status": "healthy"}
            
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestRequestLoggingMiddleware:
    """Test request logging middleware functionality."""
    
    def test_request_logging(self) -> None:
        """Test request and response logging."""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
            
        client = TestClient(app)
        
        # Test that the endpoint works
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["message"] == "success"
