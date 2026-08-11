"""
Analytics: what this user has done, and how well it scored.

One endpoint, because the page is one screen. The quality half is only possible because
this system grades its own output: every generation is scored by a separate judge model
and every verdict is logged, passes included, so the numbers are measured rather than
estimated.
"""

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..services import analytics as service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def overview(user: dict = Depends(get_current_user)):
    """Activity counts and the evaluation score distribution, for this user."""
    return service.overview(user["id"])
