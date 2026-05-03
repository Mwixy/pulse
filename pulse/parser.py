from __future__ import annotations

import re
from dataclasses import dataclass

from . import ast
from .errors import PulseSyntaxError
from .lexer import Token, lex_expr


@dataclass(frozen=True)
class _Line:
    no: int
    text: str


_FUNC_RE = re.compile(r"^func\s+([A-Za-z_]\w*)\s*\(\s*\)\s*$")
_IMPORT_RE = re.compile(r"^let\s*\(\s*([A-Za-z_]\w*)\s*\)\s*$")
_GLET_RE = re.compile(r"^let\s+([A-Za-z_]\w*)\s*=\s*(.+)$")
_ENTRY_NAME_RE = re.compile(r"^[A-Za-z_]\w*$")
_BUTTON_RE = re.compile(r"^(.+?)(?:\(\s*([A-Za-z_]\w*)\s*\))?$")
_UPDATE_RE = re.compile(r"^update\s*\(\s*([A-Za-z_]\w*)\s*\)\s*$")
_ATTR_START_RE = re.compile(r"\s([A-Za-z_]\w*)\s*=")


def _strip_comment(line: str) -> str:
    idx = line.find("!!")
    if idx != -1:
        return line[:idx]
    return line


class _ExprParser:
    def __init__(self, tokens: list[Token], *, filename: str):
        self.tokens = tokens
        self.i = 0
        self.filename = filename

    def _peek(self) -> Token:
        return self.tokens[self.i]

    def _advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _expect(self, kind: str, msg: str) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise PulseSyntaxError(msg, filename=self.filename, line=tok.line, col=tok.col)
        return self._advance()

    def parse(self) -> ast.Expr:
        expr = self._or()
        eof = self._peek()
        if eof.kind != "EOF":
            raise PulseSyntaxError("unexpected token after expression", filename=self.filename, line=eof.line, col=eof.col)
        return expr

    def _or(self) -> ast.Expr:
        left = self._and()
        while self._peek().kind == "KW" and self._peek().text == "or":
            op = self._advance()
            right = self._and()
            left = ast.Binary(line=op.line, op="or", left=left, right=right)
        return left

    def _and(self) -> ast.Expr:
        left = self._equality()
        while self._peek().kind == "KW" and self._peek().text == "and":
            op = self._advance()
            right = self._equality()
            left = ast.Binary(line=op.line, op="and", left=left, right=right)
        return left

    def _equality(self) -> ast.Expr:
        left = self._comparison()
        while self._peek().kind in {"EQEQ", "NE"}:
            op = self._advance()
            right = self._comparison()
            left = ast.Binary(line=op.line, op=op.text, left=left, right=right)
        return left

    def _comparison(self) -> ast.Expr:
        left = self._term()
        while self._peek().kind in {"LT", "LTE", "GT", "GTE"}:
            op = self._advance()
            right = self._term()
            left = ast.Binary(line=op.line, op=op.text, left=left, right=right)
        return left

    def _term(self) -> ast.Expr:
        left = self._factor()
        while self._peek().kind in {"PLUS", "MINUS"}:
            op = self._advance()
            right = self._factor()
            left = ast.Binary(line=op.line, op=op.text, left=left, right=right)
        return left

    def _factor(self) -> ast.Expr:
        left = self._unary()
        while self._peek().kind in {"STAR", "SLASH", "PERCENT"}:
            op = self._advance()
            right = self._unary()
            left = ast.Binary(line=op.line, op=op.text, left=left, right=right)
        return left

    def _unary(self) -> ast.Expr:
        tok = self._peek()
        if tok.kind == "MINUS":
            op = self._advance()
            expr = self._unary()
            return ast.Unary(line=op.line, op="-", expr=expr)
        if tok.kind == "KW" and tok.text == "not":
            op = self._advance()
            expr = self._unary()
            return ast.Unary(line=op.line, op="not", expr=expr)
        return self._call()

    def _call(self) -> ast.Expr:
        expr = self._primary()
        while True:
            tok = self._peek()
            if tok.kind == "LPAREN":
                lpar = self._advance()
                args: list[ast.Expr] = []
                if self._peek().kind != "RPAREN":
                    args.append(self._or())
                    while self._peek().kind == "COMMA":
                        self._advance()
                        args.append(self._or())
                self._expect("RPAREN", "expected ')'")
                expr = ast.Call(line=lpar.line, callee=expr, args=args)
                continue
            if tok.kind == "DOT":
                self._advance()
                ident = self._expect("IDENT", "expected attribute name after '.'")
                expr = ast.GetAttr(line=ident.line, obj=expr, name=ident.text)
                continue
            break
        return expr

    def _primary(self) -> ast.Expr:
        tok = self._peek()
        if tok.kind == "NUMBER":
            t = self._advance()
            if "." in t.text:
                return ast.Literal(line=t.line, value=float(t.text))
            return ast.Literal(line=t.line, value=int(t.text))
        if tok.kind == "STRING":
            t = self._advance()
            return ast.Literal(line=t.line, value=t.text)
        if tok.kind == "KW" and tok.text in {"true", "false"}:
            t = self._advance()
            return ast.Literal(line=t.line, value=(t.text == "true"))
        if tok.kind == "IDENT":
            t = self._advance()
            return ast.Var(line=t.line, name=t.text)
        if tok.kind == "LPAREN":
            lpar = self._advance()
            expr = self._or()
            self._expect("RPAREN", "expected ')'")
            return expr
        raise PulseSyntaxError("expected expression", filename=self.filename, line=tok.line, col=tok.col)


def parse_source(source: str, *, filename: str) -> ast.Program:
    raw_lines = source.splitlines()
    lines: list[_Line] = []
    for idx, raw in enumerate(raw_lines, start=1):
        cleaned = _strip_comment(raw).strip()
        if cleaned:
            lines.append(_Line(idx, cleaned))

    p = _Parser(lines, filename=filename)
    body = p._parse_statements(stop_on_end=False, in_block=False)
    return ast.Program(line=1, body=body)


class _Parser:
    def __init__(self, lines: list[_Line], *, filename: str):
        self.lines = lines
        self.filename = filename
        self.i = 0

    def _eof(self) -> bool:
        return self.i >= len(self.lines)

    def _peek(self) -> _Line:
        return self.lines[self.i]

    def _advance(self) -> _Line:
        ln = self.lines[self.i]
        self.i += 1
        return ln

    def _syn(self, line: _Line, msg: str) -> PulseSyntaxError:
        return PulseSyntaxError(msg, filename=self.filename, line=line.no, col=1)

    def _parse_expr_text(self, expr_text: str, *, line_no: int) -> ast.Expr:
        toks = lex_expr(expr_text, filename=self.filename, line=line_no)
        return _ExprParser(toks, filename=self.filename).parse()

    def _parse_expr_tokens(self, toks: list[Token]) -> ast.Expr:
        return _ExprParser(toks, filename=self.filename).parse()

    def _split_head_and_attrs(self, text: str) -> tuple[str, str | None]:
        m = _ATTR_START_RE.search(text)
        if not m:
            return text.strip(), None
        head = text[: m.start()].strip()
        attrs = text[m.start() :].strip()
        return head, (attrs or None)

    def _parse_attrs(self, attrs_text: str, line: _Line) -> dict[str, ast.Expr]:
        toks = lex_expr(attrs_text, filename=self.filename, line=line.no)
        attrs: dict[str, ast.Expr] = {}
        i = 0
        # ignore final EOF token
        while i < len(toks) - 1:
            if i + 1 >= len(toks) - 1 or toks[i].kind != "IDENT" or toks[i + 1].kind != "ASSIGN":
                raise self._syn(line, "invalid attribute syntax")
            name = toks[i].text
            i += 2
            start = i
            # collect value tokens until next IDENT ASSIGN or EOF
            while i < len(toks) - 1:
                if i + 1 < len(toks) - 1 and toks[i].kind == "IDENT" and toks[i + 1].kind == "ASSIGN":
                    break
                i += 1
            value_tokens = toks[start:i]
            # add EOF for expression parser
            value_tokens = value_tokens + [Token("EOF", "", line.no, 1)]
            attrs[name] = self._parse_expr_tokens(value_tokens)
        return attrs

    def _parse_statements(self, *, stop_on_end: bool, in_block: bool) -> list[ast.StmtT]:
        out: list[ast.StmtT] = []
        while not self._eof():
            line = self._peek()

            if line.text == "end":
                if stop_on_end:
                    self._advance()
                    return out
                raise self._syn(line, "unexpected 'end' at top-level")

            if line.text.endswith(":"):
                out.append(self._parse_block(in_block=in_block))
                continue

            out.append(self._parse_statement(in_block=in_block))

        if stop_on_end:
            raise PulseSyntaxError("missing 'end' to close block", filename=self.filename, line=(self.lines[-1].no if self.lines else 1), col=1)
        return out

    def _parse_block(self, *, in_block: bool) -> ast.StmtT:
        line = self._advance()
        header = line.text[:-1].strip()

        # func
        m = _FUNC_RE.match(header)
        if m:
            name = m.group(1)
            body = self._parse_statements(stop_on_end=True, in_block=True)
            return ast.FuncDef(line=line.no, name=name, body=body)

        # window "Title" [attrs]:
        if header.startswith("window "):
            rest = header[len("window ") :].strip()
            if not rest:
                raise self._syn(line, "missing title for 'window'")
            head, attrs_text = self._split_head_and_attrs(rest)
            title_expr = self._parse_expr_text(head, line_no=line.no)
            attrs = self._parse_attrs(attrs_text, line) if attrs_text else {}
            body = self._parse_statements(stop_on_end=True, in_block=True)
            return ast.WindowBlock(line=line.no, title=title_expr, attrs=attrs, body=body)

        # Button "Text"(func_name) [attrs]:
        if header.startswith("Button "):
            rest = header[len("Button ") :].strip()
            if not rest:
                raise self._syn(line, "missing text for 'Button'")
            head, attrs_text = self._split_head_and_attrs(rest)
            m = _BUTTON_RE.match(head)
            if not m:
                raise self._syn(line, "invalid Button header")
            text_part = m.group(1).strip()
            func_name = m.group(2)
            if not text_part:
                raise self._syn(line, "missing text for 'Button'")
            text_expr = self._parse_expr_text(text_part, line_no=line.no)
            attrs = self._parse_attrs(attrs_text, line) if attrs_text else {}
            body = self._parse_statements(stop_on_end=True, in_block=True)
            return ast.ButtonBlock(line=line.no, text=text_expr, func_name=func_name, attrs=attrs, body=body)

        # other blocks: keyword + expr
        for kw, ctor in (
            ("if", ast.IfBlock),
            ("while", ast.WhileBlock),
            ("until", ast.UntilBlock),
            ("after", ast.AfterBlock),
            ("every", ast.EveryBlock),
        ):
            if header == kw or header.startswith(kw + " "):
                rest = header[len(kw) :].strip()
                if not rest:
                    raise self._syn(line, f"missing condition/expression for '{kw}'")
                expr = self._parse_expr_text(rest, line_no=line.no)
                body = self._parse_statements(stop_on_end=True, in_block=True)
                if ctor in (ast.AfterBlock, ast.EveryBlock):
                    return ctor(line=line.no, seconds=expr, body=body)  # type: ignore[arg-type]
                return ctor(line=line.no, cond=expr, body=body)  # type: ignore[arg-type]

        raise self._syn(line, f"unknown block header: {header!r}")

    def _parse_statement(self, *, in_block: bool) -> ast.StmtT:
        line = self._advance()
        txt = line.text

        # GUI: update(var)
        m = _UPDATE_RE.match(txt)
        if m:
            return ast.UpdateStmt(line=line.no, name=m.group(1))

        # GUI: Label "Text" [attrs]
        if txt.startswith("Label "):
            rest = txt[len("Label ") :].strip()
            if not rest:
                raise self._syn(line, "missing text for 'Label'")
            head, attrs_text = self._split_head_and_attrs(rest)
            expr = self._parse_expr_text(head, line_no=line.no)
            attrs = self._parse_attrs(attrs_text, line) if attrs_text else {}
            return ast.LabelStmt(line=line.no, text=expr, attrs=attrs)

        # GUI: Entry "name" [attrs]
        if txt.startswith("Entry "):
            rest = txt[len("Entry ") :].strip()
            if not rest:
                raise self._syn(line, "missing variable name for 'Entry'")
            head, attrs_text = self._split_head_and_attrs(rest)
            expr = self._parse_expr_text(head, line_no=line.no)
            if not isinstance(expr, ast.Literal) or not isinstance(expr.value, str):
                raise self._syn(line, "Entry expects a string literal variable name")
            var_name = expr.value
            if not _ENTRY_NAME_RE.match(var_name):
                raise self._syn(line, "Entry variable name must be a valid identifier")
            attrs = self._parse_attrs(attrs_text, line) if attrs_text else {}
            return ast.EntryStmt(line=line.no, name=var_name, attrs=attrs)

        # GUI: Text "name" [attrs]
        if txt.startswith("Text "):
            rest = txt[len("Text ") :].strip()
            if not rest:
                raise self._syn(line, "missing variable name for 'Text'")
            head, attrs_text = self._split_head_and_attrs(rest)
            expr = self._parse_expr_text(head, line_no=line.no)
            if not isinstance(expr, ast.Literal) or not isinstance(expr.value, str):
                raise self._syn(line, "Text expects a string literal variable name")
            var_name = expr.value
            if not _ENTRY_NAME_RE.match(var_name):
                raise self._syn(line, "Text variable name must be a valid identifier")
            attrs = self._parse_attrs(attrs_text, line) if attrs_text else {}
            return ast.TextStmt(line=line.no, name=var_name, attrs=attrs)

        # GUI: Image "filename" [attrs]
        if txt.startswith("Image "):
            rest = txt[len("Image ") :].strip()
            if not rest:
                raise self._syn(line, "missing path for 'Image'")
            head, attrs_text = self._split_head_and_attrs(rest)
            path_expr = self._parse_expr_text(head, line_no=line.no)
            attrs = self._parse_attrs(attrs_text, line) if attrs_text else {}
            return ast.ImageStmt(line=line.no, path=path_expr, attrs=attrs)

        # global import: let(x)
        m = _IMPORT_RE.match(txt)
        if m:
            return ast.GlobalImport(line=line.no, name=m.group(1))

        # global let: let x = expr
        m = _GLET_RE.match(txt)
        if m:
            name = m.group(1)
            expr_text = m.group(2)
            expr = self._parse_expr_text(expr_text, line_no=line.no)
            return ast.GlobalLet(line=line.no, name=name, expr=expr)

        # local assign: x = expr (only in blocks)
        toks = lex_expr(txt, filename=self.filename, line=line.no)
        if toks and toks[0].kind == "IDENT" and toks[1].kind == "ASSIGN":
            if not in_block:
                raise self._syn(line, "top-level assignment must use 'let x = ...' (locals only exist in blocks)")
            name = toks[0].text
            rhs = toks[2:]  # includes EOF
            expr = self._parse_expr_tokens(rhs)
            return ast.LocalAssign(line=line.no, name=name, expr=expr)

        # expression statement (calls, etc.)
        expr = self._parse_expr_tokens(toks)
        return ast.ExprStmt(line=line.no, expr=expr)

