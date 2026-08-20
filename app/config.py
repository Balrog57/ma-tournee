from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    port: int = 8080
    data_dir: str = "./data"
    auth_user: str = ""
    auth_password: str = ""

    geocoder_url: str = "http://nominatim:8080"
    router_url: str = "http://osrm:5000"
    geocoder_timeout: float = 30.0
    router_timeout: float = 30.0
    geocoder_user_agent: str = "MaTournee-LEvasion/1.0 (contact: local)"

    map_center_lat: float = 49.292
    map_center_lon: float = 6.534
    map_default_zoom: int = 12
    tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    tile_attribution: str = "© OpenStreetMap contributors"

    depot_name: str = "L'Evasion"
    depot_address: str = "24 rue de la République, 57320 Bouzonville"

    avg_speed_kmh: float = 30.0
    max_import_bytes: int = 1_048_576


@lru_cache
def get_settings() -> Settings:
    return Settings()
