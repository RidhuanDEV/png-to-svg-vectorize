"""Planar map from a label image: shared boundary chains between regions.

Boundaries run along pixel cracks (between two pixels with different labels; outside the image = label 0).
Crack corners where more than two labels meet are junctions; a chain is a maximal run of cracks between
junctions (or a closed loop). Each chain is fitted ONCE and reused by both regions it separates, so neighbours
share exactly the same geometry: no gaps, no overlap needed.

Coordinates are (x, y) in pixel-corner units, y down.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Chain:
    points: np.ndarray      # (N, 2) corner coordinates (x, y), in traversal order
    left: int               # label on the left of the traversal direction (y down: left = screen-left)
    right: int
    closed: bool


def build_chains(label: np.ndarray) -> list[Chain]:
    h, w = label.shape
    P = np.pad(label.astype(np.int64), 1, constant_values=0)
    W1 = w + 1

    # horizontal cracks: corner (x, y) -> (x + 1, y); above = P[y, x+1], below = P[y+1, x+1]; moving +x, left = above
    above, below = P[0:h + 1, 1:w + 1], P[1:h + 2, 1:w + 1]
    hy, hx = np.nonzero(above != below)
    h_start = hy * W1 + hx
    h_end = h_start + 1
    h_left, h_right = above[hy, hx], below[hy, hx]
    # vertical cracks: corner (x, y) -> (x, y + 1); west = P[y+1, x], east = P[y+1, x+1]; moving +y, left = east
    west, east = P[1:h + 1, 0:w + 1], P[1:h + 1, 1:w + 2]
    vy, vx = np.nonzero(west != east)
    v_start = vy * W1 + vx
    v_end = v_start + W1
    v_left, v_right = east[vy, vx], west[vy, vx]

    start = np.r_[h_start, v_start]
    end = np.r_[h_end, v_end]
    left = np.r_[h_left, v_left]
    right = np.r_[h_right, v_right]
    n_edges = len(start)
    if n_edges == 0:
        return []

    # incidence: corner -> edges (as Python lists; only boundary corners appear)
    inc: dict[int, list[int]] = {}
    for e, (a, b) in enumerate(zip(start.tolist(), end.tolist())):
        inc.setdefault(a, []).append(e)
        inc.setdefault(b, []).append(e)
    start_l, end_l, left_l, right_l = start.tolist(), end.tolist(), left.tolist(), right.tolist()

    used = bytearray(n_edges)
    chains: list[Chain] = []

    def other(e: int, corner: int) -> int:
        return end_l[e] if start_l[e] == corner else start_l[e]

    for e0 in range(n_edges):
        if used[e0]:
            continue
        used[e0] = 1
        # forward from end of e0 (traversal orientation = e0's stored orientation)
        fwd = [start_l[e0], end_l[e0]]
        corner, e = end_l[e0], e0
        closed = False
        while len(inc[corner]) == 2:
            nxt = inc[corner][0] if inc[corner][1] == e else inc[corner][1]
            if nxt == e0:
                closed = True
                break
            if used[nxt]:
                break
            used[nxt] = 1
            corner = other(nxt, corner)
            fwd.append(corner)
            e = nxt
        if not closed:
            back = []
            corner, e = start_l[e0], e0
            while len(inc[corner]) == 2:
                nxt = inc[corner][0] if inc[corner][1] == e else inc[corner][1]
                if used[nxt]:
                    break
                used[nxt] = 1
                corner = other(nxt, corner)
                back.append(corner)
                e = nxt
            fwd = back[::-1] + fwd
        else:
            fwd = fwd[:-1]
        ids = np.array(fwd, dtype=np.int64)
        pts = np.stack([ids % W1, ids // W1], axis=1).astype(np.float64)
        chains.append(Chain(pts, int(left_l[e0]), int(right_l[e0]), closed))
    return chains


def region_loops(chains: list[Chain]):
    """For every region, the closed loops of chain references (chain index, reversed?) with the region on the
    left. Returns {region: [loop, ...]} where loop = [(chain_idx, reversed), ...]."""
    by_region: dict[int, list[tuple[int, bool]]] = {}
    for i, c in enumerate(chains):
        if c.left > 0:
            by_region.setdefault(c.left, []).append((i, False))
        if c.right > 0:
            by_region.setdefault(c.right, []).append((i, True))

    def ends(i: int, rev: bool):
        p = chains[i].points
        return (tuple(p[-1]), tuple(p[0])) if rev else (tuple(p[0]), tuple(p[-1]))

    loops: dict[int, list[list[tuple[int, bool]]]] = {}
    for r, refs in by_region.items():
        closed = [ref for ref in refs if chains[ref[0]].closed]
        open_refs = [ref for ref in refs if not chains[ref[0]].closed]
        result = [[ref] for ref in closed]
        starts: dict[tuple, list[tuple[int, bool]]] = {}
        for ref in open_refs:
            starts.setdefault(ends(*ref)[0], []).append(ref)
        used: set[tuple[int, bool]] = set()
        for ref in open_refs:
            if ref in used:
                continue
            loop = [ref]
            used.add(ref)
            first = ends(*ref)[0]
            cur_end = ends(*ref)[1]
            guard = 0
            while cur_end != first and guard < len(open_refs) + 1:
                guard += 1
                cand = [c for c in starts.get(cur_end, []) if c not in used]
                if not cand:
                    break
                nxt = cand[0]
                used.add(nxt)
                loop.append(nxt)
                cur_end = ends(*nxt)[1]
            result.append(loop)
        loops[r] = result
    return loops


def _oriented(arr_list: list[np.ndarray], rev: bool) -> list[np.ndarray]:
    return [s[::-1] for s in reversed(arr_list)] if rev else arr_list


def loop_area(chains: list[Chain], loop: list[tuple[int, bool]]) -> float:
    """Signed area (shoelace) of a loop of crack chains; all loops of one region with the region on the left
    share a sign for outer boundaries, holes have the opposite sign."""
    pts = np.vstack([chains[i].points[::-1] if rev else chains[i].points for i, rev in loop])
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def loops_to_path(loops: list[list[tuple[int, bool]]], fitted: list[list[np.ndarray]]) -> str:
    """Absolute 'M ... C ... Z' path for a set of loops, built from the shared fitted chain segments."""
    parts = []
    for loop in loops:
        segs = [s for i, rev in loop for s in _oriented(fitted[i], rev)]
        if not segs:
            continue
        x0, y0 = segs[0][0]
        parts.append(f'M{x0:.3f} {y0:.3f}')
        parts.append(''.join(f'C{a[0]:.3f} {a[1]:.3f} {b[0]:.3f} {b[1]:.3f} {c[0]:.3f} {c[1]:.3f}'
                             for _, a, b, c in segs))
        parts.append('Z')
    return ''.join(parts)


def subpixel_offsets(chain: Chain, label: np.ndarray, rgb: np.ndarray, mean: np.ndarray, hidden: np.ndarray | None,
                     min_contrast: float = 30.0) -> np.ndarray:
    """Sub-pixel position of the color edge at every crack of a chain, from anti-aliasing.

    Across a crack, the left pixel holds a fraction a_l of the left color A and the right pixel a_r of it (colors
    projected on the A-B line). With an area-sampled edge, the edge lies e = a_l + a_r - 1 pixels from the crack,
    toward the right. A and B are taken one pixel further out (local color, robust to gradients), falling back to
    the region means. Cracks between similar colors, at the image border or under the outline layer get 0."""
    h, w = label.shape
    c = chain.points
    nxt = np.roll(c, -1, axis=0) if chain.closed else c[1:]
    cur = c if chain.closed else c[:-1]
    mid = (cur + nxt) / 2
    d = nxt - cur
    nl = np.stack([d[:, 1], -d[:, 0]], 1)

    def pix(k):
        q = np.floor(mid + k * nl).astype(int)
        ok = (q[:, 0] >= 0) & (q[:, 0] < w) & (q[:, 1] >= 0) & (q[:, 1] < h)
        return np.clip(q[:, 1], 0, h - 1), np.clip(q[:, 0], 0, w - 1), ok

    ly, lx, lok = pix(0.5)
    ry, rx, rok = pix(-0.5)
    out = np.zeros(len(mid))
    if chain.left <= 0 or chain.right <= 0:
        return out
    ay, ax, aok = pix(1.5)
    by, bx, bok = pix(-1.5)
    A = np.where((aok & (label[ay, ax] == chain.left))[:, None], rgb[ay, ax], mean[chain.left])
    B = np.where((bok & (label[by, bx] == chain.right))[:, None], rgb[by, bx], mean[chain.right])
    ab = A - B
    den = (ab * ab).sum(1)
    a_l = np.clip(((rgb[ly, lx] - B) * ab).sum(1) / np.maximum(den, 1e-9), 0, 1)
    a_r = np.clip(((rgb[ry, rx] - B) * ab).sum(1) / np.maximum(den, 1e-9), 0, 1)
    use = lok & rok & (den >= min_contrast ** 2)
    if hidden is not None:
        use &= ~hidden[ly, lx] & ~hidden[ry, rx]
    out[use] = np.clip(a_l + a_r - 1, -0.75, 0.75)[use]
    return out
