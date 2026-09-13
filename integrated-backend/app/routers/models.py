"""Selectable generator models."""

from fastapi import APIRouter, Depends

from learnmate.llm.catalog import public_models

from ..deps import get_current_user

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def list_models(user: dict = Depends(get_current_user)):
    """
    Generators this server can switch between.

    Omitted `model_id` on generate/chat still uses LEARNMATE_GENERATOR_MODEL.
    Experimental entries are labelled; they are never the silent default.
    """
    return public_models()
