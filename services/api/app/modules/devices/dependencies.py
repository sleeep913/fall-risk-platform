from fastapi import Request

from app.modules.devices.service import DeviceService


def get_device_service(request: Request) -> DeviceService:
    return request.app.state.device_service
