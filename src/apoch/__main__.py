"""Entry point for ``python -m apoch``.

When the package is invoked as a module, prints usage information since the
full CLI depends on subcommands defined in ``apoch.cli``.
"""

import sys


def _print_help() -> None:
    help_text = (
        "Usage: apoch [OPTIONS] COMMAND [ARGS]...\n"
        "\n"
        "  Apoch-AI: AI-assisted development workflow framework.\n"
        "\n"
        "Options:\n"
        "  --version   Show the version and exit.\n"
        "  --help      Show this message and exit.\n"
        "\n"
        "Commands:\n"
        "  install     Install Apoch-AI or a specific module.\n"
        "  uninstall   Remove Apoch-AI or a specific module.\n"
        "  list        List all modules and their states.\n"
        "  status      System health and gateway status.\n"
        "  mcp         Manage the MCP server.\n"
        "  config      View or edit Apoch-AI configuration.\n"
        "  doctor      Run diagnostic checks.\n"
    )
    sys.stdout.write(help_text)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        _print_help()
        sys.exit(0)
    elif args[0] == "--version":
        from apoch import __version__

        sys.stdout.write(f"apoch, version {__version__}\n")
        sys.exit(0)
    else:
        _print_help()
        sys.stdout.write(
            f"\nError: No such command '{args[0]}'.\n"
            f"Run 'apoch --help' for usage.\n"
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
