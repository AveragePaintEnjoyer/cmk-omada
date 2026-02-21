#!/usr/bin/python3

import requests
from typing import Optional
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OmadaClient:
    def __init__(
        self,
        base_url: str,
        omadac_id: str,
        client_id: str,
        client_secret: str,
        verify_ssl: bool = False,
        msp: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.omadac_id = omadac_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.verify_ssl = verify_ssl
        self.msp = msp

        self.access_token: Optional[str] = None

        self.session = requests.Session()
        self.session.verify = verify_ssl

    # ---------------- AUTH ----------------

    def authenticate(self):
        response = self.session.post(
            f"{self.base_url}/openapi/authorize/token",
            params={"grant_type": "client_credentials"},
            json={
                "omadacId": self.omadac_id,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()

        self.access_token = data["result"]["accessToken"]

    # ---------------- REQUEST ----------------

    def _request(self, method: str, endpoint: str, **kwargs):
        if not self.access_token:
            self.authenticate()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer AccessToken={self.access_token}"

        response = self.session.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=headers,
            timeout=10,
            **kwargs,
        )

        data = response.json()

        if data.get("errorCode") != 0:
            raise RuntimeError(f"Omada API error: {data}")

        return data

    # ---------------- PATH ----------------

    def _api_path(self, path: str):
        if self.msp:
            return f"/openapi/v1/msp/{self.omadac_id}{path}"
        return f"/openapi/v1/{self.omadac_id}{path}"

    # ---------------- SITES ----------------

    def get_sites_page(self, page: int, page_size: int):
        return self._request(
            "GET",
            self._api_path("/sites"),
            params={"page": page, "pageSize": page_size},
        )

    def get_sites(self, page_size: int = 1000):
        page = 1
        sites = []

        while True:
            response = self.get_sites_page(page, page_size)
            result = response["result"]

            data = result["data"]
            sites.extend(data)

            total = result["totalRows"]

            if len(sites) >= total:
                break

            page += 1

        return sites

    def get_sites_info(self):
        result = []

        for s in self.get_sites():
            device_scope = (
                s["customerId"] if self.msp else self.omadac_id
            )

            result.append(
                {
                    "site_id": s["siteId"],
                    "device_scope": device_scope,
                    "name": s.get("siteName", s.get("name")),
                }
            )

        return result

    # ---------------- DEVICES ----------------

    def get_devices(
        self,
        device_scope: str,
        site_id: str,
        page: int,
        page_size: int = 1000,
    ):
        endpoint = (
            f"/openapi/v1/{device_scope}/sites/{site_id}/devices"
        )

        return self._request(
            "GET",
            endpoint,
            params={"page": page, "pageSize": page_size},
        )

    def get_all_devices_for_site(self, site):
        page = 1
        devices = []

        while True:
            response = self.get_devices(
                site["device_scope"],
                site["site_id"],
                page,
            )

            data = response["result"]["data"]
            devices.extend(data)

            if len(data) < 1000:
                break

            page += 1

        return devices

    def get_all_devices(self):
        all_devices = {}

        for site in self.get_sites_info():
            all_devices[site["site_id"]] = \
                self.get_all_devices_for_site(site)

        return all_devices

# ---------------- STATUS ----------------

OMADA_STATUS_MAP = {
    0: 2,
    1: 0,
    2: 1,
    3: 1,
    4: 2,
}

OMADA_STATUS_TEXT = {
    0: "Disconnected",
    1: "Connected",
    2: "Pending",
    3: "Heartbeat Missed",
    4: "Isolated",
}

def translate_status(omada_status: int):
    internal = OMADA_STATUS_MAP.get(omada_status, -1)
    text = OMADA_STATUS_TEXT.get(omada_status, "Unknown")
    return internal, text

# ---------------- CONFIG ----------------

client = OmadaClient(
    base_url="https://__:8043",
    omadac_id="__",
    client_id="__",
    client_secret="__",
    verify_ssl=False,
    msp=False,
)

# ---------------- RUN ----------------

devices = client.get_all_devices()

for site, devs in devices.items():
    for d in devs:
        code, text = translate_status(d["status"])
        print(
            f'{code} \'Omada {d["name"]}\' '
            f'- Hostname: {d["name"]}, '
            f'Status: {text}, '
            f'Model: {d["model"]}, '
            f'MAC: {d["mac"]}'
        )
