from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os.database import get_session
from restaurant_os.platform_data import (
    bootstrap_status,
    list_branches,
    list_catalog_products,
    list_organizations,
)

router = APIRouter(prefix="/api/v1", tags=["platform-api"])


SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/platform/bootstrap-status")
def get_bootstrap_status(session: SessionDep) -> dict[str, Any]:
    return _database_response(lambda: bootstrap_status(session))


@router.get("/organizations")
def get_organizations(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_organizations(session))


@router.get("/branches")
def get_branches(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_branches(session))


@router.get("/catalog/products")
def get_catalog_products(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_catalog_products(session))


def _database_response(operation):
    try:
        return operation()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database_unavailable") from exc
