"""Small, dependency-free client for the PagerDuty REST API v2."""

import json
import logging
from collections.abc import Iterable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

API_URL = "https://api.pagerduty.com"
PAGE_SIZE = 100
ACK_BATCH_SIZE = 250


class PagerDutyError(RuntimeError):
    """A PagerDuty API request failed."""


class PagerDutyClient:
    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Iterable[tuple[str, str | int]] = (),
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = urlencode(list(params), doseq=True)
        url = f"{API_URL}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        data = json.dumps(body).encode() if body is not None else None
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.pagerduty+json;version=2",
                "Authorization": f"Token token={self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return json.load(response)
        except HTTPError as error:
            details = error.read().decode(errors="replace")
            raise PagerDutyError(
                f"PagerDuty returned HTTP {error.code}: {details}"
            ) from error
        except URLError as error:
            raise PagerDutyError(f"Could not reach PagerDuty: {error.reason}") from error


def get_client(api_key: str) -> PagerDutyClient:
    return PagerDutyClient(api_key)


def get_current_user(client: PagerDutyClient) -> dict[str, Any]:
    return client.request("GET", "users/me")["user"]


def get_triggered_incidents(
    client: PagerDutyClient, user_ids: Iterable[str] = (), urgencies: Iterable[str] = ()
) -> list[dict[str, Any]]:
    """Return every triggered incident currently assigned to the given users."""
    logger.debug("Listing incidents")
    incidents: list[dict[str, Any]] = []
    offset = 0

    while True:
        params: list[tuple[str, str | int]] = [
            ("statuses[]", "triggered"),
            ("sort_by", "incident_number:desc"),
            ("limit", PAGE_SIZE),
            ("offset", offset),
        ]
        params.extend(("user_ids[]", user_id) for user_id in user_ids)
        params.extend(("urgencies[]", urgency) for urgency in urgencies)
        page = client.request("GET", "incidents", params=params)
        page_incidents = page["incidents"]
        incidents.extend(page_incidents)

        if not page.get("more", False):
            return incidents
        offset += len(page_incidents)


def acknowledge_incidents(
    client: PagerDutyClient, incident_ids: Iterable[str] = ()
) -> list[dict[str, Any]]:
    incident_ids = list(incident_ids)
    logger.debug("Acknowledging incidents")
    if not incident_ids:
        logger.debug("No incidents to acknowledge")
        return []

    acknowledged: list[dict[str, Any]] = []
    for start in range(0, len(incident_ids), ACK_BATCH_SIZE):
        batch = incident_ids[start : start + ACK_BATCH_SIZE]
        response = client.request(
            "PUT",
            "incidents",
            body={
                "incidents": [
                    {
                        "id": incident_id,
                        "type": "incident_reference",
                        "status": "acknowledged",
                    }
                    for incident_id in batch
                ]
            },
        )
        acknowledged.extend(response["incidents"])
    return acknowledged
