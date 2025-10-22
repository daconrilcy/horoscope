#!/bin/bash
# Check for forbidden typing aliases in Python files

set -e

echo "Checking for forbidden typing aliases..."

# Check for typing.List, typing.Dict, typing.Optional, typing.Str
if grep -r "typing\.List\|typing\.Dict\|typing\.Optional\|typing\.Str" backend/ scripts/ tests/ --include="*.py"; then
    echo "❌ Found forbidden typing aliases!"
    echo "Use native types: list, dict, str, and unions with | instead"
    exit 1
fi

echo "✅ No forbidden typing aliases found"
