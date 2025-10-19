from fastapi import HTTPException


def require_entitlement(user: dict, entitlement: str):
    ents = set(user.get("entitlements", []))
    if entitlement not in ents:
        raise HTTPException(status_code=403, detail=f"missing_entitlement:{entitlement}")
