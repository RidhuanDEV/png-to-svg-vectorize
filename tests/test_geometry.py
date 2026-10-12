import numpy as np
import pytest

from pngsvg.curves import _bezier, fit_chain, fit_curve
from pngsvg.planar import build_chains, loop_area, loops_to_path, region_loops


def _max_dev(points: np.ndarray, segs: list[np.ndarray]) -> float:
    """Largest distance from any input point to the fitted curve (dense sampling)."""
    t = np.linspace(0, 1, 200)
    curve = np.vstack([_bezier(s, t) for s in segs])
    d = np.linalg.norm(points[:, None, :] - curve[None, :, :], axis=2)
    return float(d.min(axis=1).max())


def test_fit_curve_respects_tolerance_with_few_segments():
    a = np.linspace(0, np.pi, 120)
    pts = np.stack([50 + 40 * np.cos(a), 50 + 40 * np.sin(a)], 1)
    segs = fit_curve(pts, 0.25)
    assert _max_dev(pts, segs) <= 0.3
    assert len(segs) <= 4
    assert np.allclose(segs[0][0], pts[0]) and np.allclose(segs[-1][3], pts[-1])


def test_per_point_tolerance_loosens_fit():
    rng = np.random.default_rng(0)
    x = np.linspace(0, 100, 200)
    pts = np.stack([x, 3 * np.sin(x / 7) + rng.normal(0, 0.3, x.size)], 1)
    tight = fit_curve(pts, 0.3)
    loose = fit_curve(pts, np.where(x > 50, 3.0, 0.3))
    assert len(loose) < len(tight)


def test_square_keeps_its_corners():
    corners = np.array([(10, 10), (30, 10), (30, 30), (10, 30)], float)
    loop = np.vstack([np.linspace(corners[i], corners[(i + 1) % 4], 20, endpoint=False) for i in range(4)])
    segs = fit_chain(np.round(loop), True, sigma=1.0, error=0.3)
    ends = np.array([s[3] for s in segs])
    for c in corners:   # every corner is (almost) hit by a segment end point
        assert np.linalg.norm(ends - c, axis=1).min() < 1.0


def _random_labels(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small = rng.integers(1, 5, (6, 8))
    lab = np.kron(small, np.ones((5, 5), int))
    lab[rng.random(lab.shape) < 0.05] = 5          # specks, diagonal touches, holes
    return lab


@pytest.mark.parametrize('seed', [0, 1, 2])
def test_planar_map_is_consistent(seed):
    lab = _random_labels(seed)
    h, w = lab.shape
    chains = build_chains(lab)
    # every crack between two different labels (outside = 0) appears in exactly one chain
    P = np.pad(lab, 1)
    cracks = int((P[:, 1:] != P[:, :-1]).sum() + (P[1:, :] != P[:-1, :]).sum())
    assert sum(len(c.points) - (0 if c.closed else 1) for c in chains) == cracks
    assert all(c.left != c.right for c in chains)
    for r, loops in region_loops(chains).items():
        areas = [loop_area(chains, lp) for lp in loops]
        assert abs(sum(areas)) == pytest.approx((lab == r).sum())      # outer minus holes = pixel count
        for lp in loops:                                                 # loops close
            first = chains[lp[0][0]].points
            last = chains[lp[-1][0]].points
            start = first[-1] if lp[0][1] else first[0]
            end = last[0] if lp[-1][1] else last[-1]
            assert chains[lp[0][0]].closed or np.array_equal(start, end)


def test_neighbours_share_identical_boundary():
    lab = np.ones((20, 20), int)
    lab[:, 10:] = 2
    lab[5:9, 3:6] = 2
    chains = build_chains(lab)
    fitted = [fit_chain(c.points, c.closed, 1.0, 0.3) for c in chains]
    loops = region_loops(chains)
    shared = [i for i, c in enumerate(chains) if {c.left, c.right} == {1, 2} and not c.closed]
    assert shared
    p1 = loops_to_path(loops[1], fitted)
    p2 = loops_to_path(loops[2], fitted)
    seg = fitted[shared[0]][0]
    num = f'{seg[3][0]:.3f} {seg[3][1]:.3f}'
    assert num in p1 or f'{seg[0][0]:.3f} {seg[0][1]:.3f}' in p1
    assert num in p2 or f'{seg[0][0]:.3f} {seg[0][1]:.3f}' in p2
