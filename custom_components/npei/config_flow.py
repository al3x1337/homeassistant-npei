"""Config flow for Niagara Peninsula Energy Inc. (NPEI) integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NPEIAuthError, NPEIClient
from .const import CONF_ACCOUNT_ID, CONF_PASSWORD, CONF_SERVICE_ID, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user credentials against NPEI IAM API."""
    session = async_get_clientsession(hass)
    client = NPEIClient(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=session,
    )

    try:
        await client.authenticate()
        discovery = await client.discover_account()
    except NPEIAuthError as err:
        raise InvalidAuth from err
    except Exception as err:
        raise CannotConnect from err

    account_id = discovery.get("accountId") or "Unknown"
    service_id = discovery.get("serviceId") or "Unknown"

    return {
        "title": f"NPEI Account ({account_id})",
        CONF_ACCOUNT_ID: account_id,
        CONF_SERVICE_ID: service_id,
    }


class NPEIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NPEI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during NPEI configuration")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info[CONF_ACCOUNT_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ACCOUNT_ID: info[CONF_ACCOUNT_ID],
                        CONF_SERVICE_ID: info[CONF_SERVICE_ID],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
