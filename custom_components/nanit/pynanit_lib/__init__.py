import aiohttp

API_ROOT = "https://api.nanit.com"


class NanitAPIError(Exception):
    pass


class NanitUnauthorizedError(NanitAPIError):
    pass


class NanitClient:
    _session: aiohttp.ClientSession
    _access_token: str
    _refresh_token: str

    def __init__(
        self, session: aiohttp.ClientSession, access_token: str = None, refresh_token: str = None
    ):
        self._session = session
        if access_token:
            self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token

    async def initiate_login(self, email: str, password: str) -> str:
        async with self._session.post(
            f"{API_ROOT}/login",
            json={
                "email": email,
                "password": password,
                "channel": "email",
            },
            headers={
                "nanit-api-version": "1",
            },
        ) as resp:
            login_data = await resp.json()
            if resp.status not in (482, 200):
                raise NanitAPIError(f"Bad status code from nanit API: {resp.status} {login_data}")
            mfa_token = login_data["mfa_token"]
            return mfa_token

    async def complete_login(
        self, email: str, password: str, mfa_token: str, mfa_code: str
    ) -> tuple[str, str]:
        async with self._session.post(
            f"{API_ROOT}/login",
            json={
                "email": email,
                "password": password,
                "mfa_code": mfa_code,
                "mfa_token": mfa_token,
                "channel": "email",
            },
            headers={
                "nanit-api-version": "1",
            },
        ) as resp:
            login_data = await resp.json()
            if resp.status == 401:
                raise NanitUnauthorizedError()
            if resp.status not in (200, 201):
                raise NanitAPIError(f"Bad status code from nanit API: {resp.status}")

            self._access_token = login_data["access_token"]
            self._refresh_token = login_data["refresh_token"]
            return self._access_token, self._refresh_token

    async def refresh_session(self) -> tuple[str, str]:
        async with self._session.post(
            f"{API_ROOT}/tokens/refresh",
            json={
                "refresh_token": self._refresh_token,
            },
        ) as resp:
            login_data = await resp.json()
            if resp.status != 200:
                raise NanitAPIError(f"Bad status code from nanit API: {resp.status}: {login_data}")
            self._access_token = login_data["access_token"]
            self._refresh_token = login_data["refresh_token"]
            return self._access_token, self._refresh_token

    def get_stream_url(self, baby_uid: str) -> str:
        return f"rtmps://media-secured.nanit.com/nanit/{baby_uid}.{self._access_token}"

    def get_websocket_url(self, camera_uid: str) -> str:
        return f"wss://api.nanit.com/focus/cameras/{camera_uid}/user_connect"

    async def _get_authorized(self, path: str, **kwargs) -> dict:
        async with self._session.get(
            f"{API_ROOT}{path}",
            headers={
                "Authorization": self._access_token,
            },
            **kwargs,
        ) as resp:
            if resp.status >= 400:
                raise NanitAPIError(f"Bad status code from nanit API: {resp.status}")
            data = await resp.json()
            return data

    async def get_babies(self) -> dict:
        return await self._get_authorized("/babies")

    async def get_messages(self, baby_uid: str, limit: int = 10) -> dict:
        return await self._get_authorized(
            f"/babies/{baby_uid}/messages",
            params={
                "limit": limit,
            },
        )

    async def get_events(self, baby_uid: str, limit: int = 10) -> dict:
        return await self._get_authorized(
            f"/babies/{baby_uid}/events",
            params={
                "limit": limit,
            },
        )

    async def get_latest_event(self, baby_uid) -> dict:
        return await self._get_authorized(
            f"/babies/{baby_uid}/events/last",
        )
