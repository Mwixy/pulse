from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal as TypingLiteral


@dataclass(frozen=True)
class Node:
    line: int


# ---------- Statements ----------


@dataclass(frozen=True)
class Program(Node):
    body: list["Stmt"]


class Stmt(Node):
    pass


@dataclass(frozen=True)
class GlobalLet(Stmt):
    name: str
    expr: "Expr"


@dataclass(frozen=True)
class GlobalImport(Stmt):
    name: str


@dataclass(frozen=True)
class LocalAssign(Stmt):
    name: str
    expr: "Expr"


@dataclass(frozen=True)
class ExprStmt(Stmt):
    expr: "Expr"


@dataclass(frozen=True)
class FuncDef(Stmt):
    name: str
    body: list[Stmt]


@dataclass(frozen=True)
class IfBlock(Stmt):
    cond: "Expr"
    body: list[Stmt]


@dataclass(frozen=True)
class WhileBlock(Stmt):
    cond: "Expr"
    body: list[Stmt]


@dataclass(frozen=True)
class UntilBlock(Stmt):
    cond: "Expr"
    body: list[Stmt]


@dataclass(frozen=True)
class AfterBlock(Stmt):
    seconds: "Expr"
    body: list[Stmt]


@dataclass(frozen=True)
class EveryBlock(Stmt):
    seconds: "Expr"
    body: list[Stmt]


@dataclass(frozen=True)
class WindowBlock(Stmt):
    title: "Expr"
    attrs: dict[str, "Expr"]
    body: list[Stmt]


@dataclass(frozen=True)
class LabelStmt(Stmt):
    text: "Expr"
    attrs: dict[str, "Expr"]


@dataclass(frozen=True)
class EntryStmt(Stmt):
    name: str
    attrs: dict[str, "Expr"]


@dataclass(frozen=True)
class ButtonBlock(Stmt):
    text: "Expr"
    func_name: str | None
    attrs: dict[str, "Expr"]
    body: list[Stmt]


@dataclass(frozen=True)
class TextStmt(Stmt):
    name: str
    attrs: dict[str, "Expr"]


@dataclass(frozen=True)
class ImageStmt(Stmt):
    path: "Expr"
    attrs: dict[str, "Expr"]


@dataclass(frozen=True)
class UpdateStmt(Stmt):
    name: str


StmtT = (
    GlobalLet
    | GlobalImport
    | LocalAssign
    | ExprStmt
    | FuncDef
    | IfBlock
    | WhileBlock
    | UntilBlock
    | AfterBlock
    | EveryBlock
    | WindowBlock
    | LabelStmt
    | EntryStmt
    | ButtonBlock
    | TextStmt
    | ImageStmt
    | UpdateStmt
)


# ---------- Expressions ----------


class Expr(Node):
    pass


@dataclass(frozen=True)
class Literal(Expr):
    value: Any


@dataclass(frozen=True)
class Var(Expr):
    name: str


BinaryOp = TypingLiteral["+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "and", "or"]


@dataclass(frozen=True)
class Binary(Expr):
    op: BinaryOp
    left: Expr
    right: Expr


UnaryOp = TypingLiteral["-", "not"]


@dataclass(frozen=True)
class Unary(Expr):
    op: UnaryOp
    expr: Expr


@dataclass(frozen=True)
class Call(Expr):
    callee: Expr
    args: list[Expr]


@dataclass(frozen=True)
class GetAttr(Expr):
    obj: Expr
    name: str

