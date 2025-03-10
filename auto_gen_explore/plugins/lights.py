import logging

_logger = logging.getLogger(__name__)

class LightsPlugin:
    _lights = [
        {"id": 1, "name": "Table Lamp", "is_on": False},
        {"id": 2, "name": "Porch light", "is_on": False},
        {"id": 3, "name": "Chandelier", "is_on": True},
    ]

    def get_state(
        self,
    ) -> str:
        """Gets a list of lights and their current state."""
        _logger.debug(f"Getting lights: {self._lights}")
        return self._lights

    def change_state(
        self,
        id: int,
        is_on: bool,
    ) -> str:
        """Changes the state of the light."""
        _logger.debug(f"Change light state called: id={id}, is_on={is_on}")
        for light in self._lights:
            if light["id"] == id:
                if light["is_on"] == is_on:
                    _logger.debug(f"Light {light['name']} is already {'on' if is_on else 'off'}")
                else:
                    _logger.debug(f"Changing light {light['name']} to {'on' if is_on else 'off'}")
                    light["is_on"] = is_on
                return light
        return None
    
    def save_state(self):
        return self._lights
    
    def load_state(self, state):
        self._lights = state