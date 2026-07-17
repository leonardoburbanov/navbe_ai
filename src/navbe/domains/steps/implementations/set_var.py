"""Set variable step implementation."""

from typing import Any

import jmespath
from jmespath.exceptions import JMESPathError

from navbe.core.exceptions import ValidationError
from navbe.domains.steps.interfaces import StepContext
from navbe.domains.steps.models import StepConfig
from navbe.domains.steps.registry import StepRegistry


class SetVarConfig(StepConfig):
    """Configuration for extracting one value from step input."""

    var_name: str
    value_from: str


@StepRegistry.register("set_var")
class SetVarStep:
    """Extract a value from input data using JMESPath."""

    config_schema = SetVarConfig

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate and store set-var config."""
        self.config = SetVarConfig.model_validate(config)

    async def run(self, ctx: StepContext) -> Any:
        """Return the extracted value paired with its variable name."""
        try:
            value = jmespath.search(self.config.value_from, ctx.input_data)
        except JMESPathError as exc:
            raise ValidationError(
                f"Invalid JMESPath expression: '{self.config.value_from}'",
                details={"expression": self.config.value_from},
            ) from exc
        return {"var_name": self.config.var_name, "value": value}
