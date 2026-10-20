import os
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"
GITHUB_URL = "https://github.com/search?q=PDF+to+Audio+Maxwell&type=repositories"

ORANGE = "\033[38;5;208m"
RED = "\033[38;5;196m"
GOLD = "\033[38;5;220m"
CYAN = "\033[38;5;81m"
MUTED = "\033[38;5;245m"
BOLD = "\033[1m"
RESET = "\033[0m"

TITLE_ART = (
    " ____  ____  _____   _____ ___     _    _   _ ____ ___ ___  ",
    "|  _ \\|  _ \\|  ___| |_   _/ _ \\   / \\  | | | |  _ \\_ _/ _ \\ ",
    "| |_) | | | | |_      | || | | | / _ \\ | | | | | | | | | | |",
    "|  __/| |_| |  _|     | || |_| |/ ___ \\| |_| | |_| | | |_| |",
    "|_|   |____/|_|       |_| \\___//_/   \\_\\\\___/|____/___\\___/ ",
)


def supports_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def paint(text: str, color: str) -> str:
    if not supports_color():
        return text
    return f"{color}{text}{RESET}"


def show_banner() -> None:
    print()
    for index, line in enumerate(TITLE_ART):
        color = ORANGE if index < 3 else RED
        print(paint(line, color))

    details = (
        ("PROJECT", "PDF to Audio"),
        ("AUTHOR", "Maxwell"),
        ("SOURCE", f"Open source on GitHub: {GITHUB_URL}"),
        ("NOTICE", "Use responsibly; check generated audio and respect document copyrights."),
    )
    label_width = max(len(label) for label, _ in details)
    panel_width = max(len(value) + label_width + 5 for label, value in details)
    border = "+" + "-" * (panel_width + 2) + "+"
    print(paint(border, MUTED))
    for label, value in details:
        content = f" {paint(label.ljust(label_width), GOLD)}  {value}"
        padding = panel_width - label_width - len(value) - 3
        print(f"{paint('|', MUTED)}{content}{' ' * padding} {paint('|', MUTED)}")
    print(paint(border, MUTED))
    print()


def pause_for_acknowledgement() -> None:
    try:
        input("\nPress Enter to return to the menu...")
    except EOFError:
        print()


def install_dependencies() -> None:
    print(f"\nInstalling dependencies with {sys.executable} ...\n")
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(REQUIREMENTS_FILE),
            ],
            check=True,
            cwd=PROJECT_DIR,
        )
    except subprocess.CalledProcessError as error:
        print(
            paint(
                f"\nDependency installation failed (pip exited with code {error.returncode}).",
                RED,
            )
        )
    except OSError as error:
        print(paint(f"\nCould not start pip: {error}", RED))
    else:
        print(paint("\nDependencies installed successfully.", CYAN))
    pause_for_acknowledgement()


def launch_gui() -> None:
    import tkinter as tk

    from gui import PDFToAudioApp

    root = tk.Tk()
    PDFToAudioApp(root)
    root.mainloop()


def main() -> None:
    show_banner()
    while True:
        print(paint("  [1] Install Dependencies", BOLD + ORANGE))
        print(paint("  [2] Run GUI", BOLD + CYAN))
        try:
            choice = input("\nSelect an option [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if choice == "1":
            install_dependencies()
        elif choice == "2":
            try:
                launch_gui()
            except ImportError as error:
                print(paint(f"\nCould not start the GUI: {error}", RED))
                pause_for_acknowledgement()
        else:
            print(paint("Please choose 1 or 2.", RED))


if __name__ == "__main__":
    main()
