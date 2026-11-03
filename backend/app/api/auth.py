"""Authentication endpoints (simple demo auth)."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
def session():
    """Get current session info (demo - no real auth)."""
    return {
        "authenticated": True,
        "username": "responder",
        "login_configured": False,
    }
