from fastapi import Request

from app.modules.device_packages.service import DevicePackageService


def get_device_package_service(request: Request) -> DevicePackageService:
    return request.app.state.device_package_service
