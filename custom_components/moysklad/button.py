from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Add buttons for updating products and stocks."""
    async_add_entities(
        [
            UpdateProductsButton(hass, config_entry),
            UpdateStocksButton(hass, config_entry),
        ]
    )


class UpdateProductsButton(ButtonEntity):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self.api = hass.data[DOMAIN][config_entry.entry_id]

    @property
    def name(self):
        return "Update Products"

    @property
    def unique_id(self):
        return f"{self.config_entry.entry_id}_update_products"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name="Moy Sklad",
            manufacturer="Moy Sklad",
            model="API",
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.api.update_all_entities(self.hass)
        _LOGGER.info("Full products update triggered")


class UpdateStocksButton(ButtonEntity):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self.api = hass.data[DOMAIN][config_entry.entry_id]

    @property
    def name(self):
        return "Update Stocks"

    @property
    def unique_id(self):
        return f"{self.config_entry.entry_id}_update_stocks"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name="Moy Sklad",
            manufacturer="Moy Sklad",
            model="API",
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.api.update_stocks(self.hass)
        _LOGGER.info("Stocks update triggered")
