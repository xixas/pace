"""The GTK4 + libadwaita app. `main(argv)` is the entry point `pace.cli.main` calls (contract section 5)."""


def main(argv: list[str]) -> int:
    from pace.ui.app import run

    return run(argv)
