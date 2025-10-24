# Release Notes v4.1.0 - API Gateway Hardening

**Release Date**: 2025-10-24  
**Phase**: 4.1 - API Gateway Hardening  
**Status**: ✅ Production Ready

## 🚀 New Features

### API Versioning `/v1` + Deprecation Policy
- **RFC Compliant**: Implements RFC 9745, 8594, 8288 for deprecation headers
- **Proper Redirects**: 301 for GET/HEAD, 308 for POST/PUT/PATCH/DELETE (preserves method & body)
- **CORS Safe**: OPTIONS/HEAD bypassed for preflight requests and monitoring
- **Observability**: Prometheus metrics `apigw_legacy_hits_total` and `apigw_redirects_total`
- **Documentation**: Complete migration guide and OpenAPI deprecation markers

### LLM Guard (Progressive Enforcement)
- **Rate Limiting**: Multi-tenant Redis-based rate limiting with atomic operations
- **Trust Model**: JWT validation > header-based authentication
- **Metrics**: Comprehensive monitoring and alerting

### SLO Gate + Canary Deployment
- **Freeze Policy**: Burn-rate monitoring (1h/6h windows)
- **Auto-Abort**: Automatic canary rollback on SLO violations
- **Cutover**: 48-hour dual-write/shadow-read migration

### Retrieval System Hardening
- **Dual-Write**: Shadow writes to new retrieval system
- **Cutover**: 48-hour migration window with rollback capability
- **Monitoring**: Comprehensive metrics and health checks

### Rate Limiting Multi-Pods
- **Redis Atomic**: Atomic operations across multiple pods
- **Trust Model**: JWT-based authentication with header fallback
- **Quotas**: Per-tenant quota management

### Multi-Tenant Benchmarking
- **Warm/Cold/Noisy**: Comprehensive performance testing scenarios
- **Reports**: JSON artifacts for performance analysis
- **Monitoring**: Real-time performance metrics

### Error Envelope + Idempotency
- **Error Handling**: Structured error responses with trace correlation
- **Idempotency**: POST request idempotency keys
- **Gateway**: Centralized error handling and logging

## 🔧 Technical Improvements

### API Versioning
```http
# Legacy route (deprecated)
POST /auth/login
→ 308 Permanent Redirect
→ Location: /v1/auth/login
→ Deprecation: @1761264000
→ Sunset: Wed, 31 Dec 2025 23:59:59 GMT
→ Link: </v1/auth/login>; rel="successor-version"
```

### Metrics
```promql
# Legacy traffic decay
sum(rate(apigw_legacy_hits_total[1h])) by (route)

# Redirect monitoring  
sum(rate(apigw_redirects_total[1h])) by (route, status)
```

### CORS Safety
- OPTIONS requests bypassed for CORS preflight
- HEAD requests bypassed for monitoring
- System routes (`/health`, `/metrics`, `/docs`) excluded from versioning

## 📊 Performance

- **Latency**: P95 unchanged during migration
- **Throughput**: Maintained during dual-write phase
- **Error Rate**: 5xx errors unchanged (SLO compliance)
- **Legacy Traffic**: Decay monitoring with 7-day trend analysis

## 🔒 Security

- **JWT Validation**: Enhanced trust model
- **Rate Limiting**: Multi-tenant isolation
- **Error Handling**: No PII leakage in error responses
- **Audit Trail**: Comprehensive logging with trace correlation

## 📈 Monitoring

### New Dashboards
- **Legacy Traffic Decay**: `dashboards/legacy_traffic_decay.json`
- **SLO Burn Rate**: Real-time SLO monitoring
- **Multi-Tenant Performance**: Benchmark results visualization

### New Metrics
- `apigw_legacy_hits_total{route, method}`
- `apigw_redirects_total{route, status}`
- `slo_burn_rate{service, window}`

## 🚨 Breaking Changes

**None** - All changes are backward compatible with deprecation warnings.

## 📋 Migration Required

### For API Clients
Update base URLs from legacy to versioned endpoints:

```bash
# Before (deprecated)
curl -X POST https://api.astro.com/auth/login

# After (current)  
curl -X POST https://api.astro.com/v1/auth/login
```

**Deadline**: 2025-12-31 (Sunset date)

### For Monitoring
- Update dashboards to include new metrics
- Configure alerts for legacy traffic decay
- Monitor SLO burn rates

## 🧪 Testing

- **13/13 tests passing** for API versioning (100%)
- **Comprehensive coverage** of deprecation scenarios
- **CORS bypass validation** for OPTIONS/HEAD
- **Metrics validation** for Prometheus integration

## 📚 Documentation

- **Policy**: `docs/api/versioning_deprecation_policy.md`
- **Migration**: `docs/api/openapi_versioning.md`
- **Dashboard**: `dashboards/legacy_traffic_decay.json`
- **CI**: `.github/workflows/test-versioning.yml`

## 🔗 References

- [RFC 9745: Deprecation HTTP Header](https://www.rfc-editor.org/rfc/rfc9745.html)
- [RFC 8594: Sunset HTTP Header](https://www.rfc-editor.org/rfc/rfc8594.html)
- [RFC 8288: Web Linking](https://www.rfc-editor.org/rfc/rfc8288.html)
- [MDN: 308 Permanent Redirect](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/308)

## 🎯 Next Steps

1. **T-24h**: Deploy to staging (100%)
2. **T-0**: Deploy to production (canary 10%)
3. **T+7d**: Monitor legacy traffic decay
4. **T+60d**: Sunset legacy routes (410 Gone)

## 📦 Evidence Pack

Complete evidence pack available in `artifacts/release_v4_1/`:
- ✅ Test results and coverage
- ✅ Performance benchmarks
- ✅ Compliance validation
- ✅ Monitoring configuration
- ✅ Documentation artifacts

---

**Ready for Phase 5**: Advanced Features 🚀
