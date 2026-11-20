"""NPEI (Niagara Peninsula Energy Inc.) Asynchronous API Client."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
import urllib.parse

import aiohttp

from .const import IAM_BASE_URL, MYACCOUNT_BASE_URL, USAGE_BASE_URL, WEATHER_BASE_URL

_LOGGER = logging.getLogger(__name__)


class NPEIAuthError(Exception):
    """Raised when authentication fails or credentials are invalid."""


class NPEIAPIError(Exception):
    """Raised when an API endpoint returns an error."""


class NPEIClient:
    """Async API client for NPEI customer portal."""

    def __init__(
        self,
        username: str,
        password: str,
        account_id: Optional[str] = None,
        service_id: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        self.username = username
        self.password = password
        self.account_id = account_id
        self.service_id = service_id
        self._session = session
        self._owns_session = session is None
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._customer_id: Optional[str] = None
        self._user_info: Dict[str, Any] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying aiohttp session if owned."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def authenticate(self, force: bool = False) -> str:
        """Authenticate against NPEI IAM API and return the Bearer token."""
        if (
            not force
            and self._token
            and self._token_expiry
            and datetime.now() < self._token_expiry - timedelta(minutes=5)
        ):
            return self._token

        session = await self._get_session()
        login_url = f"{IAM_BASE_URL}/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "client_id": "iam",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://myaccount.npei.ca",
            "Referer": "https://myaccount.npei.ca/page/login",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        }

        try:
            async with session.post(
                login_url, data=urllib.parse.urlencode(payload), headers=headers
            ) as resp:
                if resp.status in (400, 401, 403):
                    text = await resp.text()
                    raise NPEIAuthError(f"Login failed ({resp.status}): {text}")
                if resp.status != 200:
                    text = await resp.text()
                    raise NPEIAPIError(f"Unexpected status from IAM ({resp.status}): {text}")

                data = await resp.json()
                self._token = data.get("token")
                expires_in = data.get("expires_in", 3600)
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in)
                self._user_info = data.get("user", {})

                if not self._token:
                    raise NPEIAuthError("Login succeeded but no token was returned")

                _LOGGER.debug("Authenticated successfully. Token valid for %s seconds", expires_in)
                return self._token

        except aiohttp.ClientError as err:
            raise NPEIAPIError(f"Network error during authentication: {err}") from err

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        require_auth: bool = True,
    ) -> Any:
        """Execute an authenticated request with automatic retry on 401."""
        session = await self._get_session()
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://myaccount.npei.ca",
            "Referer": "https://myaccount.npei.ca/myaccount/myaccount",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        }

        if require_auth:
            token = await self.authenticate()
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with session.request(
                method, url, params=params, json=json_data, headers=headers
            ) as resp:
                if resp.status == 204:
                    return None
                if resp.status == 401 and require_auth:
                    _LOGGER.info("Token expired, re-authenticating and retrying...")
                    token = await self.authenticate(force=True)
                    headers["Authorization"] = f"Bearer {token}"
                    async with session.request(
                        method, url, params=params, json=json_data, headers=headers
                    ) as retry_resp:
                        if retry_resp.status == 204:
                            return None
                        if retry_resp.status != 200:
                            text = await retry_resp.text()
                            raise NPEIAPIError(f"Request failed ({retry_resp.status}): {text}")
                        return await retry_resp.json()

                if resp.status != 200:
                    text = await resp.text()
                    raise NPEIAPIError(f"Request failed ({resp.status}): {text}")

                return await resp.json()

        except aiohttp.ClientError as err:
            raise NPEIAPIError(f"Network error communicating with NPEI: {err}") from err

    async def discover_account(self) -> Dict[str, Any]:
        """Discover accountId, serviceId, and customer metadata."""
        await self.authenticate()
        whoami = await self._request("GET", f"{IAM_BASE_URL}/management/whoami")
        customer_id = (
            whoami.get("customerId")
            or self._user_info.get("customerId")
            or whoami.get("id")
        )
        self._customer_id = customer_id

        accounts_data = await self._request(
            "GET",
            f"{MYACCOUNT_BASE_URL}/api/v1/customers/{customer_id}/accounts",
            params={"searchParam": ""},
        )

        account = None
        service = None

        if isinstance(accounts_data, list) and accounts_data:
            account = accounts_data[0]
            self.account_id = account.get("accountId") or account.get("id")
            services = account.get("services", [])
            if services:
                service = services[0]
                self.service_id = service.get("serviceId") or service.get("id")
        elif isinstance(accounts_data, dict):
            account = accounts_data
            self.account_id = account.get("accountId")
            services = account.get("services", [])
            if services:
                service = services[0]
                self.service_id = service.get("serviceId")

        return {
            "customerId": customer_id,
            "accountId": self.account_id,
            "serviceId": self.service_id,
            "account": account,
            "service": service,
        }

    async def get_usage(
        self,
        start_date: str,
        end_date: str,
        view: str = "DAILY",
        best_effort: str = "N",
        tz: str = "America/New_York",
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch interval or aggregated usage from the NPEI usageapi."""
        if not self.account_id or not self.service_id:
            await self.discover_account()

        url = f"{USAGE_BASE_URL}/energy/account/{self.account_id}/service/{self.service_id}/usage"
        params = {
            "start-date": start_date,
            "end-date": end_date,
            "usage-view": view.upper(),
            "meter": "All",
            "bestEffort": "Y" if view.upper() == "HOURLY" else best_effort,
            "tz": tz,
        }
        return await self._request("GET", url, params=params)

    async def get_weather(
        self,
        from_date: str,
        to_date: str,
        time_type: str = "daily",
        location: str = "NiagaraFallsOntario",
    ) -> Optional[Dict[str, Any]]:
        """Fetch weather & temperature observations from London Hydro Shared Services."""
        url = f"{WEATHER_BASE_URL}/weathersearch"
        params = {
            "location": location,
            "fromDate": from_date,
            "toDate": to_date,
            "timeType": time_type.lower(),
            "dataType": "all",
            "tempType": "C",
            "timezone": "",
        }
        return await self._request("GET", url, params=params, require_auth=False)

    async def get_billing_chart_data(
        self,
        start_ms: int,
        end_ms: int,
    ) -> Optional[Dict[str, Any]]:
        """Fetch billing history chart data."""
        if not self.account_id or not self.service_id:
            await self.discover_account()

        url = f"{MYACCOUNT_BASE_URL}/api/v1/services/{self.service_id}/billingChartData"
        params = {
            "accountId": self.account_id,
            "view": "billing",
            "startDate": start_ms,
            "endDate": end_ms,
        }
        return await self._request("GET", url, params=params)

    @staticmethod
    def get_season_info(target_date: Optional[date] = None) -> Dict[str, Any]:
        """Calculate Ontario Regulated Price Plan season transitions."""
        target = target_date or date.today()
        year = target.year

        may_1 = date(year, 5, 1)
        nov_1 = date(year, 11, 1)

        if target < may_1:
            current_season = "winter"
            next_season = "summer"
            next_date = may_1
        elif target < nov_1:
            current_season = "summer"
            next_season = "winter"
            next_date = nov_1
        else:
            current_season = "winter"
            next_season = "summer"
            next_date = date(year + 1, 5, 1)

        days_left = (next_date - target).days

        return {
            "current_season": current_season,
            "next_season": next_season,
            "next_season_start_date": next_date.isoformat(),
            "days_until_next_season": days_left,
        }
