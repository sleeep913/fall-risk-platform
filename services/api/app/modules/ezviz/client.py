from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.modules.ezviz.errors import EzvizApiError

TOKEN_INVALID_CODES = {"10002", "110002", "110003", "310002"}
RETRYABLE_CODES = {"149999", "150000"}


@dataclass(frozen=True)
class EzvizPackageActivationResult:
    meta_code: str
    active_code: int
    message: str


class EzvizClient:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    async def request_token(self) -> tuple[str, int]:
        app_key = self._settings.ezviz_app_key
        app_secret = self._settings.ezviz_app_secret
        if app_key is None or app_secret is None:
            raise ValueError("EZVIZ credentials are not configured")
        payload = await self._post_form(
            "/api/lapp/token/get",
            {
                "appKey": app_key.get_secret_value(),
                "appSecret": app_secret.get_secret_value(),
            },
        )
        data = _require_mapping(payload.get("data"), "token response data")
        token = data.get("accessToken")
        expire_time = data.get("expireTime")
        if not isinstance(token, str) or not token:
            raise EzvizApiError("EZVIZ token response omitted accessToken")
        try:
            expires_at_ms = int(expire_time)
        except (TypeError, ValueError) as exc:
            raise EzvizApiError("EZVIZ token response contained invalid expireTime") from exc
        return token, expires_at_ms

    async def list_devices(
        self, access_token: str, page_start: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int | None]:
        payload = await self._post_form(
            "/api/lapp/device/list",
            {
                "accessToken": access_token,
                "pageStart": page_start,
                "pageSize": page_size,
            },
        )
        items = payload.get("data")
        if not isinstance(items, list):
            raise EzvizApiError("EZVIZ device list response contained invalid data")
        page = payload.get("page")
        total = None
        if isinstance(page, Mapping):
            try:
                total = int(page["total"])
            except (KeyError, TypeError, ValueError):
                pass
        return [_require_mapping(item, "device") for item in items], total

    async def list_channels(
        self, access_token: str, page_start: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int | None]:
        payload = await self._post_form(
            "/api/lapp/camera/list",
            {
                "accessToken": access_token,
                "pageStart": page_start,
                "pageSize": page_size,
            },
        )
        items = payload.get("data")
        if not isinstance(items, list):
            raise EzvizApiError("EZVIZ channel list response contained invalid data")
        page = payload.get("page")
        total = None
        if isinstance(page, Mapping):
            try:
                total = int(page["total"])
            except (KeyError, TypeError, ValueError):
                pass
        return [_require_mapping(item, "channel") for item in items], total

    async def get_device_info(
        self, access_token: str, device_serial: str
    ) -> dict[str, Any]:
        payload = await self._post_form(
            "/api/lapp/device/info",
            {"accessToken": access_token, "deviceSerial": device_serial},
        )
        return _require_mapping(payload.get("data"), "device info")

    async def activate_device_package(
        self,
        access_token: str,
        package_code: str,
        device_serial: str,
        channel_no: int,
    ) -> EzvizPackageActivationResult:
        try:
            response = await self._http_client.post(
                f"{self._settings.ezviz_api_base_url.rstrip('/')}"
                "/api/v3/mall/device/package/code/active",
                headers={"accessToken": access_token},
                json=[
                    {
                        "packageDeviceId": package_code,
                        "deviceSerial": device_serial,
                        "channelNo": str(channel_no),
                    }
                ],
                timeout=self._settings.ezviz_request_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise EzvizApiError(
                "EZVIZ package activation timed out", retryable=True
            ) from exc
        except httpx.RequestError as exc:
            raise EzvizApiError(
                "EZVIZ package activation is unreachable", retryable=True
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise EzvizApiError(
                "EZVIZ package activation returned invalid JSON",
                http_status=response.status_code,
            ) from exc
        if not isinstance(payload, Mapping):
            raise EzvizApiError("EZVIZ package activation returned an unexpected response")

        meta = _require_mapping(payload.get("meta"), "package activation meta")
        meta_code = str(meta.get("code", ""))
        meta_message = _safe_platform_message(meta.get("message"))
        if meta_code == "10002":
            raise EzvizApiError(
                meta_message,
                platform_code=meta_code,
                http_status=response.status_code,
                token_invalid=True,
            )
        if response.status_code >= 400 or meta_code != "200":
            raise EzvizApiError(
                meta_message,
                platform_code=meta_code or None,
                http_status=response.status_code,
                retryable=response.status_code >= 500 or meta_code == "500",
            )

        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise EzvizApiError("EZVIZ package activation response omitted data")
        item = _require_mapping(data[0], "package activation item")
        try:
            active_code = int(item.get("activeCode"))
        except (TypeError, ValueError) as exc:
            raise EzvizApiError(
                "EZVIZ package activation response contained invalid activeCode"
            ) from exc
        active_message = item.get("activeMessage")
        message = (
            active_message.strip()[:200]
            if isinstance(active_message, str) and active_message.strip()
            else ("操作成功" if active_code == 0 else "萤石未提供激活结果说明")
        )
        return EzvizPackageActivationResult(
            meta_code=meta_code,
            active_code=active_code,
            message=message,
        )

    async def _post_form(self, path: str, data: dict[str, object]) -> dict[str, Any]:
        try:
            response = await self._http_client.post(
                f"{self._settings.ezviz_api_base_url.rstrip('/')}{path}",
                data=data,
                timeout=self._settings.ezviz_request_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise EzvizApiError(
                "EZVIZ request timed out", retryable=True
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise EzvizApiError(
                "EZVIZ returned an HTTP error",
                http_status=exc.response.status_code,
                retryable=exc.response.status_code >= 500,
            ) from exc
        except httpx.RequestError as exc:
            raise EzvizApiError("EZVIZ is unreachable", retryable=True) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise EzvizApiError("EZVIZ returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise EzvizApiError("EZVIZ returned an unexpected response")

        code = str(payload.get("code", ""))
        if code != "200":
            raise EzvizApiError(
                _safe_platform_message(payload.get("msg")),
                platform_code=code or None,
                retryable=code in RETRYABLE_CODES,
                token_invalid=code in TOKEN_INVALID_CODES,
            )
        return payload


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EzvizApiError(f"EZVIZ response contained invalid {label}")
    return dict(value)


def _safe_platform_message(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "EZVIZ rejected the request"
    return value.strip()[:200]
