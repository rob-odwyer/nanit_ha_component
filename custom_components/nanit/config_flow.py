"""Config flow for Nanit integration."""

from __future__ import annotations

import logging
from typing import Any

import pynanit
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, ACCESS_TOKEN, REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

STEP_LOGIN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_MFA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CODE): str,
    }
)


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nanit."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_LOGIN_DATA_SCHEMA, errors=errors
            )

        email = user_input[CONF_EMAIL]
        password = user_input[CONF_PASSWORD]

        mfa_token, errors = self._start_login(email, password)
        if mfa_token is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_LOGIN_DATA_SCHEMA, errors=errors
            )

        self.data = {
            CONF_EMAIL: email,
            CONF_PASSWORD: password,
            CONF_TOKEN: mfa_token,
        }

        return self.async_show_form(step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA)

    async def async_step_mfa(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the MFA code step."""
        errors: dict[str, str] = {}
        if user_input is None:
            # TODO: Show an explanation here
            return self.async_show_form(
                step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA, errors=errors
            )

        access_token, refresh_token, errors = await self._complete_login(
            email=self.data[CONF_EMAIL],
            password=self.data[CONF_PASSWORD],
            mfa_token=self.data[CONF_TOKEN],
            mfa_code=user_input[CONF_CODE],
        )

        if access_token is None:
            return self.async_show_form(
                step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA, errors=errors
            )

        return self.async_create_entry(
            title=self.data[CONF_EMAIL],
            data={
                CONF_EMAIL: self.data[CONF_EMAIL],
                ACCESS_TOKEN: access_token,
                REFRESH_TOKEN: refresh_token,
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_DATA_SCHEMA,
            )

        reauth_entry = self._get_reauth_entry()
        email = reauth_entry.data[CONF_EMAIL]
        password = user_input[CONF_PASSWORD]

        mfa_token, errors = self._start_login(email, password)
        if mfa_token is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_DATA_SCHEMA,
                errors=errors,
            )

        self.data = {
            CONF_EMAIL: user_input[CONF_EMAIL],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_TOKEN: mfa_token,
        }
        return self.async_show_form(step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA)

    async def async_step_reauth_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the MFA code step."""
        errors: dict[str, str] = {}
        if user_input is None:
            # TODO: Show an explanation here
            return self.async_show_form(
                step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA, errors=errors
            )

        access_token, refresh_token, errors = await self._complete_login(
            email=self.data[CONF_EMAIL],
            password=self.data[CONF_PASSWORD],
            mfa_token=self.data[CONF_TOKEN],
            mfa_code=user_input[CONF_CODE],
        )

        if access_token is None:
            return self.async_show_form(
                step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA, errors=errors
            )

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates={
                CONF_EMAIL: self.data[CONF_EMAIL],
                ACCESS_TOKEN: access_token,
                REFRESH_TOKEN: refresh_token,
            },
        )

    async def _start_login(self, email: str, password: str) -> tuple[str | None, dict[str, str]]:
        errors: dict[str, str] = {}
        try:
            client = pynanit.NanitClient(async_get_clientsession(self.hass))
            mfa_token = await client.initiate_login(email=email, password=password)
            return mfa_token, errors
        except pynanit.NanitAPIError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception while logging in")
            errors["base"] = "unknown"
        return None, errors

    async def _complete_login(
        self, email: str, password: str, mfa_token, mfa_code
    ) -> tuple[str | None, str | None, dict[str, str]]:
        errors: dict[str, str] = {}
        try:
            client = pynanit.NanitClient(async_get_clientsession(self.hass))

            # TODO: retrieve user.id here and call async_set_unique_id
            access_token, refresh_token = await client.complete_login(
                email=email,
                password=password,
                mfa_token=mfa_token,
                mfa_code=mfa_code,
            )
            return access_token, refresh_token, errors
        except pynanit.NanitAPIError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception while logging in")
            errors["base"] = "unknown"
        return None, None, errors
