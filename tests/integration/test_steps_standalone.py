"""Standalone step composition tests without a Flow or execution engine."""

from navbe.domains.steps.implementations.set_var import SetVarStep
from navbe.domains.steps.implementations.transform import TransformStep
from navbe.domains.steps.interfaces import StepContext


async def test_set_var_then_transform_chain_manually() -> None:
    """Proves steps compose without any orchestration layer."""
    set_var = SetVarStep({"var_name": "total", "value_from": "amount"})
    ctx1 = StepContext(node_id="n1", input_data={"amount": 42}, flow_vars={})
    out1 = await set_var.run(ctx1)
    assert out1 == {"var_name": "total", "value": 42}

    transform = TransformStep({"query": "SELECT amount * 2 as doubled FROM input"})
    ctx2 = StepContext(node_id="n2", input_data=[{"amount": 42}], flow_vars={})
    out2 = await transform.run(ctx2)
    assert out2 == [{"doubled": 84}]
