"""Tests for ServiceRegistry (RED phase: class doesn't exist yet).

Design: ADR-001 (ServiceRegistry dataclass)
"""


class TestServiceRegistry:
    """ServiceRegistry dataclass construction."""

    def test_all_fields_default_to_none(self):
        """Every service field defaults to None when not provided."""
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        assert registry.vision is None
        assert registry.chronicle is None
        assert registry.guardian is None
        assert registry.pulse is None
        assert registry.optimizer is None
        assert registry.oracle is None

    def test_all_fields_populated(self):
        """All service fields accept a value."""
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry(
            vision="vision_mock",
            chronicle="chronicle_mock",
            guardian="guardian_mock",
            pulse="pulse_mock",
            optimizer="optimizer_mock",
            oracle="oracle_mock",
        )
        assert registry.vision == "vision_mock"
        assert registry.chronicle == "chronicle_mock"
        assert registry.guardian == "guardian_mock"
        assert registry.pulse == "pulse_mock"
        assert registry.optimizer == "optimizer_mock"
        assert registry.oracle == "oracle_mock"

    def test_partial_population(self):
        """Some fields can be set while others remain None."""
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry(vision="vision_obj", guardian="guardian_obj")
        assert registry.vision == "vision_obj"
        assert registry.guardian == "guardian_obj"
        assert registry.chronicle is None
        assert registry.pulse is None
        assert registry.optimizer is None
        assert registry.oracle is None

    def test_repr_contains_field_names(self):
        """repr includes service field names for debugging."""
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry(vision="v")
        r = repr(registry)
        assert "vision" in r
        assert "chronicle" in r

    def test_is_dataclass(self):
        """ServiceRegistry is a dataclass."""
        from dataclasses import is_dataclass

        from apoch.public_api.registry import ServiceRegistry

        assert is_dataclass(ServiceRegistry)
