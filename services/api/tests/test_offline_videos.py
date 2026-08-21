from pathlib import Path

import pytest
from httpx import AsyncClient

from app.modules.offline_videos import service as offline_video_service_module
from tests.conftest import TEST_PASSWORD


async def login_headers(client: AsyncClient, username: str = "admin") -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_video(root: Path, relative_path: str, content: bytes = b"fake-video") -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.mark.asyncio
async def test_scan_lists_supported_files_and_infers_labels(
    client: AsyncClient, app
) -> None:
    root = app.state.settings.offline_video_root
    create_video(root, "GMDCSA-24/Fall/fall-01.mp4", b"fall-video")
    create_video(root, "GMDCSA-24/ADL/sleeping.webm", b"adl-video")
    create_video(root, "CAUCAFall/Subject-1/notes.txt", b"ignored")
    headers = await login_headers(client)

    scan = await client.post("/api/v1/offline-videos/scan", headers=headers)
    videos = await client.get("/api/v1/offline-videos", headers=headers)
    library = await client.get("/api/v1/offline-videos/library", headers=headers)

    assert scan.status_code == 200
    assert scan.json()["created"] == 2
    assert scan.json()["total"] == 2
    assert videos.status_code == 200
    assert {item["label"] for item in videos.json()} == {"fall", "adl"}
    assert {item["dataset_name"] for item in videos.json()} == {"GMDCSA-24"}
    assert str(root.resolve()) not in videos.text
    assert library.json()["available_count"] == 2
    assert library.json()["labeled_count"] == 2
    assert library.json()["inference_enabled"] is False


@pytest.mark.asyncio
async def test_offline_video_routes_require_admin(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/offline-videos")).status_code == 401
    caregiver = await login_headers(client, "caregiver")

    assert (
        await client.post("/api/v1/offline-videos/scan", headers=caregiver)
    ).status_code == 403
    assert (
        await client.get("/api/v1/offline-videos/library", headers=caregiver)
    ).status_code == 403


@pytest.mark.asyncio
async def test_metadata_can_be_corrected_without_changing_the_file(
    client: AsyncClient, app
) -> None:
    root = app.state.settings.offline_video_root
    source = create_video(root, "incoming/clip-01.mp4")
    headers = await login_headers(client)
    await client.post("/api/v1/offline-videos/scan", headers=headers)
    video = (await client.get("/api/v1/offline-videos", headers=headers)).json()[0]

    response = await client.patch(
        f"/api/v1/offline-videos/{video['id']}",
        headers=headers,
        json={
            "display_name": "客厅模拟跌倒 01",
            "dataset_name": "GMDCSA-24",
            "origin": "public_dataset",
            "label": "fall",
            "source_url": "https://example.test/dataset",
            "license_note": "仅用于研究验证",
        },
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "客厅模拟跌倒 01"
    assert response.json()["origin"] == "public_dataset"
    assert source.read_bytes() == b"fake-video"

    invalid = await client.patch(
        f"/api/v1/offline-videos/{video['id']}",
        headers=headers,
        json={"display_name": None},
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_signed_playback_ticket_streams_the_selected_video(
    client: AsyncClient, app
) -> None:
    root = app.state.settings.offline_video_root
    content = b"0123456789-video-content"
    create_video(root, "sample/fall-01.mp4", content)
    headers = await login_headers(client)
    await client.post("/api/v1/offline-videos/scan", headers=headers)
    video = (await client.get("/api/v1/offline-videos", headers=headers)).json()[0]

    ticket_response = await client.post(
        f"/api/v1/offline-videos/{video['id']}/playback-ticket", headers=headers
    )
    stream_response = await client.get(ticket_response.json()["url"])
    range_response = await client.get(
        ticket_response.json()["url"], headers={"Range": "bytes=2-5"}
    )

    assert ticket_response.status_code == 200
    assert stream_response.status_code == 200
    assert stream_response.content == content
    assert stream_response.headers["content-type"] == "video/mp4"
    assert "no-store" in stream_response.headers["cache-control"]
    assert range_response.status_code == 206
    assert range_response.content == content[2:6]
    assert range_response.headers["accept-ranges"] == "bytes"
    assert (
        await client.get(
            f"/api/v1/offline-videos/{video['id']}/stream?ticket=invalid"
        )
    ).status_code == 401


@pytest.mark.asyncio
async def test_rescan_marks_removed_files_unavailable(client: AsyncClient, app) -> None:
    root = app.state.settings.offline_video_root
    source = create_video(root, "sample/fall-01.mp4")
    headers = await login_headers(client)
    await client.post("/api/v1/offline-videos/scan", headers=headers)
    video = (await client.get("/api/v1/offline-videos", headers=headers)).json()[0]
    source.unlink()

    scan = await client.post("/api/v1/offline-videos/scan", headers=headers)
    videos = await client.get("/api/v1/offline-videos", headers=headers)
    playback = await client.post(
        f"/api/v1/offline-videos/{video['id']}/playback-ticket", headers=headers
    )

    assert scan.json()["missing"] == 1
    assert videos.json()[0]["is_available"] is False
    assert playback.status_code == 409
    assert playback.json()["detail"]["code"] == "video_unavailable"


@pytest.mark.asyncio
async def test_avi_is_transcoded_once_before_browser_playback(
    client: AsyncClient, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = app.state.settings.offline_video_root
    create_video(root, "Legacy/Fall/fall-01.avi", b"legacy-avi")
    headers = await login_headers(client)
    await client.post("/api/v1/offline-videos/scan", headers=headers)
    video = (await client.get("/api/v1/offline-videos", headers=headers)).json()[0]
    transcode_calls = 0

    def fake_transcode(source: Path, target: Path, timeout_seconds: int) -> None:
        nonlocal transcode_calls
        transcode_calls += 1
        assert source.suffix == ".avi"
        assert timeout_seconds == 300
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"browser-compatible-mp4")

    monkeypatch.setattr(offline_video_service_module, "transcode_video", fake_transcode)

    first_ticket = await client.post(
        f"/api/v1/offline-videos/{video['id']}/playback-ticket", headers=headers
    )
    second_ticket = await client.post(
        f"/api/v1/offline-videos/{video['id']}/playback-ticket", headers=headers
    )
    stream = await client.get(first_ticket.json()["url"])

    assert video["requires_transcoding"] is True
    assert first_ticket.status_code == 200
    assert first_ticket.json()["transcoded"] is True
    assert second_ticket.status_code == 200
    assert transcode_calls == 1
    assert stream.content == b"browser-compatible-mp4"
    assert stream.headers["content-type"] == "video/mp4"
