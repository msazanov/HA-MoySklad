import aiohttp
import async_timeout
import base64
import logging
import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as get_device_registry
from homeassistant.helpers.entity_registry import async_get as get_entity_registry

from .const import DOMAIN, PATHNAME_KEY
from .sensor import MoySkladSensor  # Импортируем MoySkladSensor

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

_LOGGER = logging.getLogger(__name__)


class MyAPI:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.token = None

    async def authenticate(self) -> bool:
        url = "https://api.moysklad.ru/api/remap/1.2/security/token"
        auth_str = f"{self.username}:{self.password}"
        auth_bytes = auth_str.encode("ascii")
        auth_b64_bytes = base64.b64encode(auth_bytes)
        auth_b64_str = auth_b64_bytes.decode("ascii")

        _LOGGER.info(f"Base64 encoded credentials: {auth_b64_str}")

        headers = {"Authorization": f"Basic {auth_b64_str}", "Accept-Encoding": "gzip"}

        _LOGGER.info(f"Request headers: {headers}")

        async with aiohttp.ClientSession(headers=headers) as session:
            with async_timeout.timeout(10):
                async with session.post(url) as response:
                    _LOGGER.info(f"Response status: {response.status}")
                    response_text = await response.text()
                    _LOGGER.info(f"Response text: {response_text}")
                    if response.status == 200 or "access_token" in response_text:
                        data = await response.json()
                        self.token = data.get("access_token")
                        _LOGGER.info(f"Received token: {self.token}")
                        return True
                    else:
                        _LOGGER.error(f"Authentication failed: {response.status}")
                        return False

    async def get_products(self) -> list:
        url = "https://api.moysklad.ru/api/remap/1.2/entity/assortment"
        headers = {"Authorization": f"Bearer {self.token}", "Accept-Encoding": "gzip"}

        async with aiohttp.ClientSession(headers=headers) as session:
            with async_timeout.timeout(10):
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("rows", [])
                    else:
                        _LOGGER.error(f"Failed to get products: {response.status}")
                        return []

    async def get_stocks(self) -> list:
        url = "https://api.moysklad.ru/api/remap/1.2/report/stock/all/current"
        headers = {"Authorization": f"Bearer {self.token}", "Accept-Encoding": "gzip"}

        async with aiohttp.ClientSession(headers=headers) as session:
            with async_timeout.timeout(10):
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict):
                            return data.get("rows", [])
                        return data
                    else:
                        _LOGGER.error(f"Failed to get stocks: {response.status}")
                        return []

    async def update_products(self):
        products = await self.get_products()
        _LOGGER.info(f"Products updated: {products}")

    async def update_stocks(self, hass: HomeAssistant):
        stocks = await self.get_stocks()
        _LOGGER.info(f"Stocks updated: {stocks}")

        # Обновление сущностей в Home Assistant
        entities = hass.data[DOMAIN].get("entities", [])
        for entity in entities:
            if isinstance(entity, MoySkladSensor):
                stock_value = next(
                    (
                        stock["stock"]
                        for stock in stocks
                        if stock["assortmentId"] == entity.item.get("id")
                    ),
                    None,
                )
                if stock_value is not None:
                    _LOGGER.info(
                        f"Updating entity {entity.unique_id} with new stock value: {stock_value}"
                    )
                    await entity.async_update_stock(stock_value)
                else:
                    _LOGGER.info(
                        f"No matching stock value found for entity {entity.unique_id}"
                    )

    async def update_all_entities(self, hass: HomeAssistant):
        products = await self.get_products()
        stocks = await self.get_stocks()

        # Обновление существующих сущностей
        existing_entities = {
            entity.unique_id: entity for entity in hass.data[DOMAIN].get("entities", [])
        }
        updated_entities = {}

        device_registry = get_device_registry(hass)
        entity_registry = get_entity_registry(hass)

        for product in products:
            unique_id = product["id"]
            category = product.get(PATHNAME_KEY, "No Category")
            stock_value = next(
                (
                    stock["stock"]
                    for stock in stocks
                    if stock["assortmentId"] == unique_id
                ),
                None,
            )

            if unique_id in existing_entities:
                entity = existing_entities[unique_id]
                await entity.async_update_item(product, stock_value)
                updated_entities[unique_id] = entity
            else:
                # Создание новой сущности
                device = device_registry.async_get_or_create(
                    config_entry_id=list(hass.data[DOMAIN].keys())[0],
                    identifiers={(DOMAIN, unique_id)},
                    name=category,
                    manufacturer="Moy Sklad",
                    model="Product",
                )
                entity = MoySkladSensor(self, product, device)
                entity._quantity = stock_value
                updated_entities[unique_id] = entity
                hass.data[DOMAIN]["entities"].append(entity)
                entity_registry.async_get_or_create(
                    domain=DOMAIN,
                    platform="sensor",
                    unique_id=entity.unique_id,
                    config_entry_id=list(hass.data[DOMAIN].keys())[0],
                )

        # Удаление сущностей, которых нет в обновлённых данных
        for unique_id, entity in existing_entities.items():
            if unique_id not in updated_entities:
                _LOGGER.info(
                    f"Removing entity {unique_id} as it is no longer present in the source data"
                )
                hass.data[DOMAIN]["entities"].remove(entity)
                entity_registry.async_remove(entity.entity_id)

        _LOGGER.info(f"Entities updated: {updated_entities.keys()}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    username = entry.data.get("username")
    password = entry.data.get("password")

    api = MyAPI(username, password)
    if not await api.authenticate():
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
    