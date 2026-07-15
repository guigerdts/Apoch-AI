"""Tests for StackComponent abstract base class.

Spec: core-stack
Design: Core Stack Installation & Lifecycle — StackComponent Interface
"""

from __future__ import annotations

from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor


class TestStackComponentInterface:
    """Verify StackComponent defines the expected abstract interface."""

    def test_descriptor_is_abstract_property(self):
        """descriptor must be an abstract property."""
        assert isinstance(StackComponent.descriptor, property)

    def test_has_abstract_methods(self):
        """StackComponent declares all required abstract methods."""
        expected = {"install", "uninstall", "verify", "activate", "deactivate", "detect", "health"}
        for name in expected:
            method = getattr(StackComponent, name, None)
            assert method is not None, f"Missing method: {name}"


class TestConcreteComponent:
    """Verify a minimal concrete component can be created."""

    async def test_can_implement_minimal_component(self):
        """A class implementing all abstract methods can be instantiated."""
        from apoch.stack.result import OperationResult

        class MinimalComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return StackDescriptor(
                    name="minimal",
                    kind="services",
                    version="0.1.0",
                    description="Minimal test component",
                    entry_point="test:MinimalComponent",
                )

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="0.1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="verified")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="activated")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="deactivated")

            async def health(self) -> dict:
                return {"status": "healthy"}

        comp = MinimalComponent()
        assert comp.descriptor.name == "minimal"
        assert (await comp.install()).success is True
        assert (await comp.uninstall()).success is True
        assert (await comp.verify()).message == "verified"
        assert (await comp.activate()).success is True
        assert (await comp.deactivate()).success is True

    async def test_verify_passes_skip_async(self):
        """skip_async is passed through to verify."""
        from apoch.stack.result import OperationResult

        class SkipAwareComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return StackDescriptor(
                    name="skip-aware",
                    kind="services",
                    version="0.1.0",
                    description="Skip-aware test",
                    entry_point="test:SkipAwareComponent",
                )

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="0.1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="skip-aware", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="skip-aware", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                if skip_async:
                    return OperationResult(
                        success=True, component="skip-aware", message="local-only"
                    )
                return OperationResult(success=True, component="skip-aware", message="full")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="skip-aware", message="activated")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="skip-aware", message="deactivated")

            async def health(self) -> dict:
                return {"status": "healthy"}

        comp = SkipAwareComponent()
        assert (await comp.verify(skip_async=True)).message == "local-only"
        assert (await comp.verify()).message == "full"
