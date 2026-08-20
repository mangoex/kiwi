"""Legacy entrypoint retained only to fail closed.

Menu/catalog structure is now accepted exclusively through ``restaurant_os.internal_seed`` using
the versioned ``ensure_menu_catalog.v1`` operation. The governed manifest supplies explicit IDs and
reuses the former category, unit, SKU, price and recipe values without random generation.
"""


def get_engine() -> None:
    """Compatibility seam that must never be reached by the legacy entrypoint."""


def seed() -> None:
    raise RuntimeError("internal_seed_required")


if __name__ == "__main__":
    seed()
