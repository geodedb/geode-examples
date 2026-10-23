#!/usr/bin/env python3
"""Convert a GQL file to one statement per line for the CLI's batch mode."""
import sys


def statements(text):
    current = []
    quote = None
    braces = 0
    i = 0
    while i < len(text):
        char = text[i]
        pair = text[i:i + 2]
        if quote:
            current.append(char)
            if char == "\\" and i + 1 < len(text):
                i += 1
                current.append(text[i])
            elif char == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 1
                    current.append(text[i])
                else:
                    quote = None
        elif pair in ("--", "//") or char == "#":
            end = text.find("\n", i)
            i = len(text) if end == -1 else end
            current.append(" ")
            continue
        elif pair == "/*":
            end = text.find("*/", i + 2)
            if end == -1:
                raise ValueError("Unterminated GQL block comment")
            i = end + 2
            current.append(" ")
            continue
        elif char in ("'", '"', "`"):
            quote = char
            current.append(char)
        elif char == ";" and braces == 0:
            statement = "".join(current).strip()
            if statement:
                yield statement
            current = []
        else:
            if char == "{":
                braces += 1
            elif char == "}":
                braces -= 1
                if braces < 0:
                    raise ValueError("Unbalanced GQL braces")
            current.append(" " if char in "\r\n" else char)
        i += 1
    if quote or braces:
        raise ValueError("Unterminated GQL string or statement block")
    if "".join(current).strip():
        raise ValueError("GQL file must terminate its final statement with a semicolon")


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as source:
        batch = list(statements(source.read()))
    if not batch or any("\n" in statement or "\r" in statement for statement in batch):
        sys.exit("Batch requires nonempty statements without embedded literal newlines")
    print("\n".join(batch))
