"""
Domain Exceptions — Tipificación de errores en la capa de aplicación/infraestructura.

Arquitectura Hexagonal: Define contratos de error explícitos que el puerto
(repositorio) puede lanzar para permitir que el cliente (use case/handler)
tome decisiones basadas en el tipo de error, no en valores mágicos de retorno.

Ref: LSP (Liskov Substitution Principle) — los clientes pueden confiar
en que una RepositoryError significa que ocurrió un fallo de infraestructura,
no que el dato simplemente no existe.
"""


class RepositoryError(Exception):
    """Error genérico de infraestructura de repositorio.

    Indica que una operación de repositorio falló debido a un problema
    de conectividad, permisos, corrupción de datos u otro error de
    infraestructura — NO porque el dato no exista.
    """
    pass


class ConnectionError(RepositoryError):
    """Fallo específico de conexión con la base de datos.

    Distinto de un error de datos: significa que la BD no es accesible,
    no que una consulta retornó un conjunto vacío.
    """
    pass
