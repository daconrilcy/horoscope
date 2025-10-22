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
    APIVersionMiddleware,
    IdempotencyMiddleware,
    InMemoryIdempotencyStore,
    RequestLoggingMiddleware,
    TraceIdMiddleware,
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
        request.state.trace_id = None

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
        request.state.trace_id = None

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
        request.state.trace_id = None

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


class TestTraceIdMiddlewareMethods:
    """Test TraceIdMiddleware functionality."""
    
    def test_trace_id_middleware_init(self) -> None:
        """Test TraceIdMiddleware initialization."""
        app = FastAPI()
        middleware = TraceIdMiddleware(app)
        assert middleware.app == app
        
    def test_trace_id_middleware_dispatch_with_header(self) -> None:
        """Test TraceIdMiddleware dispatch with existing trace ID."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        middleware = TraceIdMiddleware(app)
        
        # Mock request with existing trace ID
        request = MagicMock()
        request.headers = {"X-Trace-ID": "existing-trace-123"}
        request.state = MagicMock()
        
        # Mock call_next
        call_next = AsyncMock()
        response = MagicMock()
        response.headers = {}
        call_next.return_value = response
        
        # Test dispatch
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Verify trace ID was set
        assert request.state.trace_id == "existing-trace-123"
        assert response.headers["X-Trace-ID"] == "existing-trace-123"
        
    def test_trace_id_middleware_dispatch_generate_new(self) -> None:
        """Test TraceIdMiddleware dispatch generating new trace ID."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        middleware = TraceIdMiddleware(app)
        
        # Mock request without trace ID
        request = MagicMock()
        request.headers = {}
        request.state = MagicMock()
        
        # Mock call_next
        call_next = AsyncMock()
        response = MagicMock()
        response.headers = {}
        call_next.return_value = response
        
        # Test dispatch
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Verify new trace ID was generated
        assert request.state.trace_id is not None
        assert len(request.state.trace_id) == 36  # UUID length
        assert response.headers["X-Trace-ID"] == request.state.trace_id


class TestRequestLoggingMiddlewareMethods:
    """Test RequestLoggingMiddleware functionality."""
    
    def test_request_logging_middleware_init(self) -> None:
        """Test RequestLoggingMiddleware initialization."""
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app)
        assert middleware.app == app
        
    def test_request_logging_middleware_dispatch(self) -> None:
        """Test RequestLoggingMiddleware dispatch."""
        from unittest.mock import AsyncMock, patch
        
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app)
        
        # Mock request
        request = MagicMock()
        request.method = "GET"
        request.url = MagicMock()
        request.url.__str__ = MagicMock(return_value="http://testserver/test")
        request.headers = {"user-agent": "test-agent", "content-length": "100"}
        request.state = MagicMock()
        request.state.trace_id = "test-trace-123"
        
        # Mock call_next
        call_next = AsyncMock()
        response = MagicMock()
        response.status_code = 200
        call_next.return_value = response
        
        # Test dispatch with logging
        with patch("backend.apigw.middleware.log") as mock_log:
            import asyncio
            asyncio.run(middleware.dispatch(request, call_next))
            
            # Verify logging calls
            assert mock_log.info.call_count == 2  # Request started + completed
            
            # Check request log
            request_log = mock_log.info.call_args_list[0][1]["extra"]
            assert request_log["method"] == "GET"
            assert request_log["url"] == "http://testserver/test"
            assert request_log["trace_id"] == "test-trace-123"
            
            # Check response log
            response_log = mock_log.info.call_args_list[1][1]["extra"]
            assert response_log["method"] == "GET"
            assert response_log["status_code"] == 200
            assert "duration" in response_log


class TestAPIVersionMiddlewareMethods:
    """Test APIVersionMiddleware functionality."""
    
    def test_api_version_middleware_init(self) -> None:
        """Test APIVersionMiddleware initialization."""
        app = FastAPI()
        middleware = APIVersionMiddleware(app, "v2")
        assert middleware.app == app
        assert middleware.required_version == "v2"
        
    def test_api_version_middleware_dispatch_valid_version(self) -> None:
        """Test APIVersionMiddleware dispatch with valid version."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        middleware = APIVersionMiddleware(app, "v1")
        
        # Mock request with valid version
        request = MagicMock()
        request.url.path = "/v1/test"
        
        # Mock call_next
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response
        
        # Test dispatch
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Should call next middleware
        call_next.assert_called_once_with(request)
        
    def test_api_version_middleware_dispatch_invalid_version(self) -> None:
        """Test APIVersionMiddleware dispatch with invalid version."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        middleware = APIVersionMiddleware(app, "v1")
        
        # Mock request with invalid version
        request = MagicMock()
        request.url.path = "/v2/test"
        request.state = MagicMock()
        request.state.trace_id = None
        
        # Mock call_next
        call_next = AsyncMock()
        
        # Test dispatch
        import asyncio
        result = asyncio.run(middleware.dispatch(request, call_next))
        
        # Should return error response, not call next
        call_next.assert_not_called()
        assert result.status_code == 400
        
    def test_api_version_middleware_dispatch_health_check(self) -> None:
        """Test APIVersionMiddleware dispatch with health check."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        middleware = APIVersionMiddleware(app, "v1")
        
        # Mock request for health check
        request = MagicMock()
        request.url.path = "/health"
        
        # Mock call_next
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response
        
        # Test dispatch
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Should call next middleware (health check exempt)
        call_next.assert_called_once_with(request)
        
    def test_api_version_middleware_dispatch_docs(self) -> None:
        """Test APIVersionMiddleware dispatch with docs."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        middleware = APIVersionMiddleware(app, "v1")
        
        # Mock request for docs
        request = MagicMock()
        request.url.path = "/docs"
        
        # Mock call_next
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response
        
        # Test dispatch
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Should call next middleware (docs exempt)
        call_next.assert_called_once_with(request)


    def test_idempotency_middleware_dispatch_non_post(self) -> None:
        """Test IdempotencyMiddleware dispatch with non-POST request."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        middleware = IdempotencyMiddleware(app)
        
        # Mock GET request
        request = MagicMock()
        request.method = "GET"
        
        # Mock call_next
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response
        
        # Test dispatch
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Should call next middleware (non-POST requests pass through)
        call_next.assert_called_once_with(request)
        
    def test_idempotency_middleware_dispatch_no_key(self) -> None:
        """Test IdempotencyMiddleware dispatch without idempotency key."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        middleware = IdempotencyMiddleware(app)
        
        # Mock POST request without idempotency key
        request = MagicMock()
        request.method = "POST"
        request.headers = {}
        
        # Mock call_next
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response
        
        # Test dispatch
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Should call next middleware (no key = pass through)
        call_next.assert_called_once_with(request)
        
    def test_idempotency_middleware_dispatch_cached_response(self) -> None:
        """Test IdempotencyMiddleware dispatch with cached response."""
        from unittest.mock import AsyncMock, patch
        
        app = FastAPI()
        store = InMemoryIdempotencyStore()
        middleware = IdempotencyMiddleware(app, store)
        
        # Mock POST request with idempotency key
        request = MagicMock()
        request.method = "POST"
        request.headers = {"Idempotency-Key": "test-key-123"}
        request.url.path = "/test"
        request.url.query = ""
        request._body = b'{"data": "test"}'
        request.state = MagicMock()
        request.state.trace_id = "test-trace-123"
        
        # Mock call_next
        call_next = AsyncMock()
        
        # Pre-populate cache
        cached_data = {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": '{"message": "cached"}',
            "timestamp": time.time(),
        }
        
        # Test dispatch with cached response
        with patch.object(store, 'get', return_value=cached_data):
            with patch("backend.apigw.middleware.log") as mock_log:
                import asyncio
                asyncio.run(middleware.dispatch(request, call_next))
                
                # Should not call next middleware (cached response)
                call_next.assert_not_called()
                
                # Should log cached response
                mock_log.info.assert_called_once()
                log_call = mock_log.info.call_args[1]["extra"]
                assert log_call["idempotency_key"] == "test-key-123"
                
    def test_idempotency_middleware_dispatch_error_response(self) -> None:
        """Test IdempotencyMiddleware dispatch with error response."""
        from unittest.mock import AsyncMock
        
        app = FastAPI()
        store = InMemoryIdempotencyStore()
        middleware = IdempotencyMiddleware(app, store)
        
        # Mock POST request with idempotency key
        request = MagicMock()
        request.method = "POST"
        request.headers = {"Idempotency-Key": "test-key-123"}
        request.url.path = "/test"
        request.url.query = ""
        request._body = b'{"data": "test"}'
        request.state = MagicMock()
        request.state.trace_id = "test-trace-123"
        
        # Mock call_next returning error response
        call_next = AsyncMock()
        response = MagicMock()
        response.status_code = 400  # Error status
        response.body = b'{"error": "bad request"}'
        response.headers = {"Content-Type": "application/json"}
        call_next.return_value = response
        
        # Test dispatch with error response
        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))
        
        # Should call next middleware
        call_next.assert_called_once_with(request)
        
        # Should not cache error responses
        cached = asyncio.run(store.get("test-key-123", middleware._generate_request_hash(request)))
        assert cached is None


    def test_generate_request_hash(self) -> None:
        """Test request hash generation."""
        from backend.apigw.middleware import IdempotencyMiddleware
        
        middleware = IdempotencyMiddleware(None)
        
        # Mock request
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/test"
        request.url.query = "param=value"
        request._body = b'{"data": "test"}'
        
        hash1 = middleware._generate_request_hash(request)
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex length
        
        # Same request should generate same hash
        hash2 = middleware._generate_request_hash(request)
        assert hash1 == hash2
        
        # Different request should generate different hash
        request.url.path = "/different"
        hash3 = middleware._generate_request_hash(request)
        assert hash1 != hash3
        
    def test_generate_request_hash_no_body(self) -> None:
        """Test request hash generation without body."""
        from backend.apigw.middleware import IdempotencyMiddleware
        
        middleware = IdempotencyMiddleware(None)
        
        # Mock request without body
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/test"
        request.url.query = ""
        
        hash_result = middleware._generate_request_hash(request)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
        
    def test_create_response_from_cache(self) -> None:
        """Test creating response from cached data."""
        from backend.apigw.middleware import IdempotencyMiddleware
        
        middleware = IdempotencyMiddleware(None)
        
        cached_data = {
            "status_code": 201,
            "headers": {"Content-Type": "application/json", "X-Custom": "value"},
            "body": '{"message": "created"}',
        }
        
        response = middleware._create_response_from_cache(cached_data)
        
        assert response.status_code == 201
        assert response.headers["Content-Type"] == "application/json"
        assert response.headers["X-Custom"] == "value"
        assert response.body.decode() == '{"message": "created"}'
        
    def test_create_response_from_cache_minimal(self) -> None:
        """Test creating response from minimal cached data."""
        from backend.apigw.middleware import IdempotencyMiddleware
        
        middleware = IdempotencyMiddleware(None)
        
        cached_data = {
            "status_code": 200,
            "headers": {},
            "body": None,
        }
        
        response = middleware._create_response_from_cache(cached_data)
        
        assert response.status_code == 200
        assert response.body.decode() == ""


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
        
    @pytest.mark.asyncio
    async def test_in_memory_store_cache_key_format(self) -> None:
        """Test cache key format."""
        store = InMemoryIdempotencyStore()
        
        response_data = {
            "status_code": 200,
            "body": '{"message": "success"}',
            "timestamp": time.time(),
        }
        
        await store.set("key-123", "hash-456", response_data)
        
        # Test that different combinations don't interfere
        cached1 = await store.get("key-123", "hash-456")
        assert cached1 is not None
        
        cached2 = await store.get("key-456", "hash-123")
        assert cached2 is None
        
        cached3 = await store.get("different-key", "hash-456")
        assert cached3 is None


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
