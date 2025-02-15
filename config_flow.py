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
        if user_input is not None:
            try:
                client = pynanit.NanitClient(async_get_clientsession(self.hass))
                mfa_token = await client.initiate_login(
                    email=user_input[CONF_EMAIL], password=user_input[CONF_PASSWORD]
                )
            except pynanit.NanitAPIError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.data = {
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_TOKEN: mfa_token,
                }
                return self.async_show_form(step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA)

        return self.async_show_form(
            step_id="user", data_schema=STEP_LOGIN_DATA_SCHEMA, errors=errors
        )

    async def async_step_mfa(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the MFA code step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = pynanit.NanitClient(async_get_clientsession(self.hass))

                access_token, refresh_token = await client.complete_login(
                    email=self.data[CONF_EMAIL],
                    password=self.data[CONF_PASSWORD],
                    mfa_token=self.data[CONF_TOKEN],
                    mfa_code=user_input[CONF_CODE],
                )
            except pynanit.NanitAPIError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=self.data[CONF_EMAIL],
                    data={
                        ACCESS_TOKEN: access_token,
                        REFRESH_TOKEN: refresh_token,
                    },
                )

        return self.async_show_form(
            step_id="mfa", data_schema=STEP_LOGIN_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle authentication failure on setup."""
        # FIXME: This isn't the correct way to handle reauthentication.
        # error: Detected reauth config flow creating a new entry, when it is expected to update an existing entry and abort. This will stop working in 2025.11, please report it to the author of the 'nanit' custom integration
        return self.async_show_form(step_id="user", data_schema=STEP_LOGIN_DATA_SCHEMA)
