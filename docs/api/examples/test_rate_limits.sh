#!/bin/bash
# Exemples cURL pour tester les rate limits et quotas

# Configuration
API_BASE_URL="https://api.example.com"
JWT_TOKEN="your-jwt-token-here"

# Headers communs
COMMON_HEADERS=(
    -H "Authorization: Bearer $JWT_TOKEN"
    -H "Content-Type: application/json"
)

echo "=== Test Rate Limiting ==="
echo ""

# Test 1: Requête normale (dans la limite)
echo "1. Requête normale (dans la limite):"
curl -s "${COMMON_HEADERS[@]}" \
     "$API_BASE_URL/v1/chat/message" \
     -d '{"message": "Hello, this is a test message"}' \
     -w "\nHTTP Status: %{http_code}\n" \
     -w "Rate Limit Headers:\n" \
     -w "  X-RateLimit-Limit: %{header_x-ratelimit-limit}\n" \
     -w "  X-RateLimit-Remaining: %{header_x-ratelimit-remaining}\n" \
     -w "  X-RateLimit-Reset: %{header_x-ratelimit-reset}\n" \
     -w "  Retry-After: %{header_retry-after}\n\n"

# Test 2: Dépassement de rate limit (simuler avec plusieurs requêtes rapides)
echo "2. Test de dépassement de rate limit (plusieurs requêtes rapides):"
for i in {1..65}; do
    echo "Requête $i:"
    response=$(curl -s "${COMMON_HEADERS[@]}" \
                   "$API_BASE_URL/v1/chat/message" \
                   -d "{\"message\": \"Test message $i\"}" \
                   -w "%{http_code}")
    
    if [[ "$response" == *"429"* ]]; then
        echo "  → Rate limit atteint (429)"
        # Récupérer les headers de rate limit
        curl -s "${COMMON_HEADERS[@]}" \
             "$API_BASE_URL/v1/chat/message" \
             -d "{\"message\": \"Test after limit\"}" \
             -I | grep -E "(HTTP|X-RateLimit|Retry-After)"
        break
    else
        echo "  → OK (200)"
    fi
    
    # Petite pause pour éviter de surcharger
    sleep 0.1
done

echo ""

# Test 3: Test avec tenant header (devrait être ignoré sauf trafic interne)
echo "3. Test avec header X-Tenant-ID (non-internal):"
curl -s "${COMMON_HEADERS[@]}" \
     -H "X-Tenant-ID: fake-tenant" \
     "$API_BASE_URL/v1/chat/message" \
     -d '{"message": "Test with fake tenant header"}' \
     -w "\nHTTP Status: %{http_code}\n" \
     -w "Response Body:\n" \
     -w "%{response_body}\n\n"

# Test 4: Test avec trafic interne (si configuré)
echo "4. Test avec trafic interne (X-Internal-Auth):"
curl -s "${COMMON_HEADERS[@]}" \
     -H "X-Internal-Auth: internal-token" \
     -H "X-Tenant-ID: internal-tenant" \
     "$API_BASE_URL/v1/chat/message" \
     -d '{"message": "Test with internal auth"}' \
     -w "\nHTTP Status: %{http_code}\n" \
     -w "Response Body:\n" \
     -w "%{response_body}\n\n"

# Test 5: Test endpoint exempté (/health)
echo "5. Test endpoint exempté (/health):"
curl -s "$API_BASE_URL/health" \
     -w "\nHTTP Status: %{http_code}\n" \
     -w "Rate Limit Headers (devraient être absents):\n" \
     -w "  X-RateLimit-Limit: %{header_x-ratelimit-limit}\n" \
     -w "  X-RateLimit-Remaining: %{header_x-ratelimit-remaining}\n\n"

# Test 6: Test quota retrieval
echo "6. Test quota retrieval:"
curl -s "${COMMON_HEADERS[@]}" \
     "$API_BASE_URL/v1/retrieval/search" \
     -d '{"query": "test query", "limit": 10}' \
     -w "\nHTTP Status: %{http_code}\n" \
     -w "Rate Limit Headers:\n" \
     -w "  X-RateLimit-Limit: %{header_x-ratelimit-limit}\n" \
     -w "  X-RateLimit-Remaining: %{header_x-ratelimit-remaining}\n" \
     -w "  X-RateLimit-Reset: %{header_x-ratelimit-reset}\n\n"

# Test 7: Test avec JWT invalide
echo "7. Test avec JWT invalide:"
curl -s -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
     -H "Content-Type: application/json" \
     "$API_BASE_URL/v1/chat/message" \
     -d '{"message": "Test with invalid JWT"}' \
     -w "\nHTTP Status: %{http_code}\n" \
     -w "Response Body:\n" \
     -w "%{response_body}\n\n"

# Test 8: Test de respect du Retry-After
echo "8. Test de respect du Retry-After:"
echo "Faire une requête qui dépasse la limite, puis attendre le Retry-After..."

# Simuler un dépassement
for i in {1..65}; do
    curl -s "${COMMON_HEADERS[@]}" \
         "$API_BASE_URL/v1/chat/message" \
         -d "{\"message\": \"Burst test $i\"}" > /dev/null
done

# Récupérer le Retry-After
retry_after=$(curl -s "${COMMON_HEADERS[@]}" \
                   "$API_BASE_URL/v1/chat/message" \
                   -d '{"message": "Test after burst"}' \
                   -I | grep -i "retry-after" | cut -d' ' -f2 | tr -d '\r')

if [[ -n "$retry_after" ]]; then
    echo "Retry-After détecté: ${retry_after}s"
    echo "Attente de ${retry_after} secondes..."
    sleep "$retry_after"
    
    echo "Test après attente:"
    curl -s "${COMMON_HEADERS[@]}" \
         "$API_BASE_URL/v1/chat/message" \
         -d '{"message": "Test after retry wait"}' \
         -w "\nHTTP Status: %{http_code}\n" \
         -w "Rate Limit Headers:\n" \
         -w "  X-RateLimit-Limit: %{header_x-ratelimit-limit}\n" \
         -w "  X-RateLimit-Remaining: %{header_x-ratelimit-remaining}\n"
else
    echo "Aucun Retry-After détecté"
fi

echo ""
echo "=== Tests terminés ==="
echo ""
echo "Pour analyser les résultats:"
echo "1. Vérifiez les codes de statut HTTP (200, 429)"
echo "2. Examinez les headers X-RateLimit-*"
echo "3. Vérifiez la présence du header Retry-After pour les 429"
echo "4. Consultez les logs du serveur pour les détails (trace_id)"
echo ""
echo "Métriques Prometheus à surveiller:"
echo "- apigw_rate_limit_decisions_total{route,result}"
echo "- apigw_rate_limit_blocks_total{route,reason}"
echo "- apigw_tenant_spoof_attempts_total{route}"
