# OpenAPI Documentation - API Versioning

## Deprecated Routes

Les routes suivantes sont dépréciées et seront supprimées le **31 décembre 2025** :

### Authentication Routes

- **POST** `/auth/login` → **POST** `/v1/auth/login`
- **POST** `/auth/signup` → **POST** `/v1/auth/signup`
- **POST** `/auth/logout` → **POST** `/v1/auth/logout`

### Horoscope Routes

- **POST** `/horoscope/natal` → **POST** `/v1/horoscope/natal`
- **GET** `/horoscope/today` → **GET** `/v1/horoscope/today`
- **GET** `/horoscope/chart/{id}` → **GET** `/v1/horoscope/chart/{id}`

### Chat Routes

- **POST** `/chat/advise` → **POST** `/v1/chat/advise`
- **POST** `/chat/ask` → **POST** `/v1/chat/ask`
- **GET** `/chat/history` → **GET** `/v1/chat/history`

## Migration Guide

### 1. Update Base URLs

```bash
# Before (deprecated)
curl -X POST https://api.astro.com/auth/login

# After (current)
curl -X POST https://api.astro.com/v1/auth/login
```

### 2. Handle Deprecation Headers

Les routes legacy retournent les headers suivants :

```http
HTTP/1.1 308 Permanent Redirect
Location: /v1/auth/login
Deprecation: @1761264000
Sunset: Wed, 31 Dec 2025 23:59:59 GMT
Link: </v1/auth/login>; rel="successor-version", <https://docs.astro.com/api/versioning>; rel="deprecation"
Warning: 299 - "Deprecated API. Use /v1/auth/login"
Cache-Control: public, max-age=86400
```

### 3. Client Implementation

```python
import requests
from datetime import datetime

def make_api_request(url, **kwargs):
    response = requests.request(url=url, **kwargs)
    
    # Check for deprecation warnings
    if 'Deprecation' in response.headers:
        deprecation_timestamp = response.headers['Deprecation']
        sunset_date = response.headers.get('Sunset')
        
        print(f"⚠️  Deprecated API used: {url}")
        print(f"   Deprecated since: {deprecation_timestamp}")
        print(f"   Sunset date: {sunset_date}")
        
        # Follow redirect if present
        if 'Location' in response.headers:
            new_url = response.headers['Location']
            print(f"   Redirecting to: {new_url}")
            return requests.request(url=new_url, **kwargs)
    
    return response
```

## Timeline

- **2025-10-24** : Début de la dépréciation (headers `Deprecation` ajoutés)
- **2025-12-31** : Date de sunset (routes legacy supprimées)
- **2026-01-01** : Routes legacy retournent `410 Gone`

## Support

- 📖 [Documentation complète](https://docs.astro.com/api/versioning)
- 🐛 [Signaler un problème](https://github.com/astro/api/issues)
- 💬 [Support technique](mailto:support@astro.com)

## References

- [RFC 9745: The Deprecation HTTP Response Header Field](https://www.rfc-editor.org/rfc/rfc9745.html)
- [RFC 8594: The Sunset HTTP Header Field](https://www.rfc-editor.org/rfc/rfc8594.html)
- [RFC 8288: Web Linking](https://www.rfc-editor.org/rfc/rfc8288.html)
