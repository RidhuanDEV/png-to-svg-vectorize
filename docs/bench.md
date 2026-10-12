# Benchmark

Run with `python bench/synthetic.py` once, then `python bench/run.py` (needs Chrome or Edge for the similarity
render). Compare against the committed baseline with `python bench/run.py --baseline bench/baseline.json`
(exit code 1 on regression: similarity −0.3 points or size +10 %).

- **Synthetic set** (`bench/synthetic.py`, 9 procedural images, license-free): face with soft blush, flat logo,
  outlined icon, radial-gradient sphere, faint concentric rings, stripes + dots, thin lines, gradient background,
  overlapping leaves.
- **Private set**: 15 cartoon illustrations from the Turion app (image-generator art, 1536×1024 / 1774×887). Not
  published; numbers reported for reference.

Machine: Windows 11 laptop, Python 3.13, single process.

## v0.1 baseline (2026-10-12)

### Synthetic set

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| face | 98.56% | 99.1% | 96120 | 4882 | 69 | 9.2 |
| gradient-bg | 99.47% | 99.7% | 62038 | 3173 | 14 | 9.1 |
| icon-outline | 99.81% | 99.6% | 42758 | 2179 | 8 | 7.6 |
| leaves | 98.97% | 97.8% | 156408 | 7822 | 348 | 7.4 |
| logo-flat | 99.85% | 99.5% | 48180 | 2488 | 288 | 7.9 |
| rings | 99.37% | 99.7% | 274245 | 14306 | 128 | 10.0 |
| sphere | 99.62% | 99.5% | 141684 | 7487 | 24 | 6.0 |
| stripes | 99.49% | 98.4% | 130265 | 6916 | 142 | 7.8 |
| thin-lines | 97.67% | 97.5% | 37771 | 1896 | 142 | 5.6 |
| **median** | 99.47% | 99.5% | 96120 | 4882 | 128 | 7.8 |

### Private set (Turion illustrations)

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| acuan-gagal | 99.10% | 98.3% | 395959 | 18655 | 604 | 18.3 |
| acuan-sukses | 98.94% | 98.4% | 370628 | 17437 | 569 | 18.2 |
| promo-gizi | 98.55% | 95.7% | 494092 | 22501 | 668 | 19.7 |
| promo-kendaraan | 98.34% | 95.7% | 459659 | 20977 | 396 | 19.2 |
| promo-kesehatan | 98.40% | 95.5% | 743061 | 33717 | 970 | 27.6 |
| promo-keuangan | 98.57% | 95.7% | 477963 | 22011 | 673 | 19.9 |
| promo-offline | 98.51% | 96.1% | 483387 | 22445 | 403 | 19.0 |
| promo-olahraga | 98.53% | 96.0% | 415956 | 19032 | 249 | 16.3 |
| promo-peluncuran | 98.71% | 96.2% | 460184 | 20973 | 836 | 18.0 |
| promo-pendidikan | 98.38% | 95.2% | 526618 | 24275 | 543 | 18.6 |
| promo-pengingat | 98.57% | 96.3% | 395252 | 18584 | 443 | 16.0 |
| promo-pola-hidup | 98.67% | 96.8% | 381325 | 17767 | 388 | 16.0 |
| promo-premium | 98.72% | 96.9% | 605496 | 28554 | 627 | 22.2 |
| promo-rumah | 98.87% | 97.0% | 374213 | 17156 | 412 | 16.9 |
| promo-sambutan | 98.94% | 97.3% | 353154 | 16394 | 280 | 14.8 |
| **median** | 98.57% | 96.2% | 459659 | 20973 | 543 | 18.3 |
