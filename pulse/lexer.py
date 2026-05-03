from __future__ import annotations

from dataclasses import dataclass

from .errors import PulseSyntaxError


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    col: int


KEYWORDS = {"true", "false", "and", "or", "not"}


SINGLE = {
    "(": "LPAREN",
    ")": "RPAREN",
    ",": "COMMA",
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "%": "PERCENT",
    "<": "LT",
    ">": "GT",
    "=": "ASSIGN",
    ".": "DOT",
}


def lex_expr(text: str, *, filename: str, line: int) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    col = 1

    def err(msg: str) -> PulseSyntaxError:
        return PulseSyntaxError(msg, filename=filename, line=line, col=col)

    while i < len(text):
        ch = text[i]
        if ch in " \t\r":
            i += 1
            col += 1
            continue

        # identifiers / keywords
        if ch.isalpha() or ch == "_":
            start_i = i
            start_col = col
            i += 1
            col += 1
            while i < len(text) and (text[i].isalnum() or text[i] == "_"):
                i += 1
                col += 1
            word = text[start_i:i]
            kind = "KW" if word in KEYWORDS else "IDENT"
            tokens.append(Token(kind, word, line, start_col))
            continue

        # numbers
        if ch.isdigit():
            start_i = i
            start_col = col
            i += 1
            col += 1
            has_dot = False
            while i < len(text):
                if text[i].isdigit():
                    i += 1
                    col += 1
                    continue
                if text[i] == "." and not has_dot:
                    has_dot = True
                    i += 1
                    col += 1
                    continue
                break
            tokens.append(Token("NUMBER", text[start_i:i], line, start_col))
            continue

        # strings
        if ch in {"'", '"'}:
            quote = ch
            start_col = col
            i += 1
            col += 1
            out = []
            while i < len(text) and text[i] != quote:
                if text[i] == "\\":
                    if i + 1 >= len(text):
                        raise err("unterminated string escape")
                    nxt = text[i + 1]
                    mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"'}
                    out.append(mapping.get(nxt, nxt))
                    i += 2
                    col += 2
                    continue
                out.append(text[i])
                i += 1
                col += 1
            if i >= len(text) or text[i] != quote:
                raise err("unterminated string literal")
            i += 1
            col += 1
            tokens.append(Token("STRING", "".join(out), line, start_col))
            continue

        # multi-char operators
        if ch in {"=", "!", "<", ">"} and i + 1 < len(text):
            two = text[i : i + 2]
            if two in {"==", "!=", "<=", ">="}:
                kind = {"==": "EQEQ", "!=": "NE", "<=": "LTE", ">=": "GTE"}[two]
                tokens.append(Token(kind, two, line, col))
                i += 2
                col += 2
                continue

        # single-char operators / punctuation
        if ch in SINGLE:
            tokens.append(Token(SINGLE[ch], ch, line, col))
            i += 1
            col += 1
            continue

        raise err(f"unexpected character {ch!r}")

    tokens.append(Token("EOF", "", line, col))
    return tokens

