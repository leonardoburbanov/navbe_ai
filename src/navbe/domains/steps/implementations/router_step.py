"""Router step implementation."""

from typing import Any

from simpleeval import (
    FeatureNotAvailable,
    FunctionNotDefined,
    InvalidExpression,
    NameNotDefined,
    simple_eval,
)

from navbe.core.exceptions import ExecutionError, ValidationError
from navbe.domains.steps.interfaces import StepContext
from navbe.domains.steps.models import StepConfig
from navbe.domains.steps.registry import StepRegistry


class RouterConfig(StepConfig):
    """Configuration for choosing the next node from a safe expression."""

    condition: str
    routes: dict[str, str]


@StepRegistry.register("router")
class RouterStep:
    """Evaluate a safe route condition and return the next node id."""

    config_schema = RouterConfig

    def __init__(self, config: dict[str, Any]) -> None:
        """Validate and store router config."""
        self.config = RouterConfig.model_validate(config)

    async def run(self, ctx: StepContext) -> Any:
        """Evaluate the condition in a sandboxed expression evaluator."""
        try:
            result = simple_eval(
                self.config.condition,
                names={
                    "flow_vars": ctx.flow_vars,
                    "node_outputs": ctx.flow_vars.get("node_outputs", {}),
                },
            )
        except (SyntaxError, InvalidExpression) as exc:
            raise ValidationError(
                f"Invalid router condition: '{self.config.condition}'",
                details={"condition": self.config.condition},
            ) from exc
        except (FeatureNotAvailable, FunctionNotDefined, NameNotDefined) as exc:
            raise ExecutionError(
                "Router condition could not be evaluated",
                details={"condition": self.config.condition},
            ) from exc

        if result not in self.config.routes:
            raise ExecutionError(
                f"Router condition result '{result}' not in defined routes",
                details={"result": result, "routes": list(self.config.routes)},
            )
        return {"route": result, "next_node": self.config.routes[result]}
