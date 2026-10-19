"""Read flowcharts on a board as algorithms.

Boards explain simple algorithms with flowcharts: an ellipse to start and end, trapezoids for
input and output, rectangles for steps, diamonds for decisions, empty circles where branches
meet again. This module follows the arrows from each start and writes the chart as structured
pseudocode (sequence, IF/ELSE, REPEAT, calls), so a recap can explain what the algorithm does
instead of listing labels.

Conventions that come from how the boards were drawn:
- shapes boxed together (inside a larger rectangle) or touching each other form one unit;
- a box an arrow goes into and comes back out of is a call (e.g. one recursive call);
- the branch of a decision that leads back to it is a loop body, the other branch the exit,
  whether or not the arrows are labelled;
- a chart's title is the text right above its start or right below its end;
- faded shapes are context, not the focus.
"""

import re
from collections import deque
from dataclasses import dataclass, field

from app.scene import ConnectorElement, GeoElement, Scene, TextElement, reading_order_text

START_RE = re.compile(r"^(почетак|pocetak|početak|start|begin|почни|pocni)\b", re.I)
END_RE = re.compile(r"^(крај|kraj|end|stop|конец|kraj programa)\b", re.I)
INPUT_RE = re.compile(r"^(улаз|ulaz|input|унос|unos|учитај|ucitaj|učitaj)\b", re.I)
OUTPUT_RE = re.compile(r"^(излаз|izlaz|output|испис|ispis|испиши|ispisi|ispiši)\b", re.I)
TOUCH = 3  # px: shapes this close count as joined
MAX_STEPS = 120


@dataclass
class Node:
    id: str
    kind: str  # start, end, io, decision, process, merge, text, box
    label: str
    x: float
    y: float
    w: float
    h: float
    faded: bool = False

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def contains(self, other: "Node") -> bool:
        return (
            self.x - 1 <= other.x
            and self.y - 1 <= other.y
            and other.x + other.w <= self.x + self.w + 1
            and other.y + other.h <= self.y + self.h + 1
        )


@dataclass
class Edge:
    src: str
    dst: str
    label: str
    label_text: str = ""  # id of a free-standing text used as this edge's label


@dataclass
class Chart:
    title: str
    lines: list[str]
    node_ids: set[str]
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    loops: list[tuple[str, list[str]]] = field(default_factory=list)  # (condition, body)
    decisions: list[tuple[str, list[str]]] = field(default_factory=list)  # (condition, labels)
    calls: list[str] = field(default_factory=list)
    units: list[list[str]] = field(default_factory=list)
    complete: bool = True  # reaches an end

    def text(self) -> str:
        head = f"Algorithm “{self.title}”:" if self.title else "Algorithm:"
        return "\n".join([head, *self.lines])

    def describe(self) -> str:
        """One plain sentence about the algorithm's structure (used without AI)."""
        in_loop = {s for _, body in self.loops for s in body}
        setup = [s for s in self.steps if s not in in_loop][:2]
        parts = []
        if self.inputs:
            parts.append(f"takes {', '.join(self.inputs)}")
        if setup and self.loops:
            parts.append(f"starts with {' and '.join(setup)}")
        elif self.steps and not (self.decisions or self.calls or self.units):
            parts.append(f"does {' → '.join(self.steps[:4])}")
        for cond, body in self.loops[:2]:
            what = " and ".join(body[:2]) if body else "its steps"
            parts.append(f"repeats {what} while “{cond}”")
        for cond, labels in self.decisions[:2]:
            parts.append(f"checks “{cond}”" + (f" ({' / '.join(labels)})" if labels else ""))
        bases = {re.sub(r"\s*\(.*\)\s*$", "", c) for c in self.calls}
        if len(self.calls) >= 2 and len(bases) == 1:
            parts.append(
                f"calls “{bases.pop()}” recursively ({', '.join(self.calls[:4])}), "
                "each call returning to the one that made it"
            )
        elif self.calls:
            parts.append(f"calls a box from {', '.join(self.calls[:3])} and comes back")
        if self.units and not (self.loops or self.decisions or self.calls):
            parts.append(f"works through {len(self.units[0])} joined steps in order")
        if self.outputs:
            parts.append(f"gives {', '.join(self.outputs)}")
        if not self.complete:
            parts.append("(the chart was left unfinished)")
        name = f"“{self.title}”" if self.title else "An algorithm"
        return f"{name}: " + (", ".join(parts) if parts else "a sequence of steps") + "."


def _one_line(label: str) -> str:
    return " ".join(label.split())


class _Graph:
    def __init__(self, scene: Scene):
        self.nodes: dict[str, Node] = {}
        self.texts: list[Node] = []
        for el in scene.elements:
            if isinstance(el, GeoElement):
                self.nodes[el.id] = Node(
                    el.id,
                    self._kind(el),
                    _one_line(el.label),
                    el.x,
                    el.y,
                    el.w,
                    el.h,
                    faded=el.opacity < 0.6,
                )
            elif isinstance(el, TextElement):
                node = Node(
                    el.id,
                    "text",
                    _one_line(el.text),
                    el.x,
                    el.y,
                    el.w,
                    el.h or 20,
                    faded=el.opacity < 0.6,
                )
                self.texts.append(node)
                self.nodes[el.id] = node
        self.edges: list[Edge] = []
        for el in scene.elements:
            if not (
                isinstance(el, ConnectorElement)
                and el.from_id in self.nodes
                and el.to_id in self.nodes
            ):
                continue
            src, dst = el.from_id, el.to_id
            if el.end_head == "none" and el.start_head != "none":
                src, dst = dst, src  # arrowhead drawn at the start
            self.edges.append(Edge(src, dst, _one_line(el.label)))
        self._find_boxes()
        self._find_joined_units()
        self._attach_branch_labels()

    @staticmethod
    def _kind(el: GeoElement) -> str:
        label = _one_line(el.label)
        if el.geo in ("ellipse", "oval"):
            if START_RE.match(label):
                return "start"
            if END_RE.match(label):
                return "end"
            return "merge" if not label else "process"
        if el.geo == "diamond":
            return "decision"
        if el.geo in ("trapezoid", "rhombus", "triangle"):
            return "io"
        return "process"

    def _find_boxes(self) -> None:
        """Rectangles enclosing two or more other shapes are units ('boxed together')."""
        self.box_of: dict[str, str] = {}  # node -> innermost enclosing box
        boxes = []
        for n in self.nodes.values():
            if n.kind != "process" or n.w * n.h <= 0:
                continue
            inside = [m for m in self.nodes.values() if m is not n and n.contains(m)]
            if len([m for m in inside if m.kind != "text"]) >= 2:
                n.kind = "box"
                boxes.append((n.w * n.h, n, inside))
        for _, box, inside in sorted(boxes, key=lambda t: -t[0]):  # largest first, inner wins
            for m in inside:
                self.box_of[m.id] = box.id

    def _find_joined_units(self) -> None:
        """Shapes touching each other in a row or column (no arrows between them) are a unit."""
        cand = [n for n in self.nodes.values() if n.kind in ("process", "io")]
        parent = {n.id: n.id for n in cand}

        def find(a: str) -> str:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for i, a in enumerate(cand):
            for b in cand[i + 1 :]:
                if _touching(a, b):
                    parent[find(a.id)] = find(b.id)
        groups: dict[str, list[Node]] = {}
        for n in cand:
            groups.setdefault(find(n.id), []).append(n)
        self.unit_of: dict[str, list[Node]] = {}
        for members in groups.values():
            if len(members) < 2:
                continue
            ys = [m.cy for m in members]
            vertical = max(ys) - min(ys) > max(m.cx for m in members) - min(m.cx for m in members)
            members.sort(key=(lambda m: (m.y, m.x)) if vertical else (lambda m: (m.x, m.y)))
            for m in members:
                self.unit_of[m.id] = members

    def _attach_branch_labels(self) -> None:
        """Short texts drawn next to a decision (T/F, Da/Ne, 1/2/3) label its branches.

        Each text goes to the outgoing arrow whose target lies in the same direction from the
        decision as the text does.
        """
        short = [t for t in self.texts if 0 < len(t.label) <= 5 and not self.ins(t.id)]
        taken: set[str] = set()
        for d in (n for n in self.nodes.values() if n.kind == "decision"):
            outs = [e for e in self.outs(d.id) if not e.label]
            reach = 0.9 * max(d.w, d.h)
            near = [
                t
                for t in short
                if t.id not in taken
                and d.x - reach <= t.cx <= d.x + d.w + reach
                and d.y - reach <= t.cy <= d.y + d.h + reach
            ]
            for t in sorted(near, key=lambda t: abs(t.cx - d.cx) + abs(t.cy - d.cy)):
                tx, ty = t.cx - d.cx, t.cy - d.cy
                best, score = None, 0.0
                for e in outs:
                    if e.label:
                        continue
                    target = self.nodes[e.dst]
                    vx, vy = target.cx - d.cx, target.cy - d.cy
                    norm = ((vx * vx + vy * vy) ** 0.5) * ((tx * tx + ty * ty) ** 0.5) or 1
                    cos = (tx * vx + ty * vy) / norm
                    if cos > score:
                        best, score = e, cos
                if best is not None:
                    best.label, best.label_text = t.label, t.id
                    taken.add(t.id)

    def outs(self, nid: str) -> list[Edge]:
        return [e for e in self.edges if e.src == nid]

    def ins(self, nid: str) -> list[Edge]:
        return [e for e in self.edges if e.dst == nid]

    def reaches(self, start: str, target: str, avoid: set[str]) -> bool:
        seen, queue = set(), deque([start])
        while queue:
            cur = queue.popleft()
            if cur == target:
                return True
            if cur in seen or cur in avoid:
                continue
            seen.add(cur)
            queue.extend(e.dst for e in self.outs(cur))
        return False

    def distances(self, start: str, stop: set[str]) -> dict[str, int]:
        dist, queue = {start: 0}, deque([start])
        while queue:
            cur = queue.popleft()
            if cur in stop:
                continue
            for e in self.outs(cur):
                if e.dst not in dist:
                    dist[e.dst] = dist[cur] + 1
                    queue.append(e.dst)
        return dist


def _touching(a: Node, b: Node) -> bool:
    h_gap = max(a.x, b.x) - min(a.x + a.w, b.x + b.w)
    v_gap = max(a.y, b.y) - min(a.y + a.h, b.y + b.h)
    h_overlap = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    v_overlap = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    stacked = v_gap <= TOUCH and h_overlap >= 0.5 * min(a.w, b.w)
    side_by_side = h_gap <= TOUCH and v_overlap >= 0.5 * min(a.h, b.h)
    return stacked or side_by_side


class _Writer:
    def __init__(self, g: _Graph, chart: Chart):
        self.g, self.chart = g, chart
        self.done: set[str] = set()
        self.steps = 0

    def emit(self, depth: int, text: str) -> None:
        self.chart.lines.append("  " * (depth + 1) + text)

    def step(self, node: Node, depth: int) -> None:
        self.done.add(node.id)
        self.chart.node_ids.add(node.id)
        self.steps += 1
        faded = " (faded on the board)" if node.faded else ""
        if node.kind == "io":
            nxt = self._next_real(node.id)
            if INPUT_RE.match(node.label) and not OUTPUT_RE.match(node.label):
                self.emit(depth, f"INPUT {node.label}{faded}")
                self.chart.inputs.append(node.label)
            elif OUTPUT_RE.match(node.label) or (
                nxt is not None and nxt.kind == "end" or not self.g.outs(node.id)
            ):
                self.emit(depth, f"OUTPUT {node.label}{faded}")
                self.chart.outputs.append(node.label)
            elif not self.chart.steps and not self.chart.loops:
                self.emit(depth, f"INPUT {node.label}{faded}")
                self.chart.inputs.append(node.label)
            else:
                self.emit(depth, f"SHOW {node.label}{faded}")
                self.chart.outputs.append(node.label)
        else:
            self.emit(depth, f"{node.label}{faded}")
            self.chart.steps.append(node.label)

    def _next_real(self, nid: str) -> Node | None:
        """First following node that is not a merge point."""
        seen = set()
        while True:
            outs = self.g.outs(nid)
            if len(outs) != 1 or nid in seen:
                return None
            seen.add(nid)
            node = self.g.nodes[outs[0].dst]
            if node.kind != "merge":
                return node
            nid = node.id

    def unit(self, members: list[Node], depth: int) -> None:
        self.emit(depth, "UNIT (shapes joined together on the board, read in order):")
        labels = []
        for i, m in enumerate(members):
            if m.id in self.done:
                continue
            if m.kind == "io" and i in (0, len(members) - 1):
                role = "INPUT" if i == 0 else "OUTPUT"
                self.done.add(m.id)
                self.chart.node_ids.add(m.id)
                self.steps += 1
                self.emit(depth + 1, f"{role} {m.label}")
                (self.chart.inputs if i == 0 else self.chart.outputs).append(m.label)
            else:
                self.step(m, depth + 1)
            labels.append(m.label)
        self.chart.units.append(labels)

    def box_body(self, box: Node, depth: int) -> None:
        """Contents of a called box, top to bottom, including the calls they make."""
        members = [n for n in self.g.nodes.values() if self.g.box_of.get(n.id) == box.id]
        for m in sorted(members, key=lambda m: (m.y, m.x)):
            if m.id in self.done or m.kind in ("text", "merge"):
                continue
            self.step(m, depth)
            for e in self.g.outs(m.id):
                target = self.g.nodes[e.dst]
                if target.kind == "box" and target.id not in self.done:
                    self._follow(m, [e], depth, stop=set())

    def walk(self, nid: str | None, depth: int, stop: set[str], inside: str | None = None):
        g = self.g
        while nid is not None and nid not in stop and self.steps < MAX_STEPS:
            node = g.nodes[nid]
            if inside and g.box_of.get(nid) != inside and nid != inside:
                return nid  # left the called box
            if nid in self.done:
                # Joins a path already written out (e.g. a branch that merges into another).
                target = self._next_real(nid) if node.kind == "merge" else node
                if target is not None and target.kind != "end" and target.id not in stop:
                    self.emit(depth, f"(continues at “{target.label}”, as above)")
                return None
            if node.kind == "start":
                self.done.add(nid)
                self.chart.node_ids.add(nid)
                self.emit(depth, "START")
            elif node.kind == "end":
                self.done.add(nid)
                self.chart.node_ids.add(nid)
                self.emit(depth, "END")
                return None
            elif node.kind == "merge":
                self.done.add(nid)
                self.chart.node_ids.add(nid)
            elif node.kind == "decision":
                nid = self.decision(node, depth, stop)
                continue
            elif nid in g.unit_of:
                self.unit(g.unit_of[nid], depth)
                members = {m.id for m in g.unit_of[nid]}
                outs = [e for m in members for e in g.outs(m) if e.dst not in members]
                nid = self._follow(node, outs, depth, stop)
                continue
            elif node.kind == "box":
                self.done.add(nid)
                self.chart.node_ids.add(nid)
                self.emit(depth, f"BOX {node.label}".rstrip() + ":")
                self.box_body(node, depth + 1)
            else:
                self.step(node, depth)
            nid = self._follow(node, g.outs(nid), depth, stop)
        return None

    def _follow(self, node: Node, outs: list[Edge], depth: int, stop: set[str]) -> str | None:
        """Handle calls into boxes, then return the next node on the main path."""
        rest = []
        for e in outs:
            target = self.g.nodes[e.dst]
            if target.kind == "box" and self._returns(target, node.id):
                self.emit(depth, f"CALLS the box below, which returns to “{node.label}”:")
                self.chart.calls.append(node.label)
                self.done.add(target.id)
                self.chart.node_ids.add(target.id)
                self.box_body(target, depth + 1)
            else:
                rest.append(e)
        if not rest:
            return None
        if len(rest) > 1:  # several plain arrows out of a step: follow each
            for e in rest[1:]:
                self.emit(depth, f"ALSO → {self.g.nodes[e.dst].label or 'next'}:")
                self.walk(e.dst, depth + 1, stop)
        return rest[0].dst

    def _returns(self, box: Node, caller: str) -> bool:
        members = {n for n, b in self.g.box_of.items() if b == box.id} | {box.id}
        return any(e.src in members and e.dst == caller for e in self.g.edges)

    def decision(self, node: Node, depth: int, stop: set[str]) -> str | None:
        g = self.g
        self.done.add(node.id)
        self.chart.node_ids.add(node.id)
        outs = g.outs(node.id)
        self.chart.node_ids |= {e.label_text for e in outs if e.label_text}
        if not outs:
            self.emit(depth, f"CHECK “{node.label}”")
            self.chart.decisions.append((node.label, []))
            return None
        back = [e for e in outs if g.reaches(e.dst, node.id, avoid=stop)]
        if back and len(back) < len(outs):
            body = back[0]
            exits = [e for e in outs if e is not body]
            when = f" (on {body.label})" if body.label else ""
            self.emit(depth, f"REPEAT while “{node.label}”{when}:")
            before = len(self.chart.steps)
            self.walk(body.dst, depth + 1, stop | {node.id})
            self.chart.loops.append((node.label, self.chart.steps[before:]))
            if exits[0].label:
                self.emit(depth, f"when “{node.label}” is {exits[0].label}, continue:")
            return exits[0].dst
        # IF / ELSE: branches until they meet again
        dists = [g.distances(e.dst, stop | {node.id}) for e in outs]
        common = set(dists[0]).intersection(*dists[1:]) - {node.id}
        join = min(common, key=lambda n: max(d[n] for d in dists)) if common else None
        self.emit(depth, f"IF “{node.label}”:")
        labels = []
        unlabelled = not any(e.label for e in outs)
        for i, e in enumerate(outs, start=1):
            name = e.label or (f"case {i}" if unlabelled else "otherwise")
            labels.append(name)
            self.emit(depth + 1, f"[{name}]:")
            before = len(self.chart.lines)
            self.walk(e.dst, depth + 2, stop | ({join} if join else set()) | {node.id})
            if len(self.chart.lines) == before:
                self.emit(depth + 2, "(no steps; goes straight on)")
        self.chart.decisions.append((node.label, labels))
        return join


def _title_candidates(g: _Graph, chart_nodes: list[Node]) -> list[tuple[float, Node]]:
    """(distance, text) for texts right above the chart's start or right below its end."""
    starts = [n for n in chart_nodes if n.kind == "start"]
    ends = [n for n in chart_nodes if n.kind == "end"]
    xs0 = min(n.x for n in chart_nodes)
    xs1 = max(n.x + n.w for n in chart_nodes)
    out = []
    for t in g.texts:
        if not t.label or t in chart_nodes or len(t.label) <= 5:
            continue
        if min(xs1, t.x + t.w) - max(xs0, t.x) <= 0:
            continue
        for st in starts:
            gap = st.y - (t.y + t.h)
            if -10 <= gap <= 120:
                out.append((max(gap, 0), t))
        for e in ends:
            gap = t.y - (e.y + e.h)
            if 0 <= gap <= 160:
                out.append((gap + 40, t))  # titles above the start win ties
    return out


def analyze(scene: Scene) -> list[Chart]:
    """All flowcharts on a board, each as structured pseudocode."""
    g = _Graph(scene)
    charts: list[Chart] = []
    used: set[str] = set()
    starts = sorted(
        (n for n in g.nodes.values() if n.kind == "start"), key=lambda n: (n.y // 400, n.x)
    )
    # Pieces that are not reached from a start but still have arrows (unfinished charts)
    roots = starts + sorted(
        (
            n
            for n in g.nodes.values()
            if n.kind not in ("start", "text", "box") and g.outs(n.id) and not g.ins(n.id)
        ),
        key=lambda n: (n.x, n.y),
    )
    for root in roots:
        if root.id in used:
            continue
        chart = Chart(title="", lines=[], node_ids=set())
        writer = _Writer(g, chart)
        writer.walk(root.id, 0, stop=set())
        if root.kind != "start":
            kinds = {g.nodes[n].kind for n in chart.node_ids}
            # Arrows between plain shapes (graphs, object diagrams, circuits) are not
            # algorithms; an unfinished flowchart still shows input/output, a decision or an end.
            if writer.steps == 0 or not kinds & {"io", "decision", "end"}:
                continue
        if root.kind != "start":
            chart.lines.insert(0, "  (not connected to a start on the board)")
        # Only charts that begin at a start can be "unfinished"; loose pieces are just pieces.
        chart.complete = root.kind != "start" or any(
            g.nodes[n].kind == "end" for n in chart.node_ids
        )
        if not chart.complete:
            chart.lines.append("  (the arrows stop here; the chart does not reach an end)")
        used |= chart.node_ids
        # Shapes boxed together with the chart's steps
        boxes: dict[str, list[str]] = {}
        for n in sorted(chart.node_ids, key=lambda n: (g.nodes[n].y, g.nodes[n].x)):
            b = g.box_of.get(n)
            if b and g.nodes[n].kind not in ("merge", "box", "text"):
                boxes.setdefault(b, []).append(g.nodes[n].label)
        for b, labels in boxes.items():
            if g.nodes[b].id in chart.node_ids:
                continue
            name = f" “{g.nodes[b].label}”" if g.nodes[b].label else ""
            faded = " (faded: shown for context)" if g.nodes[b].faded else ""
            chart.lines.append(f"  Boxed together on the board{name}{faded}: {'; '.join(labels)}")
            chart.units.append(labels)
        charts.append(chart)
    charts = [c for c in charts if len(c.lines) > 1]
    # Each title text belongs to the chart it is closest to.
    pairs = sorted(
        (dist, i, t.id, t.label)
        for i, c in enumerate(charts)
        for dist, t in _title_candidates(g, [g.nodes[n] for n in c.node_ids])
    )
    titled, taken = set(), set()
    for _, i, tid, label in pairs:
        if i not in titled and tid not in taken:
            charts[i].title = label
            titled.add(i)
            taken.add(tid)
    return charts


def board_reading(scene: Scene) -> str:
    """Transcript: flowcharts as algorithms first, then everything else on the board."""
    charts = analyze(scene)
    if not charts:
        return reading_order_text(scene)
    used = set().union(*(c.node_ids for c in charts))
    titles = {c.title for c in charts if c.title}
    parts = [c.text() for c in charts]
    rest = reading_order_text(scene, skip_ids=used, skip_texts=titles)
    if rest.strip():
        parts.append("Other notes on the board (not part of a flowchart):\n" + rest)
    return "\n\n".join(parts)
