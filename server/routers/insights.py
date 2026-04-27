"""Insights REST router — Phase 3+ placeholder.

Provides stub endpoints that return empty lists or 501 responses
so the API surface is documented and clients get proper errors.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("")
async def list_insights() -> list[dict[str, str]]:
    """Return empty list — insights are not implemented until Phase 3."""
    return []


@router.patch("/{insight_id}")
async def update_insight(insight_id: int) -> None:
    """Reject insight updates — not implemented until Phase 3."""
    raise HTTPException(
        status_code=501,
        detail="Insights not implemented until Phase 3",
    )
