import httpx
from starlette import status

from config import app_config


class SurpassRequestService:
    def __init__(self):
        self.base_url = app_config.SURPASS_API_BASE_URL
        self.bearer_token = app_config.SURPASS_TOKEN
        self.api_prefix = "api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }

    async def make_request(self, endpoint: str, method: str = "POST", data=None, params=None):
        url = f"{self.base_url}/{self.api_prefix}/{endpoint}"
        response = None

        try:
            timeout = httpx.Timeout(30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, params=params, headers=self.headers)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=self.headers)
                else:
                    return None, status.HTTP_400_BAD_REQUEST, "Unsupported HTTP method"
                response_data = response.json()

                if response.status_code >= 400:
                    error_message = response_data.get("message", "API returned an error")
                    return response_data, response.status_code, error_message
                return response.json(), response.status_code, None

        except httpx.RequestError as e:
            return None, status.HTTP_500_INTERNAL_SERVER_ERROR, f"Request error: {str(e)}"
        except httpx.HTTPStatusError as e:
            return None, e.response.status_code, f"HTTP error: {str(e)}"
        except Exception as e:
            return None, status.HTTP_500_INTERNAL_SERVER_ERROR, f"Unexpected error: {str(e)}"
