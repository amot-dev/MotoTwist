from fastapi import HTTPException
from starlette.datastructures import UploadFile
from typing import NoReturn, TypeGuard

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