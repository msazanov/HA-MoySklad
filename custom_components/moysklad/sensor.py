from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as get_device_registry
import logging
from .const import DOMAIN, PATHNAME_KEY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    api = hass.data[DOMAIN][entry.entry_id]
    products = await api.get_products()

    products_by_category = {}
    for product in products:
        category = product.get(PATHNAME_KEY, "No Category")
        if not category:
            category = "No Category"
        if category not in products_by_category:
            products_by_category[category] = []
        products_by_category[category].append(product)

    device_registry = get_device_registry(hass)
    entities = []
    for category, items in products_by_category.items():
        device_name = category
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device_name)},
            name=device_name,
            manufacturer="Moy Sklad",
            model="Product",
        )
        for item in items:
            entities.append(MoySkladSensor(api, item, device))

    async_add_entities(entities, True)
    hass.data[DOMAIN]["entities"] = entities  # Store entities for stock updates


class MoySkladSensor(Entity):
    def __init__(self, api, item, device):
        self.api = api
        self.item = item
        self._device = device
        self._attr_name = item["name"]
        self._attr_unique_id = item["id"]
        self._attr_unit_of_measurement = "THB"
        self._state = item.get("salePrices", [{}])[0].get("value", 0) / 100
        self._quantity = item.get("quantity")

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def state(self):
        return self._state

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device.name)},
            "name": self._device.name,
            "manufacturer": "Moy Sklad",
            "model": "Product",
        }

    @property
    def extra_state_attributes(self):
        return {
            "id": self.item.get("id"),
            "accountId": self.item.get("accountId"),
            "shared": self.item.get("shared"),
            "updated": self.item.get("updated"),
            "name": self.item.get("name"),
            "description": self.item.get("description"),
            "code": self.item.get("code"),
            "externalCode": self.item.get("externalCode"),
            "archived": self.item.get("archived"),
            "pathName": self.item.get("pathName"),
            "minPrice": self.format_price(
                self.item.get("minPrice", {}).get("value", 0)
            ),
            "salePrices": [
                self.format_price(price.get("value", 0))
                for price in self.item.get("salePrices", [])
            ],
            "buyPrice": self.format_price(
                self.item.get("buyPrice", {}).get("value", 0)
            ),
            "discountProhibited": self.item.get("discountProhibited"),
            "weighed": self.item.get("weighed"),
            "weight": self.item.get("weight"),
            "volume": self.item.get("volume"),
            "stock": self._quantity,  # Use quantity as stock
            "article": self.item.get("article"),
            "inTransit": self.item.get("inTransit"),
            "reserve": self.item.get("reserve"),
        }

    @staticmethod
    def format_price(price):
        return f"{price / 100:.2f}"

    async def async_update_stock(self, stock_value):
        _LOGGER.info(
            f"Updating stock for entity {self._attr_unique_id} with new stock value: {stock_value}"
        )
        self._quantity = stock_value
        self.async_write_ha_state()

    async def async_update_item(self, item, stock_value):
        _LOGGER.info(
            f"Updating item for entity {self._attr_unique_id} with new item data: {item}"
        )
        self.item = item
        self._attr_name = item["name"]
        self._state = item.get("salePrices", [{}])[0].get("value", 0) / 100
        self._quantity = stock_value
        self.async_write_ha_state()
