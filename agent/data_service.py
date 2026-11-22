"""Access to the mock data service under DATA_BASE_URL, shared by all tools.

Every request is an HTTP GET. HTTP 404 means "no data", which is a result and not an error; any
other problem comes back as a result with "error". The tools never raise because of the service.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_SECONDS = 15


def normalize_city(value: str) -> str:
    """Lowercase without umlauts, the convention of the city codes: "München" -> "muenchen"."""
    text = value.strip().lower()
    for umlaut, spelled_out in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, spelled_out)
    return text


class DataService:
    """The data service plus what it says about itself: cities, routes and the user's home."""

    def __init__(
        self,
        base_url: str,
        cities: dict[str, str] | None = None,
        routes: list[tuple[str, str]] | None = None,
        home: str | None = None,
    ):
        self.base_url = base_url
        self.cities = cities or {}  # city code -> name, e.g. "muenchen" -> "München"
        self.routes = routes or []  # (from code, to code)
        self.home = self.city_code(home) if home else None  # city code of the user's home

    @classmethod
    def connect(cls, base_url: str) -> "DataService":
        """Read index.json and context.json once. If they are missing, the tools still work."""
        index = _read_json(f"{base_url}/index.json")
        context = _read_json(f"{base_url}/context.json")
        cities = index.get("cities") if isinstance(index.get("cities"), dict) else {}
        routes = index.get("routes") if isinstance(index.get("routes"), list) else []
        home = context.get("home")
        return cls(
            base_url,
            cities={str(code): str(name) for code, name in cities.items()},
            routes=[(str(r[0]), str(r[1])) for r in routes if isinstance(r, list) and len(r) == 2],
            home=home if isinstance(home, str) else None,
        )

    def get(self, *segments: str, about: dict, no_data: str) -> dict:
        """GET {base_url}/{segments joined by /}.json, e.g. get("weather", "ulm", "2026-10-29", ...).

        about names what was asked for and is repeated in a "no data" or error result, so the model
        knows which day, place or route the gap belongs to.
        """
        url = f"{self.base_url}/" + "/".join(urllib.parse.quote(s, safe="") for s in segments) + ".json"
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
                return json.load(response)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return {**about, "data_available": False, "message": no_data}
            return {**about, "error": f"data service returned HTTP {err.code}"}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            return {**about, "error": f"data service unreachable: {err}"}

    def city_code(self, value: str) -> str | None:
        """The city code for a code or city name, or None if the service has no data for it.

        If the service did not say which cities it knows, the normalized value is used as is.
        """
        key = normalize_city(value)
        if not self.cities:
            return key or None
        for code, name in self.cities.items():
            if key in (normalize_city(code), normalize_city(name)):
                return code
        return None

    def unknown_city(self, value: str, **about) -> dict:
        """The result for a place the service has no data for: a gap, not an error."""
        return {
            **about,
            "city": value,
            "data_available": False,
            "message": f"There is no data for {value!r}. {self.describe_cities()}",
        }

    def describe_cities(self) -> str:
        if not self.cities:
            return 'Pass cities as lowercase codes without umlauts, e.g. "muenchen" for München.'
        known = ", ".join(f"{code} ({name})" for code, name in self.cities.items())
        return f"Pass the city code. There is data only for these cities: {known}."

    def describe_routes(self) -> str:
        if not self.routes:
            return ""
        known = ", ".join(f"{origin} -> {destination}" for origin, destination in self.routes)
        return f"There are connections only on these routes: {known}."

    def describe_home(self) -> str:
        if not self.home:
            return ""
        name = self.cities.get(self.home, self.home)
        return (
            f"The user's home is {name} (city code {self.home}); trips start there unless the "
            "question says otherwise."
        )


def _read_json(url: str) -> dict:
    """A JSON object from the service, or {} if it cannot be read."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            data = json.load(response)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
