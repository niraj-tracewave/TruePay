from typing import Union

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.responses import JSONResponse, Response

from app_logging import app_logger


class ApiResponse:
    @staticmethod
    def create_response(success: bool, message: str, status_code: int, data: list = None) -> JSONResponse:
        data_dict = {"message": message, "success": success, "status_code": status_code}
        if data:
            if 'data' in data:
                data_dict |= data
            else:
                data_dict['data'] = data
        else:
            data_dict['data'] = {}
        response_headers = {"Content-Type": "application/json"}
        return JSONResponse(
            content=jsonable_encoder(data_dict),
            status_code=status.HTTP_200_OK,
            headers=response_headers
            )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Union[JSONResponse, Response]:
    errors = exc.errors()
    formatted_errors = []

    for error in errors:
        loc = error.get("loc", [])
        field = ".".join(str(part) for part in loc[1:]) if len(loc) > 1 else loc[-1] if loc else "unknown"
        msg = error.get("msg", "Invalid input")
        formatted_errors.append(f"'{field}' - {msg}")

    app_logger.error(f"Validation error on {request.method} {request.url.path} | Errors: {formatted_errors[0]}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder(
            {
                "success": False,
                "message": formatted_errors[0],
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": {}
            }
        )
    )
