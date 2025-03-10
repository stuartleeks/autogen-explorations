import datetime
import logging
from dataclasses import dataclass, asdict
from typing import Annotated

_logger = logging.getLogger(__name__)


@dataclass
class DishInstructionStep:
    description: str
    duration_minutes: int


@dataclass
class DishInstruction:
    name: str
    steps: list[DishInstructionStep] | None = None
    steps_frozen: list[DishInstructionStep] | None = None


@dataclass
class Dish:
    name: str
    frozen: bool


@dataclass
class PreparationStep:
    dish_name: str
    start_time: datetime.time
    description: str


class MealsPlugin:
    # This data could be stored in a database or other data source
    dish_instructions = {
        "pasta": DishInstruction(
            name="Pasta",
            steps=[
                DishInstructionStep(
                    description="Boil water", duration_minutes=10),
                DishInstructionStep(
                    description="Cook pasta", duration_minutes=10),
            ]),
        "biryani": DishInstruction(
            name="Biryani",
            steps=[
                DishInstructionStep(
                    description="Put in oven", duration_minutes=15),
                DishInstructionStep(
                    description="Stir", duration_minutes=15),
            ],
            steps_frozen=[
                DishInstructionStep(
                    description="Put in over", duration_minutes=20),
                DishInstructionStep(
                    description="Stir", duration_minutes=20),
            ]
        ),
        "lasagne": DishInstruction(
            name="Lasagne",
            steps=[
                DishInstructionStep(description="Cook", duration_minutes=35),
            ],
            steps_frozen=[
                DishInstructionStep(description="Cook", duration_minutes=45),
            ],
        ),
        "soup": DishInstruction(
            name="Soup",
            steps=[
                DishInstructionStep(description="Heat soup",
                                    duration_minutes=10),
            ]),
        "salad": DishInstruction(
            name="Salad",
            steps=[
                DishInstructionStep(description="Prep", duration_minutes=10),
            ]),
    }

    dishes: list[Dish] = []

    #
    # Dishes
    #

    def get_dish_options(
        self,
    ) -> dict:
        """Gets a list of dishes to choose from, including their cooking time"""
        _logger.debug(f"get_dish_options.")
        return self.dish_instructions

    #
    # Meals
    #

    def add_meal(
        self,
        name: str,
        frozen: bool
    ) -> str:
        """Adds a dish to the list of dishes to cook"""
        _logger.debug(f"add_dish {name} {frozen}")
        lower_name = name.lower()
        if lower_name in self.dish_instructions:
            if frozen:
                if self.dish_instructions[lower_name].steps_frozen:
                    self.dishes.append(Dish(name=name, frozen=True))
                    return f"Dish {name} added."
                else:
                    return f"Dish {name} cannot cooked from frozen."
            else:
                if self.dish_instructions[lower_name].steps:
                    self.dishes.append(Dish(name=name, frozen=False))
                    return f"Dish {name} added."
                else:
                    return f"Dish {name} cannot cooked from fresh."
        else:
            return f"Dish {name} not found."

    def remove_dish(
        self,
        name: str,
    ) -> str:
        """Removes a dishes from the list of dishes to cook"""
        _logger.debug(f"remove_dish: {name}")
        for dish in self.dishes:
            if dish.name.lower() == name.lower():
                self.dishes.remove(dish)
                return f"Dish {name} removed."
        return f"Dish {name} not found."

    def get_dishes(
        self,
    ) -> list[Dish]:
        """Gets the list of dishes to cook"""
        _logger.debug(f"get_dishes: {self.dishes}")
        return self.dishes

    def get_meal_steps(
        self,
        ready_time: str,
    ) -> list[PreparationStep]:
        """Gets the instructions for the meal listing the steps for all the dishes to be ready for the desired time"""
        _logger.debug(
            f"get_meal steps - starting (ready_time:{ready_time})...")

        if isinstance(ready_time, str):
            try:
                # Parse "18:00"
                ready_time = datetime.datetime.strptime(
                    ready_time, "%H:%M").time()
                now = datetime.datetime.now()
                ready_time = datetime.datetime.combine(now.date(), ready_time)
            except ValueError:
                try:
                    # Parse "18:00:00"
                    ready_time = datetime.datetime.strptime(
                        ready_time, "%H:%M:%S").time()
                    now = datetime.datetime.now()
                    ready_time = datetime.datetime.combine(
                        now.date(), ready_time)
                except ValueError:
                    try:
                        # Parse "2022-12-31T18:00:00Z"
                        ready_time = datetime.datetime.fromisoformat(
                            ready_time)
                    except ValueError:
                        try:
                            # Parse "2022-12-31T18:00"
                            ready_time = datetime.datetime.strptime(
                                ready_time, "%Y-%m-%dT%H:%M")
                        except ValueError:
                            return f"Time format not recognized: try '17:00', '17:00:00', '2022-12-31T17:00:00Z', or '2022-12-31T17:00'."

        preparation_steps = []
        for dish in self.dishes:
            lower_name = dish.name.lower()
            dish_instruction = self.dish_instructions[lower_name]
            steps = dish_instruction.steps_frozen if dish.frozen else dish_instruction.steps
            step_end_time = ready_time
            for step in reversed(steps):
                step_end_time = step_end_time - \
                    datetime.timedelta(minutes=step.duration_minutes)
                preparation_steps.append(
                    PreparationStep(
                        dish_name=dish.name,
                        start_time=step_end_time,
                        description=step.description
                    )
                )
        preparation_steps.sort(key=lambda x: x.start_time)
        _logger.debug(f"get_meal steps - result: {preparation_steps}")
        return preparation_steps

    # @kernel_function(
    #     name="get_current_date",
    #     description="Gets the current date",
    # )
    # def get_current_date(self):
    #     _logger.debug(f"Getting current date.")
    #     return datetime.datetime.now().date()

    def save_state(self):
        return [asdict(d) for d in self.dishes]

    def load_state(self, state):
        self.dishes = [Dish(name=d["name"], frozen=d["frozen"]) for d in state]
