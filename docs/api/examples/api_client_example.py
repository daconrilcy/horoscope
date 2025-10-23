#!/usr/bin/env python3
"""
Exemple de client Python pour gérer les rate limits et quotas de l'API.

Ce script démontre comment :
- Gérer les réponses 429 (Too Many Requests)
- Respecter les headers Retry-After
- Implémenter un backoff exponentiel
- Utiliser les métriques de rate limiting
"""

import time
import requests
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ErrorCode(Enum):
    """Codes d'erreur de l'API."""
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class RateLimitInfo:
    """Informations de rate limiting."""
    limit: int
    remaining: int
    reset: int
    retry_after: Optional[int] = None


class APIError(Exception):
    """Exception de base pour les erreurs API."""
    
    def __init__(self, code: str, message: str, trace_id: Optional[str] = None, details: Dict[str, Any] = None):
        self.code = code
        self.message = message
        self.trace_id = trace_id
        self.details = details or {}
        super().__init__(f"{code}: {message}")


class RateLimitError(APIError):
    """Erreur de rate limiting."""
    
    def __init__(self, code: str, message: str, trace_id: Optional[str], details: Dict[str, Any], retry_after: int):
        super().__init__(code, message, trace_id, details)
        self.retry_after = retry_after


class QuotaExceededError(APIError):
    """Erreur de quota dépassé."""
    
    def __init__(self, code: str, message: str, trace_id: Optional[str], details: Dict[str, Any], retry_after: int):
        super().__init__(code, message, trace_id, details)
        self.retry_after = retry_after


class APIClient:
    """Client API avec gestion des rate limits."""
    
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        })
    
    def _parse_rate_limit_headers(self, response: requests.Response) -> RateLimitInfo:
        """Parse les headers de rate limiting."""
        headers = response.headers
        
        return RateLimitInfo(
            limit=int(headers.get('X-RateLimit-Limit', 0)),
            remaining=int(headers.get('X-RateLimit-Remaining', 0)),
            reset=int(headers.get('X-RateLimit-Reset', 0)),
            retry_after=int(headers.get('Retry-After', 0)) if headers.get('Retry-After') else None
        )
    
    def _handle_error_response(self, response: requests.Response) -> None:
        """Gère les réponses d'erreur."""
        try:
            error_data = response.json()
        except ValueError:
            response.raise_for_status()
        
        code = error_data.get('code', 'UNKNOWN_ERROR')
        message = error_data.get('message', 'Unknown error')
        trace_id = error_data.get('trace_id')
        details = error_data.get('details', {})
        
        # Gestion spécifique des erreurs de rate limiting
        if code == ErrorCode.RATE_LIMITED.value:
            retry_after = details.get('retry_after', 1)
            raise RateLimitError(code, message, trace_id, details, retry_after)
        elif code == ErrorCode.QUOTA_EXCEEDED.value:
            retry_after = details.get('retry_after', 3600)
            raise QuotaExceededError(code, message, trace_id, details, retry_after)
        elif code in [ErrorCode.UNAUTHORIZED.value, ErrorCode.FORBIDDEN.value]:
            raise APIError(code, message, trace_id, details)
        elif response.status_code >= 500:
            raise APIError(code, message, trace_id, details)
        else:
            raise APIError(code, message, trace_id, details)
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Fait une requête HTTP avec gestion d'erreur."""
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        
        if response.status_code != 200:
            self._handle_error_response(response)
        
        return response
    
    def make_request_with_retry(self, method: str, endpoint: str, max_retries: int = 3, **kwargs) -> Dict[str, Any]:
        """Fait une requête avec retry automatique pour les rate limits."""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                response = self._make_request(method, endpoint, **kwargs)
                
                # Parse rate limit info
                rate_limit_info = self._parse_rate_limit_headers(response)
                
                # Log rate limit status
                print(f"Rate limit: {rate_limit_info.remaining}/{rate_limit_info.limit} remaining")
                
                return response.json()
                
            except RateLimitError as e:
                last_exception = e
                print(f"Rate limited (attempt {attempt + 1}/{max_retries}): {e.message}")
                print(f"Waiting {e.retry_after} seconds...")
                time.sleep(e.retry_after)
                
            except QuotaExceededError as e:
                last_exception = e
                print(f"Quota exceeded (attempt {attempt + 1}/{max_retries}): {e.message}")
                print(f"Waiting {e.retry_after} seconds...")
                time.sleep(e.retry_after)
                
            except APIError as e:
                # Ne pas retry pour les erreurs d'auth ou autres erreurs client
                if e.code in [ErrorCode.UNAUTHORIZED.value, ErrorCode.FORBIDDEN.value]:
                    raise e
                last_exception = e
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2 ** attempt)  # Backoff exponentiel
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2 ** attempt)  # Backoff exponentiel
        
        if last_exception:
            raise last_exception
        raise Exception("Max retries exceeded")
    
    def send_chat_message(self, message: str) -> Dict[str, Any]:
        """Envoie un message de chat."""
        return self.make_request_with_retry(
            'POST',
            '/v1/chat/message',
            json={'message': message}
        )
    
    def search_retrieval(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Effectue une recherche."""
        return self.make_request_with_retry(
            'POST',
            '/v1/retrieval/search',
            json={'query': query, 'limit': limit}
        )
    
    def get_health(self) -> Dict[str, Any]:
        """Vérifie la santé de l'API."""
        return self.make_request_with_retry('GET', '/health')


def main():
    """Exemple d'utilisation du client API."""
    
    # Configuration
    API_BASE_URL = "https://api.example.com"
    JWT_TOKEN = "your-jwt-token-here"
    
    # Créer le client
    client = APIClient(API_BASE_URL, JWT_TOKEN)
    
    print("=== Test du client API avec gestion des rate limits ===\n")
    
    # Test 1: Requête normale
    print("1. Test requête normale:")
    try:
        response = client.send_chat_message("Hello, this is a test message")
        print(f"   Réponse: {response}")
    except Exception as e:
        print(f"   Erreur: {e}")
    
    print()
    
    # Test 2: Test de rate limiting (plusieurs requêtes rapides)
    print("2. Test de rate limiting (burst de requêtes):")
    for i in range(65):  # Dépasser la limite de 60
        try:
            response = client.send_chat_message(f"Test message {i}")
            print(f"   Requête {i}: OK")
        except RateLimitError as e:
            print(f"   Requête {i}: Rate limited - {e.message}")
            print(f"   Retry-After: {e.retry_after}s")
            break
        except Exception as e:
            print(f"   Requête {i}: Erreur - {e}")
            break
    
    print()
    
    # Test 3: Test avec backoff exponentiel
    print("3. Test avec backoff exponentiel:")
    try:
        response = client.send_chat_message("Test after rate limit")
        print(f"   Réponse après attente: {response}")
    except Exception as e:
        print(f"   Erreur: {e}")
    
    print()
    
    # Test 4: Test endpoint exempté
    print("4. Test endpoint exempté (/health):")
    try:
        response = client.get_health()
        print(f"   Health check: {response}")
    except Exception as e:
        print(f"   Erreur: {e}")
    
    print()
    
    # Test 5: Test quota retrieval
    print("5. Test quota retrieval:")
    try:
        response = client.search_retrieval("test query", limit=10)
        print(f"   Recherche: {response}")
    except Exception as e:
        print(f"   Erreur: {e}")
    
    print()
    print("=== Tests terminés ===")


if __name__ == "__main__":
    main()
