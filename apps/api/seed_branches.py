"""Legacy entrypoint retained only to fail closed.

Branch topology is now accepted exclusively through ``restaurant_os.internal_seed`` using the
versioned ``ensure_branch_topology.v1`` operation. Historical random sales/mock generation is not
part of the governed command.
"""


def get_engine() -> None:
    """Compatibility seam that must never be reached by the legacy entrypoint."""


def seed() -> None:
    raise RuntimeError("internal_seed_required")


if __name__ == "__main__":
    seed()
