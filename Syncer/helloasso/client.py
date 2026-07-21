"""
Asynchronous HelloAsso API client.

Owns the shared HTTP session and the concurrency limiter, and exposes the
endpoints used by the syncer. Throttling and retries are centralized in a
single request wrapper.
"""

import asyncio
import random
from typing import Any, Dict, List, Optional

import aiohttp

from ..models.helloasso.ClientConfig import ClientConfig
from ..models.app.Secrets import Secrets

class HttpError(Exception):
    """Non-recoverable HTTP error after all retries have been exhausted."""

class HelloAssoClient:
    """Owns the shared HTTP session, concurrency limiter and API endpoints."""

    config: ClientConfig

    def __init__(self, session: aiohttp.ClientSession, config: ClientConfig):
        self.session = session
        self.config = config

        # A single semaphore bounds the global concurrency (across all forms).
        self.semaphore = asyncio.Semaphore(1 if config.http_client.concurrency == 1 else max(1, config.http_client.concurrency))
        self._token: Optional[str] = None

    async def _request_json(self,
                            method: str,
                            url: str,
                            *,
                            expected_status: int = 200,
                            **kwargs: Any) -> Dict[str, Any]:
        """Perform an HTTP request returning JSON, with throttling and retries.

        - Acquires the semaphore to bound the number of concurrent requests.
        - Applies a delay (with a small jitter) to space out calls and reduce
          the risk of being flagged by the API.
        - Retries with exponential backoff and honors the ``Retry-After`` header
          returned on a ``429`` (Too Many Requests) status.
        """

        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self.config.http_client.user_agent)
        if self._token:
            headers.setdefault("Authorization", f"Bearer {self._token}")

        last_error: Optional[Exception] = None

        for attempt in range(self.config.http_client.max_retries):
            async with self.semaphore:
                # Throttle: space out calls (jitter to avoid a regular pattern)
                if self.config.http_client.request_delay > 0:
                    jitter = random.uniform(0, self.config.http_client.request_delay * 0.25)
                    await asyncio.sleep(self.config.http_client.request_delay + jitter)

                try:
                    async with self.session.request(method, url, headers=headers, **kwargs) as response:
                        # Explicit rate limiting: honor Retry-After
                        if response.status == 429:
                            retry_after = float(response.headers.get("Retry-After", self.config.http_client.retry_delay))
                            last_error = HttpError(f"429 Too Many Requests sur {url}")
                            if attempt < self.config.http_client.max_retries - 1:
                                await asyncio.sleep(retry_after)
                                continue
                            raise last_error

                        response.raise_for_status()

                        if response.status != expected_status:
                            raise HttpError(
                                f"Statut inattendu {response.status} (attendu {expected_status}) sur {url}")

                        return await response.json()

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_error = e
                    if attempt == self.config.http_client.max_retries - 1:
                        raise
                    await asyncio.sleep(self.config.http_client.retry_delay * (attempt + 1))

        raise HttpError(f"Échec de la requête {method} {url}: {last_error}")

    async def authenticate(self) -> None:
        """Retrieve an OAuth2 access token (initial sequential step)"""

        payload = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "client_credentials"
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        data = await self._request_json("POST", self.config.hello_asso.oauth_url, data=payload, headers=headers)
        token = data.get("access_token")

        if not token:
            raise ValueError(f"Pas de token d'accès dans la réponse: {data}")

        self._token = token

    async def get_all_payments(self,
                               form_slug: str,
                               form_type: str = "Membership",
                               page_size: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve all payments for a given form (with pagination)

        Pagination stays sequential because the number of pages is only known
        once a partial/empty page is received. Each page request still goes
        through the concurrency limiter (_request_json).
        """
        url = f"{self.config.hello_asso.base_url}/organizations/{self.config.hello_asso.organization}/forms/{form_type}/{form_slug}/payments"

        headers = {"Content-Type": "application/json"}

        all_payments = []
        page = 1

        while True:
            params = {
                "page": page,
                "limit": page_size
            }

            try:
                data = await self._request_json("GET", url, headers=headers, params=params)
            except (aiohttp.ClientError, HttpError, asyncio.TimeoutError) as e:
                print(f"Erreur lors de la récupération des paiements (page {page}): {e}")
                break

            payments = data.get("data", [])

            if not payments:
                break

            all_payments.extend(payments)

            # Last page reached (partial page)
            if len(payments) < page_size:
                break

            page += 1

        return all_payments

    async def get_order_details(self, order_id: int) -> Dict[str, Any]:
        """Retrieve the details of a specific order"""
        url = f"{self.config.hello_asso.base_url}/orders/{order_id}"

        try:
            return await self._request_json("GET", url)
        except (aiohttp.ClientError, HttpError, asyncio.TimeoutError) as e:
            print(f"Erreur lors de la récupération des détails de la commande {order_id}: {e}")
            return {}
