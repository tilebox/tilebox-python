import os
import re
import sys
from typing import TextIO

_STYLES = {
    "bold": "1",
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
}
_TAG = re.compile(r"\[(/?)([a-z]+(?: [a-z]+)*)\]")
_RESET = "\033[0m"


def print_notice(message: str, output: TextIO | None = None) -> None:
    """Print a notice with nested color/bold tags, e.g. `[yellow][bold]Hello[/bold][/yellow]`.

    Tags can combine styles (`[bold red]...[/bold red]`). Unknown or mismatched
    tags remain literal. Redirected output, NO_COLOR, and dumb terminals use plain text.
    Output defaults to the current sys.stderr.
    """
    if output is None:
        output = sys.stderr
    color = output.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"
    styles: list[str] = []

    def replace_tag(match: re.Match[str]) -> str:
        closing, style = match.groups()
        if any(name not in _STYLES for name in style.split()):
            return match.group()
        if closing:
            if not styles or styles[-1] != style:
                return match.group()
            styles.pop()
        else:
            styles.append(style)
        if not color:
            return ""
        codes = [_STYLES[name] for active in styles for name in active.split()]
        return _RESET + (f"\033[{';'.join(codes)}m" if codes else "")

    rendered = _TAG.sub(replace_tag, message)
    if color and styles:
        rendered += _RESET
    output.write(rendered + "\n")
