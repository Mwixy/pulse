from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:  # Tkinter is optional; non-GUI programs should still run
    import tkinter as tk  # type: ignore[import]
except Exception:  # pragma: no cover
    tk = None  # type: ignore[assignment]

from . import ast
from .errors import PulseRuntimeError
from .parser import parse_source
from .pyinterop import _PyRoot


@dataclass
class _Frame:
    locals: dict[str, Any] = field(default_factory=dict)


class _FunctionValue:
    def __init__(self, rt: "PulseRuntime", name: str):
        self._rt = rt
        self._name = name

    def __call__(self, *args: Any) -> Any:
        return self._rt._call_user_function(self._name, list(args))

    def __repr__(self) -> str:
        return f"<func {self._name}>"


class PulseRuntime:
    def __init__(self) -> None:
        self.globals: dict[str, Any] = {}
        self.funcs: dict[str, ast.FuncDef] = {}
        self.filename = "<unknown>"

        # GUI state (for Tkinter integration)
        self._tk_root: Any | None = None
        self._tk_entries: dict[str, Any] = {}
        self._tk_text_vars: dict[str, Any] = {}
        self._tk_images: list[Any] = []
        # variable -> list of UI update callbacks (value -> None)
        self._tk_var_bindings: dict[str, list[Callable[[Any], None]]] = {}

        # Python interop root (for py.<module> access)
        self._py_root = _PyRoot()

        self.builtins: dict[str, Callable[..., Any]] = {
            "print": self._builtin_print,
            "sleep": self._builtin_sleep,
            "time": self._builtin_time,
        }

    def run(self, source: str, *, filename: str = "<memory>") -> None:
        self.filename = filename
        program = parse_source(source, filename=filename)
        self._exec_block(program.body, frame=None)

    # ----------- builtins -----------

    def _builtin_print(self, *args: Any) -> None:
        print(*args)

    def _builtin_sleep(self, seconds: Any) -> None:
        try:
            s = float(seconds)
        except Exception as e:  # noqa: BLE001
            raise PulseRuntimeError(f"sleep(seconds): expected number, got {seconds!r}", filename=self.filename, line=1) from e
        time.sleep(s)

    def _builtin_time(self) -> float:
        return time.time()

    # ----------- execution -----------

    def _exec_block(self, body: list[ast.StmtT], *, frame: _Frame | None) -> None:
        for stmt in body:
            self._exec_stmt(stmt, frame=frame)

    def _exec_stmt(self, stmt: ast.StmtT, *, frame: _Frame | None) -> None:
        if isinstance(stmt, ast.GlobalLet):
            val = self._eval(stmt.expr, frame=frame)
            self.globals[stmt.name] = val
            return

        if isinstance(stmt, ast.GlobalImport):
            if frame is None:
                raise PulseRuntimeError("let(x) is only valid inside a block", filename=self.filename, line=stmt.line)
            if stmt.name not in self.globals:
                raise PulseRuntimeError(f"global '{stmt.name}' is not defined", filename=self.filename, line=stmt.line)
            frame.locals[stmt.name] = self.globals[stmt.name]
            return

        if isinstance(stmt, ast.LocalAssign):
            if frame is None:
                raise PulseRuntimeError("top-level assignment must use 'let x = ...'", filename=self.filename, line=stmt.line)
            val = self._eval(stmt.expr, frame=frame)
            frame.locals[stmt.name] = val
            return

        if isinstance(stmt, ast.ExprStmt):
            self._eval(stmt.expr, frame=frame)
            return

        if isinstance(stmt, ast.FuncDef):
            self.funcs[stmt.name] = stmt
            return

        # ----- GUI: window / widgets -----

        if isinstance(stmt, ast.WindowBlock):
            if tk is None:
                raise PulseRuntimeError("Tkinter is not available on this system", filename=self.filename, line=stmt.line)
            if self._tk_root is not None:
                raise PulseRuntimeError("nested windows are not supported", filename=self.filename, line=stmt.line)

            title_val = self._eval(stmt.title, frame=frame)
            # evaluate window attributes
            win_opts = {name: self._eval(expr, frame=frame) for name, expr in stmt.attrs.items()}

            root = tk.Tk()
            root.title(str(title_val))
            # geometry: width / height
            width = win_opts.pop("width", None)
            height = win_opts.pop("height", None)
            if width is not None or height is not None:
                try:
                    w = int(width) if width is not None else root.winfo_width() or 400
                    h = int(height) if height is not None else root.winfo_height() or 300
                    root.geometry(f"{w}x{h}")
                except Exception:
                    pass
            # background color
            bg = win_opts.pop("bg", None) or win_opts.pop("background", None)
            if bg is not None:
                try:
                    root.configure(bg=bg)
                except Exception:
                    pass

            self._tk_root = root
            self._tk_entries = {}
            self._tk_text_vars = {}
            self._tk_images = []
            self._tk_var_bindings = {}
            try:
                self._exec_block(stmt.body, frame=_Frame())
                root.mainloop()
            finally:
                self._tk_root = None
                self._tk_entries = {}
                self._tk_text_vars = {}
                self._tk_images = []
                self._tk_var_bindings = {}
            return

        if isinstance(stmt, ast.LabelStmt):
            if self._tk_root is None or tk is None:
                raise PulseRuntimeError("Label must be inside a window block", filename=self.filename, line=stmt.line)
            text_val = self._eval(stmt.text, frame=frame)
            opts = {name: self._eval(expr, frame=frame) for name, expr in stmt.attrs.items()}
            widget_opts, pack_opts = self._split_widget_and_pack_options(opts)
            # map color alias
            color = widget_opts.pop("color", None)
            if color is not None:
                widget_opts.setdefault("fg", color)
            lbl = tk.Label(self._tk_root, text=str(text_val), **widget_opts)
            lbl.pack(**pack_opts)
            # bind label text to variable if expression is a simple Var
            if isinstance(stmt.text, ast.Var):
                var_name = stmt.text.name

                def _update_label(val: Any, widget: Any = lbl) -> None:  # noqa: ANN401
                    try:
                        widget.configure(text=str(val))
                    except Exception:
                        pass

                self._register_var_binding(var_name, _update_label)
                if var_name in self.globals:
                    _update_label(self.globals[var_name])
            return

        if isinstance(stmt, ast.EntryStmt):
            if self._tk_root is None or tk is None:
                raise PulseRuntimeError("Entry must be inside a window block", filename=self.filename, line=stmt.line)
            opts = {name: self._eval(expr, frame=frame) for name, expr in stmt.attrs.items()}
            widget_opts, pack_opts = self._split_widget_and_pack_options(opts)
            color = widget_opts.pop("color", None)
            if color is not None:
                widget_opts.setdefault("fg", color)
            sv = tk.StringVar()

            def _on_change(*_: Any) -> None:
                self.globals[stmt.name] = sv.get()

            sv.trace_add("write", _on_change)
            ent = tk.Entry(self._tk_root, textvariable=sv, **widget_opts)
            ent.pack(**pack_opts)
            self._tk_entries[stmt.name] = sv
            # allow update(var) to push current global value into entry
            def _update_entry(val: Any, var=sv) -> None:  # noqa: ANN401
                try:
                    var.set(str(val))
                except Exception:
                    pass

            self._register_var_binding(stmt.name, _update_entry)
            return

        if isinstance(stmt, ast.ButtonBlock):
            if self._tk_root is None or tk is None:
                raise PulseRuntimeError("Button must be inside a window block", filename=self.filename, line=stmt.line)

            text_val = self._eval(stmt.text, frame=frame)
            opts = {name: self._eval(expr, frame=frame) for name, expr in stmt.attrs.items()}
            widget_opts, pack_opts = self._split_widget_and_pack_options(opts)
            # legacy aliases
            color = widget_opts.pop("color", None)
            if color is not None:
                widget_opts.setdefault("fg", color)

            def _on_click() -> None:
                try:
                    if stmt.func_name is not None:
                        self._call_user_function(stmt.func_name, [])
                    if stmt.body:
                        self._exec_block(stmt.body, frame=_Frame())
                except PulseRuntimeError as e:
                    print(e)

            btn = tk.Button(self._tk_root, text=str(text_val), command=_on_click, **widget_opts)
            btn.pack(**pack_opts)
            return

        if isinstance(stmt, ast.TextStmt):
            if self._tk_root is None or tk is None:
                raise PulseRuntimeError("Text must be inside a window block", filename=self.filename, line=stmt.line)
            opts = {name: self._eval(expr, frame=frame) for name, expr in stmt.attrs.items()}
            widget_opts, pack_opts = self._split_widget_and_pack_options(opts)
            color = widget_opts.pop("color", None)
            if color is not None:
                widget_opts.setdefault("fg", color)
            txt = tk.Text(self._tk_root, **widget_opts)
            txt.pack(**pack_opts)
            self.globals[stmt.name] = ""

            def _on_change(event: Any, name: str = stmt.name, widget: Any = txt) -> None:  # noqa: ANN401
                try:
                    self.globals[name] = widget.get("1.0", "end-1c")
                except Exception:
                    pass

            txt.bind("<KeyRelease>", _on_change)
            self._tk_text_vars[stmt.name] = txt

            def _update_text(val: Any, widget: Any = txt) -> None:  # noqa: ANN401
                try:
                    widget.delete("1.0", "end")
                    widget.insert("1.0", str(val))
                except Exception:
                    pass

            self._register_var_binding(stmt.name, _update_text)
            return

        if isinstance(stmt, ast.ImageStmt):
            if self._tk_root is None or tk is None:
                raise PulseRuntimeError("Image must be inside a window block", filename=self.filename, line=stmt.line)
            path_val = self._eval(stmt.path, frame=frame)
            opts = {name: self._eval(expr, frame=frame) for name, expr in stmt.attrs.items()}
            widget_opts, pack_opts = self._split_widget_and_pack_options(opts)
            color = widget_opts.pop("color", None)
            if color is not None:
                widget_opts.setdefault("fg", color)
            width_opt = widget_opts.pop("width", None)
            height_opt = widget_opts.pop("height", None)
            try:
                raw_path = Path(str(path_val))
                if not raw_path.is_absolute():
                    base = Path(self.filename).parent
                    raw_path = base / raw_path
                img = tk.PhotoImage(file=str(raw_path))
                # naive resize using subsample if width/height provided
                if width_opt is not None or height_opt is not None:
                    try:
                        target_w = int(width_opt) if width_opt is not None else img.width()
                        target_h = int(height_opt) if height_opt is not None else img.height()
                        sx = max(img.width() // max(target_w, 1), 1)
                        sy = max(img.height() // max(target_h, 1), 1)
                        img = img.subsample(sx, sy)
                    except Exception:
                        pass
            except Exception as e:  # noqa: BLE001
                raise PulseRuntimeError(f"failed to load image: {str(raw_path)!r}", filename=self.filename, line=stmt.line) from e
            lbl = tk.Label(self._tk_root, image=img, **widget_opts)
            lbl.image = img  # keep reference
            self._tk_images.append(img)
            lbl.pack(**pack_opts)
            return

        if isinstance(stmt, ast.UpdateStmt):
            name = stmt.name
            if name not in self.globals:
                raise PulseRuntimeError(f"global '{name}' is not defined", filename=self.filename, line=stmt.line)
            val = self.globals[name]
            for fn in self._tk_var_bindings.get(name, []):
                try:
                    fn(val)
                except Exception:
                    pass
            return

        if isinstance(stmt, ast.IfBlock):
            cond = self._eval(stmt.cond, frame=frame)
            if not isinstance(cond, bool):
                raise PulseRuntimeError("if condition must be boolean", filename=self.filename, line=stmt.line)
            if cond:
                self._exec_block(stmt.body, frame=_Frame())
            return

        if isinstance(stmt, ast.WhileBlock):
            loop_frame = _Frame()
            while True:
                cond = self._eval(stmt.cond, frame=frame)
                if not isinstance(cond, bool):
                    raise PulseRuntimeError("while condition must be boolean", filename=self.filename, line=stmt.line)
                if not cond:
                    break
                self._exec_block(stmt.body, frame=loop_frame)
            return

        if isinstance(stmt, ast.UntilBlock):
            loop_frame = _Frame()
            while True:
                cond = self._eval(stmt.cond, frame=frame)
                if not isinstance(cond, bool):
                    raise PulseRuntimeError("until condition must be boolean", filename=self.filename, line=stmt.line)
                if cond:
                    break
                self._exec_block(stmt.body, frame=loop_frame)
            return

        if isinstance(stmt, ast.AfterBlock):
            secs = self._eval(stmt.seconds, frame=frame)
            # If we are inside a Tk window, use Tk's millisecond-based timer
            if self._tk_root is not None and tk is not None:
                try:
                    delay_ms = int(float(secs))
                except Exception as e:  # noqa: BLE001
                    raise PulseRuntimeError("after expects numeric milliseconds", filename=self.filename, line=stmt.line) from e

                def _cb() -> None:
                    self._exec_block(stmt.body, frame=_Frame())

                self._tk_root.after(delay_ms, _cb)
                return

            # Non-GUI: fall back to blocking sleep in seconds
            try:
                time.sleep(float(secs))
            except Exception as e:  # noqa: BLE001
                raise PulseRuntimeError("after expects numeric seconds", filename=self.filename, line=stmt.line) from e
            self._exec_block(stmt.body, frame=_Frame())
            return

        if isinstance(stmt, ast.EveryBlock):
            interval = self._eval(stmt.seconds, frame=frame)
            # GUI: recurring timer using Tk
            if self._tk_root is not None and tk is not None:
                try:
                    delay_ms = int(float(interval))
                except Exception as e:  # noqa: BLE001
                    raise PulseRuntimeError("every expects numeric milliseconds", filename=self.filename, line=stmt.line) from e

                def _tick() -> None:
                    self._exec_block(stmt.body, frame=_Frame())
                    self._tk_root.after(delay_ms, _tick)

                self._tk_root.after(delay_ms, _tick)
                return

            # Non-GUI: blocking loop in seconds
            try:
                s = float(interval)
            except Exception as e:  # noqa: BLE001
                raise PulseRuntimeError("every expects numeric seconds", filename=self.filename, line=stmt.line) from e
            while True:
                time.sleep(s)
                self._exec_block(stmt.body, frame=_Frame())

        raise PulseRuntimeError(f"unsupported statement: {type(stmt).__name__}", filename=self.filename, line=stmt.line)

    # ----------- evaluation -----------

    def _resolve_name(self, name: str, *, frame: _Frame | None, line: int) -> Any:
        if frame is None:
            if name == "py":
                return self._py_root
            if name in self.globals:
                return self.globals[name]
            if name in self.funcs:
                return _FunctionValue(self, name)
            if name in self.builtins:
                return self.builtins[name]
            raise PulseRuntimeError(f"'{name}' is not defined in global scope", filename=self.filename, line=line)

        if name in frame.locals:
            return frame.locals[name]
        if name == "py":
            return self._py_root
        if name in self.funcs:
            return _FunctionValue(self, name)
        if name in self.builtins:
            return self.builtins[name]
        raise PulseRuntimeError(
            f"'{name}' cannot be found in the local scope (use let({name}) to import a global)",
            filename=self.filename,
            line=line,
        )

    def _eval(self, expr: ast.Expr, *, frame: _Frame | None) -> Any:
        if isinstance(expr, ast.Literal):
            return expr.value
        if isinstance(expr, ast.Var):
            return self._resolve_name(expr.name, frame=frame, line=expr.line)
        if isinstance(expr, ast.GetAttr):
            obj = self._eval(expr.obj, frame=frame)
            try:
                return getattr(obj, expr.name)
            except AttributeError as e:  # noqa: BLE001
                raise PulseRuntimeError(f"object has no attribute {expr.name!r}", filename=self.filename, line=expr.line) from e
        if isinstance(expr, ast.Unary):
            v = self._eval(expr.expr, frame=frame)
            if expr.op == "-":
                return -v
            if expr.op == "not":
                if not isinstance(v, bool):
                    raise PulseRuntimeError("'not' expects boolean", filename=self.filename, line=expr.line)
                return not v
            raise PulseRuntimeError(f"unknown unary op {expr.op!r}", filename=self.filename, line=expr.line)
        if isinstance(expr, ast.Binary):
            if expr.op == "and":
                left = self._eval(expr.left, frame=frame)
                if not isinstance(left, bool):
                    raise PulseRuntimeError("'and' expects booleans", filename=self.filename, line=expr.line)
                if not left:
                    return False
                right = self._eval(expr.right, frame=frame)
                if not isinstance(right, bool):
                    raise PulseRuntimeError("'and' expects booleans", filename=self.filename, line=expr.line)
                return left and right
            if expr.op == "or":
                left = self._eval(expr.left, frame=frame)
                if not isinstance(left, bool):
                    raise PulseRuntimeError("'or' expects booleans", filename=self.filename, line=expr.line)
                if left:
                    return True
                right = self._eval(expr.right, frame=frame)
                if not isinstance(right, bool):
                    raise PulseRuntimeError("'or' expects booleans", filename=self.filename, line=expr.line)
                return left or right

            l = self._eval(expr.left, frame=frame)
            r = self._eval(expr.right, frame=frame)
            op = expr.op
            if op == "+":
                return l + r
            if op == "-":
                return l - r
            if op == "*":
                return l * r
            if op == "/":
                return l / r
            if op == "%":
                return l % r
            if op == "==":
                return l == r
            if op == "!=":
                return l != r
            if op == "<":
                return l < r
            if op == "<=":
                return l <= r
            if op == ">":
                return l > r
            if op == ">=":
                return l >= r
            raise PulseRuntimeError(f"unknown binary op {op!r}", filename=self.filename, line=expr.line)
        if isinstance(expr, ast.Call):
            callee = self._eval(expr.callee, frame=frame)
            args = [self._eval(a, frame=frame) for a in expr.args]
            if callable(callee):
                try:
                    return callee(*args)
                except PulseRuntimeError:
                    raise
                except Exception as e:  # noqa: BLE001
                    raise PulseRuntimeError(f"call failed: {e}", filename=self.filename, line=expr.line) from e
            raise PulseRuntimeError("attempted to call a non-callable value", filename=self.filename, line=expr.line)

        raise PulseRuntimeError(f"unsupported expression: {type(expr).__name__}", filename=self.filename, line=expr.line)

    def _split_widget_and_pack_options(self, options: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        pack_keys = {"padx", "pady", "side", "anchor", "fill", "expand"}
        widget_opts: dict[str, Any] = {}
        pack_opts: dict[str, Any] = {}
        for k, v in options.items():
            if k in pack_keys:
                pack_opts[k] = v
            else:
                widget_opts[k] = v
        return widget_opts, pack_opts

    def _register_var_binding(self, name: str, fn: Callable[[Any], None]) -> None:
        self._tk_var_bindings.setdefault(name, []).append(fn)

    def _call_user_function(self, name: str, args: list[Any]) -> Any:
        fn = self.funcs.get(name)
        if fn is None:
            raise PulseRuntimeError(f"function '{name}' is not defined", filename=self.filename, line=1)
        if args:
            raise PulseRuntimeError(f"function '{name}' takes no arguments", filename=self.filename, line=fn.line)
        self._exec_block(fn.body, frame=_Frame())
        return None

