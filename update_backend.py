import os

operations_code = """
def update_user(
    session: Session,
    user_id: str,
    email: str | None = None,
    display_name: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    
    update_data = {}
    if email is not None:
        update_data["email"] = email.strip().lower()
    if display_name is not None:
        update_data["display_name"] = display_name.strip()
    
    if update_data:
        update_data["updated_at"] = _now()
        session.execute(
            sa.update(models.users)
            .where(models.users.c.id == user_id)
            .values(**update_data)
        )
        _audit(session, action="user.updated", entity_type="user", entity_id=user_id, payload=update_data, actor_user_id=actor_id)
        session.commit()
    return {"id": user_id, **update_data}

def delete_user(
    session: Session,
    user_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    session.execute(
        sa.update(models.users)
        .where(models.users.c.id == user_id)
        .values(status="suspended", updated_at=_now())
    )
    _audit(session, action="user.deleted", entity_type="user", entity_id=user_id, payload={"status": "suspended"}, actor_user_id=actor_id)
    session.commit()
    return {"id": user_id, "status": "suspended"}

def update_branch(
    session: Session,
    branch_id: str,
    name: str | None = None,
    code: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    
    update_data = {}
    if name is not None:
        update_data["name"] = name.strip()
    if code is not None:
        update_data["code"] = code.strip()
        
    if update_data:
        update_data["updated_at"] = _now()
        session.execute(
            sa.update(models.branches)
            .where(models.branches.c.id == branch_id)
            .values(**update_data)
        )
        _audit(session, action="branch.updated", entity_type="branch", entity_id=branch_id, payload=update_data, actor_user_id=actor_id)
        session.commit()
    return {"id": branch_id, **update_data}

def delete_branch(
    session: Session,
    branch_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    session.execute(
        sa.update(models.branches)
        .where(models.branches.c.id == branch_id)
        .values(status="inactive", updated_at=_now())
    )
    _audit(session, action="branch.deleted", entity_type="branch", entity_id=branch_id, payload={"status": "inactive"}, actor_user_id=actor_id)
    session.commit()
    return {"id": branch_id, "status": "inactive"}

def update_product(
    session: Session,
    product_id: str,
    name: str | None = None,
    sku: str | None = None,
    price_cents: int | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    
    update_data = {}
    if name is not None:
        update_data["name"] = name.strip()
    if sku is not None:
        update_data["sku"] = sku.strip().upper()
    if price_cents is not None:
        update_data["price_cents"] = price_cents
        
    if update_data:
        update_data["updated_at"] = _now()
        session.execute(
            sa.update(models.products)
            .where(models.products.c.id == product_id)
            .values(**update_data)
        )
        _audit(session, action="product.updated", entity_type="product", entity_id=product_id, payload=update_data, actor_user_id=actor_id)
        session.commit()
    return {"id": product_id, **update_data}

def delete_product(
    session: Session,
    product_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    session.execute(
        sa.update(models.products)
        .where(models.products.c.id == product_id)
        .values(status="inactive", updated_at=_now())
    )
    _audit(session, action="product.deleted", entity_type="product", entity_id=product_id, payload={"status": "inactive"}, actor_user_id=actor_id)
    session.commit()
    return {"id": product_id, "status": "inactive"}
"""

api_endpoints = """
@router.put("/users/{user_id}")
def put_user(
    user_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    email = payload.get("email")
    display_name = payload.get("display_name")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_user(session, user_id, email, display_name, actor_id)
    )

@router.delete("/users/{user_id}")
def delete_user_endpoint(
    user_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: delete_user(session, user_id, actor_id)
    )

@router.put("/branches/{branch_id}")
def put_branch(
    branch_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    code = payload.get("code")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_branch(session, branch_id, name, code, actor_id)
    )

@router.delete("/branches/{branch_id}")
def delete_branch_endpoint(
    branch_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: delete_branch(session, branch_id, actor_id)
    )

@router.put("/catalog/products/{product_id}")
def put_catalog_product(
    product_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    sku = payload.get("sku")
    price_cents = payload.get("price_cents")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_product(session, product_id, name, sku, price_cents, actor_id)
    )

@router.delete("/catalog/products/{product_id}")
def delete_catalog_product_endpoint(
    product_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: delete_product(session, product_id, actor_id)
    )

"""

operations_path = r"c:\Users\Miguel Gonzalez\Downloads\Kiwi\apps\api\restaurant_os\operations.py"
with open(operations_path, "a") as f:
    f.write(operations_code)

api_path = r"c:\Users\Miguel Gonzalez\Downloads\Kiwi\apps\api\restaurant_os\api.py"
with open(api_path, "r") as f:
    api_content = f.read()

# Add imports to api.py
imports_str = """
    update_user,
    delete_user,
    update_branch,
    delete_branch,
    update_product,
    delete_product,
"""
api_content = api_content.replace(
    "create_product,",
    "create_product," + imports_str,
    1
)

# Add endpoints before def _database_response
api_content = api_content.replace(
    "def _database_response(operation):",
    api_endpoints + "\ndef _database_response(operation):",
    1
)

with open(api_path, "w") as f:
    f.write(api_content)

print("Backend updated successfully.")
