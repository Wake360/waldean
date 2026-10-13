"""Name-level def-use analysis over notebook code cells (libcst).

Deliberately not a full abstract interpretation: bindings follow document
order (the notebook's v1 linear-execution assumption) with kill-on-reassign,
which is what the 2026-07-04 dogfood review showed real notebooks need.
Known blind spots, accepted for v1: conditional rebinds (`if demo: X = ...`)
kill the chain like unconditional ones, and code inside function bodies is
not modeled as notebook-level bindings.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import cast

import libcst as cst
from libcst.metadata import CodeRange, MetadataWrapper, PositionProvider

from .ingest import ParsedNotebook

# a magic/shell line is %name, %%name or !cmd — never "% b)" (formatting
# continuation) or "!= x"
_MAGIC_RE = re.compile(r"^(%%?[A-Za-z]|!\s*[A-Za-z./~])")

# line magics that wrap a statement: the payload is real code and must stay
# visible to dataflow (`%time X = fit(...)` must not vanish). Payloads that
# start with an option flag or another magic are not plain Python: fall back
# to the pass replacement.
_WRAPPER_MAGIC_RE = re.compile(r"^%%?(?:time|timeit|prun)\s+(?![-%!])(.+)$")

# cell magics whose body is not Python; anything else that fails to parse
# is a real parse error and must be recorded
# cst.parse_module + MetadataWrapper are superlinear; a single pathological
# cell (e.g. a 10MB generated paste) can dominate runtime. Skip cells past
# this size — far above any real analysis cell — so one cell cannot hang a run.
MAX_CELL_SOURCE_BYTES = 200_000

# cst.parse_module recurses natively per level of expression nesting, and a deep
# enough tree overflows the native stack (an uncatchable SIGSEGV) before any
# Python-level guard can fire. Nesting is driven not only by bracket/paren/brace
# depth but by attribute chains (a.b.c), subscript/call chains (a[0][0], f()()),
# and operators — all of which _structural_depth counts. A cell above this bound
# is skipped before parse_module ever sees it. 500 is far above any real notebook
# (dense method chains run well under 100) and far below the native crash point.
MAX_CELL_NEST_DEPTH = 500

MUTATING_METHODS = {"append", "extend", "update", "insert", "setdefault", "add"}

_NON_PYTHON_CELL_MAGICS = {
    "%%writefile", "%%file", "%%bash", "%%sh", "%%script", "%%cmd",
    "%%html", "%%javascript", "%%js", "%%latex", "%%markdown", "%%svg",
    "%%perl", "%%ruby",
}


def expr_names(node: cst.CSTNode) -> set[str]:
    """Variable names an expression reads. Attribute chains contribute only
    their base name (df.status -> df); attr parts are not variables."""
    names: set[str] = set()

    def walk(n: cst.CSTNode) -> None:
        if isinstance(n, cst.Name):
            names.add(n.value)
        elif isinstance(n, cst.Attribute):
            walk(n.value)
        elif isinstance(n, cst.Call):
            walk(n.func)
            for arg in n.args:
                walk(arg.value)
        else:
            for child in n.children:
                walk(child)

    walk(node)
    return names


def _subscript_key(node: cst.Subscript) -> str:
    """A stable label for a subscript: literal keys keep their value so
    models['clf'] and models['scaler'] stay distinct receivers; dynamic
    keys become '?' (consumers treat those as unresolvable)."""
    if len(node.slice) == 1 and isinstance(node.slice[0].slice, cst.Index):
        v = node.slice[0].slice.value
        if isinstance(v, (cst.SimpleString, cst.Integer)):
            return v.value
    return "?"


def _dotted(node: cst.BaseExpression) -> str | None:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr.value}" if base else None
    if isinstance(node, cst.Subscript):
        base = _dotted(node.value)
        return f"{base}[{_subscript_key(node)}]" if base else None
    if isinstance(node, cst.Call):
        # constructor-chained receiver: StandardScaler().fit_transform(X)
        # must still yield a CallSite (receiver "StandardScaler()")
        base = _dotted(node.func)
        return f"{base}()" if base else None
    return None


@dataclass
class CallSite:
    func: str  # dotted, e.g. "scaler.fit_transform" or "train_test_split"
    name: str  # final segment, e.g. "fit_transform"
    receiver: str | None  # "scaler" for scaler.fit_transform, None for bare calls
    cell: int
    line: int  # 1-based within the cell
    loop_depth: int
    pos_args: list[set[str]] = field(default_factory=list)  # names per positional arg
    kw_args: dict[str, set[str]] = field(default_factory=dict)  # names per keyword arg
    loop_vars: set[str] = field(default_factory=set)  # targets of enclosing for-loops
    end_line: int = 0

    @property
    def arg_names(self) -> set[str]:
        return set().union(set(), *self.pos_args, *self.kw_args.values())

    @property
    def receiver_base(self) -> str | None:
        """Plain variable underneath the receiver: data['a'] -> data."""
        if self.receiver is None:
            return None
        return self.receiver.split("[", 1)[0].split(".", 1)[0]


@dataclass
class AssignEvent:
    targets: set[str]
    sources: set[str]
    cell: int
    line: int
    call: CallSite | None = None  # the exact CallSite object when the value is a call
    end_line: int = 0
    col: int = 0
    ordered_targets: list[str] = field(default_factory=list)


@dataclass
class SliceEvent:
    base: str
    cell: int
    line: int
    lower: str
    upper: str


@dataclass
class FuncDef:
    name: str
    params: list[str]
    calls: list[CallSite] = field(default_factory=list)
    assigns: list[AssignEvent] = field(default_factory=list)


class _CellVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, cell_index: int):
        self.cell = cell_index
        self.loop_depth = 0
        self.scope_depth = 0  # inside def/lambda/class: not notebook-level bindings
        self.calls: list[CallSite] = []
        self.assigns: list[AssignEvent] = []
        self.mutations: list[AssignEvent] = []
        self.slices: list[SliceEvent] = []
        self.functions: list[FuncDef] = []
        self._func: FuncDef | None = None
        self._lambda: FuncDef | None = None
        self._pipe_lambdas: set[int] = set()
        self._pending: dict[int, AssignEvent] = {}  # id(call node) -> its assign event
        self._loop_vars: list[set[str]] = []  # target names per enclosing for-loop

    def _line(self, node: cst.CSTNode) -> int:
        return cast(CodeRange, self.get_metadata(PositionProvider, node)).start.line

    def _end_line(self, node: cst.CSTNode) -> int:
        return cast(CodeRange, self.get_metadata(PositionProvider, node)).end.line

    def visit_For(self, node: cst.For) -> None:
        self.loop_depth += 1
        self._loop_vars.append(_target_names(node.target))

    def leave_For(self, original_node: cst.For) -> None:
        self.loop_depth -= 1
        self._loop_vars.pop()

    def visit_While(self, node: cst.While) -> None:
        self.loop_depth += 1

    def leave_While(self, original_node: cst.While) -> None:
        self.loop_depth -= 1

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.scope_depth += 1
        if self.scope_depth == 1:
            params = [p.name.value for p in node.params.params]
            self._func = FuncDef(name=node.name.value, params=params)
            self.functions.append(self._func)

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        self.scope_depth -= 1
        if self.scope_depth == 0:
            self._func = None

    def visit_Lambda(self, node: cst.Lambda) -> None:
        self.scope_depth += 1
        if self.scope_depth == 1 and self._func is None and id(node) in self._pipe_lambdas:
            params = [p.name.value for p in node.params.params]
            self._func = self._lambda = FuncDef(name=self._lambda_name(node), params=params)
            self.functions.append(self._func)

    def leave_Lambda(self, original_node: cst.Lambda) -> None:
        self.scope_depth -= 1
        if self.scope_depth == 0 and self._lambda is not None and self._lambda is self._func:
            self._lambda = self._func = None

    def _lambda_name(self, node: cst.Lambda) -> str:
        return f"<lambda@{self._line(node)}:{cast(CodeRange, self.get_metadata(PositionProvider, node)).start.column}>"

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.scope_depth += 1

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self.scope_depth -= 1

    def _call_site(self, node: cst.Call, line: int) -> CallSite | None:
        dotted = _dotted(node.func)
        if dotted is None:
            return None
        receiver = None
        if isinstance(node.func, (cst.Attribute, cst.Subscript)):
            receiver = _dotted(node.func.value)
        pos_args: list[set[str]] = []
        kw_args: dict[str, set[str]] = {}
        for position, arg in enumerate(node.args):
            names = expr_names(arg.value)
            if position == 0 and dotted.endswith(".pipe") and isinstance(arg.value, cst.Lambda):
                self._pipe_lambdas.add(id(arg.value))
                names = {self._lambda_name(arg.value)}
            if arg.keyword is not None:
                kw_args[arg.keyword.value] = names
            else:
                pos_args.append(names)
        return CallSite(
            func=dotted,
            name=dotted.rsplit(".", 1)[-1].split("[", 1)[0],
            receiver=receiver,
            cell=self.cell,
            line=line,
            loop_depth=self.loop_depth,
            pos_args=pos_args,
            kw_args=kw_args,
            loop_vars=set().union(set(), *self._loop_vars),
            end_line=self._end_line(node),
        )

    def visit_Call(self, node: cst.Call) -> None:
        site = self._call_site(node, self._line(node))
        if site is None:
            return
        if self._func is None:
            self.calls.append(site)
        elif self.scope_depth == 1:
            self._func.calls.append(site)
        base = site.receiver_base
        if site.name in MUTATING_METHODS and base is not None and base == site.receiver and self.scope_depth == 0:
            self.mutations.append(AssignEvent(
                targets={base}, sources=site.arg_names | {base},
                cell=self.cell, line=site.line, end_line=site.end_line,
                col=cast(CodeRange, self.get_metadata(PositionProvider, node)).start.column,
            ))
        ev = self._pending.pop(id(node), None)
        if ev is not None:
            ev.call = site  # identity-shared: detect can test `ev.call is call`

    def _record_assign(self, targets: set[str], value: cst.BaseExpression, node: cst.CSTNode,
                       extra_sources: Collection[str] = frozenset(),
                       ordered: list[str] | None = None) -> None:
        if self.scope_depth > 0:
            if self._func is not None and self.scope_depth == 1:
                self._func.assigns.append(AssignEvent(
                    targets=targets, sources=expr_names(value) | set(extra_sources),
                    cell=self.cell, line=self._line(node), end_line=self._end_line(node),
                    col=cast(CodeRange, self.get_metadata(PositionProvider, node)).start.column,
                    ordered_targets=ordered or [],
                ))
            return  # function/class locals do not rebind notebook names
        ev = AssignEvent(
            targets=targets,
            sources=expr_names(value) | set(extra_sources),
            cell=self.cell,
            line=self._line(node),
            end_line=self._end_line(node),
            col=cast(CodeRange, self.get_metadata(PositionProvider, node)).start.column,
            ordered_targets=ordered or [],
        )
        self.assigns.append(ev)
        if isinstance(value, cst.Call):
            self._pending[id(value)] = ev

    def visit_Assign(self, node: cst.Assign) -> None:
        targets: set[str] = set()
        mutated: set[str] = set()  # df["x"] = ... mutates df: keep df's history
        ordered: list[str] = []
        for t in node.targets:
            if isinstance(t.target, (cst.Subscript, cst.Attribute)):
                mutated |= _target_names(t.target)
            targets |= _target_names(t.target)
            if isinstance(t.target, (cst.Tuple, cst.List)):
                ordered = [el.value.value for el in t.target.elements if isinstance(el.value, cst.Name)]
        self._record_assign(targets, node.value, node, extra_sources=mutated, ordered=ordered)
        self._record_slices(node.value)

    def _record_slices(self, value: cst.BaseExpression) -> None:
        if self.scope_depth > 0:
            return
        exprs = [el.value for el in value.elements] if isinstance(value, cst.Tuple) else [value]
        code = cst.Module(body=[]).code_for_node
        for expr in exprs:
            if not isinstance(expr, cst.Subscript) or len(expr.slice) != 1:
                continue
            sl = expr.slice[0].slice
            if not isinstance(sl, cst.Slice):
                continue
            head = expr.value
            if isinstance(head, cst.Attribute) and head.attr.value == "iloc":
                head = head.value
            if not isinstance(head, cst.Name):
                continue
            self.slices.append(SliceEvent(
                base=head.value, cell=self.cell, line=self._line(expr),
                lower=code(sl.lower) if sl.lower is not None else "",
                upper=code(sl.upper) if sl.upper is not None else "",
            ))

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if node.value is not None:
            self._record_assign(_target_names(node.target), node.value, node)

    def visit_AugAssign(self, node: cst.AugAssign) -> None:
        targets = _target_names(node.target)
        self._record_assign(targets, node.value, node, extra_sources=targets)


def _target_names(node: cst.BaseExpression) -> set[str]:
    if isinstance(node, cst.Name):
        return {node.value}
    if isinstance(node, (cst.Tuple, cst.List)):
        names: set[str] = set()
        for el in node.elements:
            names |= _target_names(el.value)
        return names
    if isinstance(node, (cst.Subscript, cst.Attribute)):
        # df["x"] = ... mutates df; treat df as (re)assigned
        return _target_names(node.value)
    return set()


def _strip_magics(source: str) -> str:
    lines = []
    for line in source.splitlines():
        stripped = line.lstrip()
        if _MAGIC_RE.match(stripped):
            indent = line[: len(line) - len(stripped)]
            wrapper = _WRAPPER_MAGIC_RE.match(stripped)
            if wrapper:
                lines.append(indent + wrapper.group(1))
            else:
                lines.append(indent + "pass  # magic stripped")
        else:
            lines.append(line)
    return "\n".join(lines)


@dataclass
class NotebookDataflow:
    calls: list[CallSite] = field(default_factory=list)
    assigns: list[AssignEvent] = field(default_factory=list)
    mutations: list[AssignEvent] = field(default_factory=list)  # x.append(v)-style in-place updates
    slices: list[SliceEvent] = field(default_factory=list)
    functions: dict[str, FuncDef] = field(default_factory=dict)
    parse_errors: list[int] = field(default_factory=list)  # cell indices that failed to parse
    skipped_cells: list[int] = field(default_factory=list)  # cell indices skipped by a size/depth cap
    _by_name: dict[str, list[AssignEvent]] | None = field(default=None, repr=False)
    _by_name_mut: dict[str, list[AssignEvent]] | None = field(default=None, repr=False)

    def slice_splits(self) -> list[CallSite]:
        sinks: list[CallSite] = []
        by_base: dict[str, list[SliceEvent]] = {}
        for s in self.slices:
            by_base.setdefault(s.base, []).append(s)
        for base, events in by_base.items():
            heads = [e for e in events if e.upper and not e.lower]
            tails = [e for e in events if e.lower and not e.upper]
            pairs = [(h, t) for h in heads for t in tails if h.upper == t.lower]
            if not pairs:
                continue
            last = max(pairs[0], key=lambda e: (e.cell, e.line))
            sinks.append(CallSite(func="slice_split", name="slice_split", receiver=None,
                                  cell=last.cell, line=last.line, loop_depth=0, pos_args=[{base}]))
        return sinks

    def _index(self, mutations: bool) -> dict[str, list[AssignEvent]]:
        cached = self._by_name_mut if mutations else self._by_name
        if cached is not None:
            return cached
        index: dict[str, list[AssignEvent]] = {}
        events = self.assigns + self.mutations if mutations else self.assigns
        for ev in sorted(events, key=lambda e: (e.cell, e.line, e.col)) if mutations else events:
            for t in ev.targets:
                index.setdefault(t, []).append(ev)
        if mutations:
            self._by_name_mut = index
        else:
            self._by_name = index
        return index

    def last_assign(self, name: str, before: tuple[int, ...], mutations: bool = False) -> AssignEvent | None:
        """Latest assignment to `name` strictly before (cell, line), in
        document order — the notebook's v1 linear-execution assumption."""
        for ev in reversed(self._index(mutations).get(name, [])):
            if (ev.cell, ev.line, ev.col) < before:
                return ev
        return None

    def chain(self, names: set[str], at: tuple[int, ...],
              mutations: bool = False) -> tuple[list[AssignEvent], set[tuple[str, int | None]]]:
        """Flow-sensitive dependency chain: the assign events and
        (name, binding-event-id) pairs reachable from `names` as bound at
        position `at`. A name rebound between its producer and `at` kills
        the older chain — reusing `X` for a second dataset no longer links
        the two."""
        events: list[AssignEvent] = []
        bindings: set[tuple[str, int | None]] = set()
        frontier: list[tuple[str, tuple[int, ...]]] = [(n, at) for n in names]
        while frontier:
            n, pos = frontier.pop()
            ev = self.last_assign(n, pos, mutations)
            key = (n, id(ev) if ev is not None else None)
            if key in bindings:
                continue
            bindings.add(key)
            if ev is None:
                continue
            events.append(ev)
            for s in ev.sources:
                frontier.append((s, (ev.cell, ev.line, ev.col)))
        return events, bindings

    def binding(self, name: str, at: tuple[int, ...], mutations: bool = False) -> tuple[str, int | None]:
        ev = self.last_assign(name, at, mutations)
        return (name, id(ev) if ev is not None else None)


_DEPTH_OPERATOR_CHARS = frozenset("*/%@<>&|^~")


def _structural_depth(source: str) -> int:
    """A sound upper bound on the AST expression-nesting depth of ``source``.

    Every level libcst recurses through is introduced by at least one opening
    bracket, an attribute dot, or an operator. These are counted cumulatively
    within a statement: left-associative chains such as ``a[0][0][0]`` and
    ``a.b.c`` do not nest lexically (bracket depth stays flat) but do nest in the
    AST, so opens are never decremented — the running count only resets at a
    statement boundary (a newline or ``;`` outside brackets). A leading sign
    (``-1``, ``+1``) is excluded since it follows a non-operand character
    (start of expression, another operator, an open bracket, a comma); binary
    ``+``/``-`` between operands always counts, even bare digit-to-digit
    (``1+1``) — checking what precedes rather than what follows, since a chain
    like ``1+1+1+...`` has a digit on both sides of every operator either way.
    Over-approximate by design: a flagged cell is skipped, never parsed.
    """
    peak = 0
    run = 0
    bracket = 0
    prev = ""
    for i, ch in enumerate(source):
        drive = False
        if ch in "([{":
            bracket += 1
            drive = True
        elif ch in ")]}":
            if bracket > 0:
                bracket -= 1
        elif ch == ".":
            drive = not prev.isdigit()  # attribute access, not a float point
        elif ch in _DEPTH_OPERATOR_CHARS:
            drive = True
        elif ch in "+-":
            drive = prev.isalnum() or prev in ")]}\"'_"
        elif ch in "\n;" and bracket == 0:
            run = 0
        if drive:
            run += 1
            if run > peak:
                peak = run
        if not ch.isspace():
            prev = ch
    return peak


def _rename_names(names: set[str], rename: dict[str, set[str]]) -> set[str]:
    out: set[str] = set()
    for n in names:
        out |= rename.get(n, {n})
    return out


def _rename_dotted(text: str | None, rename: dict[str, set[str]]) -> str | None:
    if text is None:
        return None
    head, sep, rest = text.partition(".")
    head, bracket, idx = head.partition("[")
    target = rename.get(head)
    if not target or len(target) != 1:
        return text
    return next(iter(target)) + bracket + idx + sep + rest


def _rename_call(c: CallSite, rename: dict[str, set[str]], site: CallSite) -> CallSite:
    return CallSite(
        func=_rename_dotted(c.func, rename) or c.func,
        name=c.name,
        receiver=_rename_dotted(c.receiver, rename),
        cell=site.cell, line=site.line, loop_depth=site.loop_depth,
        pos_args=[_rename_names(a, rename) for a in c.pos_args],
        kw_args={k: _rename_names(v, rename) for k, v in c.kw_args.items()},
        loop_vars=set(site.loop_vars), end_line=site.end_line,
    )


def _call_target(site: CallSite, functions: dict[str, FuncDef]) -> tuple[FuncDef | None, list[set[str]]]:
    if site.receiver is None and site.name in functions:
        return functions[site.name], site.pos_args
    if site.name == "pipe" and site.receiver is not None and site.pos_args:
        if len(site.pos_args[0]) == 1 and site.receiver_base:
            fname = next(iter(site.pos_args[0]))
            if fname in functions:
                return functions[fname], [{site.receiver_base}] + site.pos_args[1:]
    return None, []


def analyze(nb: ParsedNotebook) -> NotebookDataflow:
    flow = NotebookDataflow()
    for cell in nb.code_cells:
        if len(cell.source) > MAX_CELL_SOURCE_BYTES:
            flow.skipped_cells.append(cell.index)  # surfaced as a partial-results warning
            continue  # oversized cell: skip to keep runtime bounded
        if _structural_depth(cell.source) > MAX_CELL_NEST_DEPTH:
            flow.skipped_cells.append(cell.index)
            continue  # deep nesting overflows the native parser stack: skip
        # valid Python first: a leading "%" can be a formatting continuation
        # line, not a magic, and stripping it would break the parse
        try:
            try:
                module = cst.parse_module(cell.source)
            except cst.ParserSyntaxError:
                try:
                    module = cst.parse_module(_strip_magics(cell.source))
                except cst.ParserSyntaxError:
                    first_word = cell.source.lstrip().split(None, 1)[0] if cell.source.strip() else ""
                    if first_word in _NON_PYTHON_CELL_MAGICS:
                        continue  # body is not Python by design; not an error
                    flow.parse_errors.append(cell.index)
                    continue
            wrapper = MetadataWrapper(module)
            visitor = _CellVisitor(cell.index)
            wrapper.visit(visitor)
        except RecursionError:
            continue  # deep expression tree exhausts the recursion limit: skip
        flow.calls.extend(visitor.calls)
        flow.assigns.extend(visitor.assigns)
        flow.mutations.extend(visitor.mutations)
        flow.slices.extend(visitor.slices)
        flow.functions.update({f.name: f for f in visitor.functions})
    for site in list(flow.calls):
        fn, args = _call_target(site, flow.functions)
        if fn is None:
            continue
        rename = {p: a for p, a in zip(fn.params, args) if a}
        for c in fn.calls:
            flow.calls.append(_rename_call(c, rename, site))
        for ev in fn.assigns:
            flow.assigns.append(AssignEvent(
                targets=_rename_names(ev.targets, rename), sources=_rename_names(ev.sources, rename),
                cell=site.cell, line=site.line, end_line=site.end_line or site.line, col=0,
            ))
    flow.assigns.sort(key=lambda e: (e.cell, e.line, e.col))
    return flow
