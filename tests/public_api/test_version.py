"""Tests for API version constant (RED phase: constant doesn't exist yet).

Design: ADR-005
Spec: mcp-public-api §Versionado de la API
"""


class TestAPIVersion:
    """API_VERSION constant value and type."""

    def test_api_version_is_string(self):
        """API_VERSION must be a string."""
        from apoch.public_api.version import API_VERSION

        assert isinstance(API_VERSION, str)

    def test_api_version_equals_1_0(self):
        """API_VERSION must equal "1.0" for initial release."""
        from apoch.public_api.version import API_VERSION

        assert API_VERSION == "1.0"

    def test_api_version_is_not_empty(self):
        """API_VERSION must be a non-empty string."""
        from apoch.public_api.version import API_VERSION

        assert len(API_VERSION) > 0
