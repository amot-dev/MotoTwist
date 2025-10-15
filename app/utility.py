from fastapi import FastAPI, HTTPException
from fastapi.openapi.utils import get_openapi
from starlette.datastructures import UploadFile
from starlette.routing import Route
from typing import Any, Callable, NoReturn, TypeGuard

from app.config import logger


def raise_http(detail: str, status_code: int = 500, exception: Exception | None = None) -> NoReturn:
    """
    Log an error and its stack trace, then raise an HTTPException.

    :param detail: The error message to send to the client.
    :param status_code: Optional HTTP status code. Defaults to 500.
    :param exception: Optional Exception object from which to create stack trace. Defaults to None.
    :raises HTTPException: Always.
    """
    if exception:
        logger.exception(detail)
        raise HTTPException(status_code=status_code, detail=detail) from exception
    else:
        logger.error(detail)
        raise HTTPException(status_code=status_code, detail=detail)


def is_form_value_string(value: UploadFile | str | None) -> TypeGuard[str]:
    """
    Type Guard to validate form values as strings.

    :param value: The form value to validate.
    :return: True if the value is a string, False otherwise.
    """
    """Returns True if the form value is a string, acting as a type guard."""
    return value is not None and isinstance(value, str)


def update_schema_name(app: FastAPI, function: Callable[..., Any], name: str) -> None:
    """
    Updates the Pydantic schema name for a FastAPI function that takes
    in a fastapi.UploadFile = File(...) or bytes = File(...).

    This is a known issue that was reported on FastAPI#1442 in which
    the schema for file upload routes were auto-generated with no
    customization options. This renames the auto-generated schema to
    something more useful and clear.

    <h2>Source</h2>
    <a href=https://github.com/fastapi/fastapi/issues/1442#issuecomment-788633654>
        https://github.com/fastapi/fastapi/issues/1442#issuecomment-788633654
    </a>

    :param app: The FastAPI application to modify.
    :param function: The function object to modify.
    :param name: The new name of the schema.
    """
    for route in app.routes:
        if isinstance(route, Route):
            if route.endpoint is function:
                route.body_field.type_.__name__ = name  # pyright: ignore [reportUnknownMemberType, reportAttributeAccessIssue]
                break



def sort_schema_names(app: FastAPI):
    """
    Sorts the component schemas in the FastAPI OpenAPI documentation alphabetically.

    This utility addresses cases where the generated schemas do not appear in a
    clean alphabetical order. This can occur after programmatically renaming
    auto-generated schemas (e.g., for file uploads), as the original internal
    sort order might be preserved.

    By calling this function after all routes have been added and schemas have
    been modified, it forces a final, clean alphabetical re-sorting of the
    schemas before the documentation is rendered.

    :param app: The FastAPI application whose OpenAPI schema needs to be sorted.
    """
    # Get or create openapi_schema
    openapi_schema = app.openapi_schema if app.openapi_schema else get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags
    )

    # Get the dictionary of schemas
    all_schemas = openapi_schema.get("components", {}).get("schemas", {})
    if all_schemas:
        # Sort the dictionary alphabetically by key (the schema name)
        sorted_schemas = dict(sorted(all_schemas.items()))
        print(sorted_schemas)
        # Replace the old schemas with the newly sorted ones
        openapi_schema["components"]["schemas"] = sorted_schemas

    # Save
    app.openapi_schema = openapi_schema