class DomainError(Exception):
    """
    Excepción base para todos los errores de dominio de RestaurantOS.
    Nunca se debe lanzar directamente, usar subclases.
    """
    pass

class ValidationError(DomainError):
    """Lanzada cuando un Value Object o Entidad tiene datos inválidos."""
    pass

class StateTransitionError(DomainError):
    """Lanzada cuando se intenta una transición inválida en una máquina de estados."""
    pass

class ResourceNotFoundError(DomainError):
    """Lanzada cuando una entidad requerida para una operación de dominio no existe."""
    pass

class BusinessRuleViolationError(DomainError):
    """Lanzada cuando se rompe una regla de negocio específica (ej: ciclo en recetas, inventario negativo sin autorización)."""
    pass
