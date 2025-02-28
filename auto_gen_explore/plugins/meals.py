import datetime
import logging
from dataclasses import dataclass
from typing import Annotated
from semantic_kernel.functions import kernel_function

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
    time_to_be_ready = None

    #
    # Dishes
    #

    @kernel_function(
        name="get_dish_options",
        description="Gets a list of dishes to choose from, including their cooking time",
    )
    def get_dish_options(
        self,
    ) -> dict:
        """Gets a list of dishes to choose from, including their cooking time"""
        _logger.debug(f"get_dish_options.")
        return self.dish_instructions

    #
    # Meals
    #

    @kernel_function(
        name="add_dish",
        description="Adds a dish to the list of dishes to cook",
    )
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
                if self.dish_instructions[name].steps:
                    self.dishes.append(Dish(name=name, frozen=False))
                    return f"Dish {name} added."
                else:
                    return f"Dish {name} cannot cooked from fresh."
        else:
            return f"Dish {name} not found."

    @kernel_function(
        name="remove_dish",
        description="Removes a dish from the list of dishes to cook",
    )
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

    @kernel_function(
        name="get_dishes",
        description="Gets the list of dishes to cook",
    )
    def get_dishes(
        self,
    ) -> list[Dish]:
        """Gets the list of dishes to cook"""
        _logger.debug(f"get_dishes: {self.dishes}")
        return self.dishes

    @kernel_function(
        name="get_meal_steps",
        description="Gets the instructions for the meal listing the steps for all the dishes to be ready for the desired time",
    )
    def get_meal_steps(
        self,
    ) -> list[PreparationStep]:
        """Gets the instructions for the meal listing the steps for all the dishes to be ready for the desired time"""
        _logger.debug(f"get_meal steps - starting...")
        if not self.time_to_be_ready:
            raise ValueError("Time to be ready not set.")

        preparation_steps = []
        for dish in self.dishes:
            lower_name = dish.name.lower()
            dish_instruction = self.dish_instructions[lower_name]
            steps = dish_instruction.steps_frozen if dish.frozen else dish_instruction.steps
            step_end_time = self.time_to_be_ready
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


    #
    # Ready time functions
    #

    # @kernel_function(
    #     name="set_time_to_be_ready",
    #     description="Sets the time by which the meal should be ready",
    #     # description="Sets the time by which the meal should be ready - specify as yyyy-mm-ddThh:mm",
    # )
    # def set_time_to_be_ready(
    #     self,
    #     time: str,
    # ) -> str:
    #     """Sets the time by which the meal should be ready"""
    #     _logger.debug(f"Time to be ready set to {time}.")
    #     try:
    #         # Parse "2022-12-31T18:00:00Z"
    #         time = datetime.datetime.fromisoformat(time)
    #     except ValueError:
    #         # Parse "2022-12-31T18:00"
    #         time = datetime.datetime.strptime(time, "%Y-%m-%dT%H:%M")
                
    #     self.time_to_be_ready = time
    #     return f"Time to be ready set to {time}."

    @kernel_function(
        name="set_time_to_be_ready",
        description="Sets the time by which the meal should be ready",
    )
    def set_time_to_be_ready(
        self,
        time: str | datetime.datetime,
    ) -> str:
        """Sets the time by which the meal should be ready"""
        _logger.debug(f"Time to be ready set to {time}.")
        if isinstance(time, str):
            try :
                # Parse "18:00"
                time = datetime.datetime.strptime(time, "%H:%M")
            except ValueError:
                try:
                    # Parse "18:00:00"
                    time = datetime.datetime.strptime(time, "%H:%M:%S")
                except ValueError:
                    try:
                        # Parse "2022-12-31T18:00:00Z"
                        time = datetime.datetime.fromisoformat(time)
                    except ValueError:
                        try:
                            # Parse "2022-12-31T18:00"
                            time = datetime.datetime.strptime(time, "%Y-%m-%dT%H:%M")
                        except ValueError:
                            return f"Time format not recognized: try '17:00', '17:00:00', '2022-12-31T17:00:00Z', or '2022-12-31T17:00'."
                
        self.time_to_be_ready = time
        return f"Time to be ready set to {time}."

    @kernel_function(
        name="get_time_to_be_ready",
        description="Gets the time by which the meal should be ready",
    )
    def get_time_to_be_ready(
        self,
    ) -> datetime.datetime:
        """Gets the time by which the meal should be ready"""
        _logger.debug(f"Time to be ready: {self.time_to_be_ready}")
        return self.time_to_be_ready


    # @kernel_function(
    #     name="get_current_date",
    #     description="Gets the current date",
    # )
    # def get_current_date(self):
    #     _logger.debug(f"Getting current date.")
    #     return datetime.datetime.now().date()