"""Tests for error code catalog and helper (RED phase: constants don't exist yet).

Design: ADR-004 (error codes)
Spec: mcp-public-api §Catálogo Global de Códigos de Error
"""


class TestErrorCodeConstants:
    """Each error code constant exists, has the correct string value, and is non-empty."""

    def test_err_timeout(self):
        from apoch.public_api.errors import ERR_TIMEOUT

        assert ERR_TIMEOUT == "ERR_TIMEOUT"
        assert isinstance(ERR_TIMEOUT, str)

    def test_err_no_data(self):
        from apoch.public_api.errors import ERR_NO_DATA

        assert ERR_NO_DATA == "ERR_NO_DATA"
        assert isinstance(ERR_NO_DATA, str)

    def test_err_not_initialized(self):
        from apoch.public_api.errors import ERR_NOT_INITIALIZED

        assert ERR_NOT_INITIALIZED == "ERR_NOT_INITIALIZED"

    def test_err_dependency_unavailable(self):
        from apoch.public_api.errors import ERR_DEPENDENCY_UNAVAILABLE

        assert ERR_DEPENDENCY_UNAVAILABLE == "ERR_DEPENDENCY_UNAVAILABLE"

    def test_err_permission_denied(self):
        from apoch.public_api.errors import ERR_PERMISSION_DENIED

        assert ERR_PERMISSION_DENIED == "ERR_PERMISSION_DENIED"

    def test_err_invalid_argument(self):
        from apoch.public_api.errors import ERR_INVALID_ARGUMENT

        assert ERR_INVALID_ARGUMENT == "ERR_INVALID_ARGUMENT"

    def test_err_internal(self):
        from apoch.public_api.errors import ERR_INTERNAL

        assert ERR_INTERNAL == "ERR_INTERNAL"

    def test_err_unknown(self):
        from apoch.public_api.errors import ERR_UNKNOWN

        assert ERR_UNKNOWN == "ERR_UNKNOWN"

    def test_all_codes_have_non_empty_strings(self):
        """All error codes must be non-empty strings."""
        from apoch.public_api.errors import (
            ERR_DEPENDENCY_UNAVAILABLE,
            ERR_INTERNAL,
            ERR_INVALID_ARGUMENT,
            ERR_NO_DATA,
            ERR_NOT_INITIALIZED,
            ERR_PERMISSION_DENIED,
            ERR_TIMEOUT,
            ERR_UNKNOWN,
        )

        for code in (
            ERR_TIMEOUT,
            ERR_NO_DATA,
            ERR_NOT_INITIALIZED,
            ERR_DEPENDENCY_UNAVAILABLE,
            ERR_PERMISSION_DENIED,
            ERR_INVALID_ARGUMENT,
            ERR_INTERNAL,
            ERR_UNKNOWN,
        ):
            assert isinstance(code, str)
            assert len(code) > 0


class TestErrorResponseHelper:
    """error_response() helper builds error dict."""

    def test_returns_dict_with_ok_false(self):
        from apoch.public_api.errors import error_response

        result = error_response("ERR_TIMEOUT", "Module did not respond")
        assert result == {
            "ok": False,
            "error": {
                "code": "ERR_TIMEOUT",
                "message": "Module did not respond",
            },
        }

    def test_accepts_error_constants(self):
        from apoch.public_api.errors import ERR_NO_DATA, error_response

        result = error_response(ERR_NO_DATA, "No data available")
        assert result["error"]["code"] == "ERR_NO_DATA"

    def test_message_can_be_empty_string(self):
        """Message can be empty for errors without details."""
        from apoch.public_api.errors import error_response

        result = error_response("ERR_UNKNOWN", "")
        assert result["error"]["message"] == ""
