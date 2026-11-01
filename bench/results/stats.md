Gain = per-picture difference, positive = this version better (lower defects / size count as better).

### this version vs 1.6.0 — flat art (40 pictures)

| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |
|---|---|---|---|---|---|---|
| similarity | 99.44 % | 99.62 % | +0.01 % [+0.00 %, +0.11 %] | 21 / 19 / 0 | 4.5e-06 | +1.00 |
| defects | 0.36 % | 0.14 % | +0.00 % [+0.00 %, +0.03 %] | 15 / 23 / 2 | 2.9e-04 | +0.80 |
| ssim | 0.9828 | 0.9881 | +0.0003 [+0.0000, +0.0035] | 19 / 21 / 0 | 4.5e-06 | +1.00 |
| bytes | 33.4 KB | 33.4 KB | +0.0 KB [-0.6 KB, +0.0 KB] | 6 / 18 / 16 | 0.015 | -0.64 |

### this version vs 1.6.0 — all pictures (45 pictures)

| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |
|---|---|---|---|---|---|---|
| similarity | 99.29 % | 99.57 % | +0.00 % [+0.00 %, +0.05 %] | 21 / 24 / 0 | 4.0e-06 | +1.00 |
| defects | 0.52 % | 0.17 % | +0.00 % [+0.00 %, +0.00 %] | 15 / 28 / 2 | 2.7e-04 | +0.80 |
| ssim | 0.9817 | 0.9864 | +0.0000 [+0.0000, +0.0016] | 19 / 26 / 0 | 4.0e-06 | +1.00 |
| bytes | 40.3 KB | 40.9 KB | +0.0 KB [+0.0 KB, +0.0 KB] | 6 / 23 / 16 | 0.017 | -0.64 |

### this version vs vtracer-default — flat art (40 pictures)

| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |
|---|---|---|---|---|---|---|
| similarity | 98.99 % | 99.62 % | +0.53 % [+0.46 %, +0.87 %] | 38 / 2 / 0 | 4.3e-08 | +1.00 |
| defects | 0.20 % | 0.14 % | +0.10 % [+0.03 %, +0.28 %] | 28 / 5 / 7 | 3.6e-04 | +0.67 |
| ssim | 0.9660 | 0.9881 | +0.0171 [+0.0126, +0.0237] | 37 / 1 / 2 | 2.0e-07 | +0.95 |
| bytes | 136.9 KB | 33.4 KB | +83.3 KB [+44.8 KB, +159.4 KB] | 39 / 0 / 1 | 2.5e-11 | +0.99 |

### this version vs vtracer-default — all pictures (45 pictures)

| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |
|---|---|---|---|---|---|---|
| similarity | 98.90 % | 99.57 % | +0.51 % [+0.45 %, +0.72 %] | 39 / 2 / 4 | 3.6e-05 | +0.70 |
| defects | 0.40 % | 0.17 % | +0.07 % [+0.03 %, +0.21 %] | 29 / 5 / 11 | 0.012 | +0.43 |
| ssim | 0.9600 | 0.9864 | +0.0139 [+0.0112, +0.0215] | 38 / 1 / 6 | 2.8e-04 | +0.62 |
| bytes | 143.1 KB | 40.9 KB | +103.3 KB [+57.5 KB, +167.4 KB] | 44 / 0 / 1 | 8.0e-13 | +0.99 |

### this version vs vtracer-fine — flat art (40 pictures)

| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |
|---|---|---|---|---|---|---|
| similarity | 99.04 % | 99.62 % | +0.48 % [+0.41 %, +0.66 %] | 38 / 1 / 1 | 1.5e-07 | +0.95 |
| defects | 0.17 % | 0.14 % | +0.09 % [+0.00 %, +0.16 %] | 24 / 6 / 10 | 0.012 | +0.50 |
| ssim | 0.9647 | 0.9881 | +0.0166 [+0.0124, +0.0211] | 37 / 1 / 2 | 6.4e-07 | +0.91 |
| bytes | 189.6 KB | 33.4 KB | +166.1 KB [+97.1 KB, +293.3 KB] | 40 / 0 / 0 | 1.8e-12 | +1.00 |

### this version vs vtracer-fine — all pictures (45 pictures)

| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |
|---|---|---|---|---|---|---|
| similarity | 99.03 % | 99.57 % | +0.45 % [+0.38 %, +0.57 %] | 38 / 1 / 6 | 5.8e-04 | +0.58 |
| defects | 0.19 % | 0.17 % | +0.03 % [-0.01 %, +0.13 %] | 24 / 6 / 15 | 0.307 | +0.18 |
| ssim | 0.9631 | 0.9864 | +0.0155 [+0.0109, +0.0186] | 37 / 1 / 7 | 0.002 | +0.52 |
| bytes | 219.2 KB | 40.9 KB | +187.1 KB [+118.9 KB, +570.3 KB] | 45 / 0 / 0 | 5.7e-14 | +1.00 |

### this version vs potrace-8 — flat art (40 pictures)

| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |
|---|---|---|---|---|---|---|
| similarity | 98.22 % | 99.62 % | +0.99 % [+0.41 %, +1.74 %] | 37 / 1 / 2 | 7.8e-11 | +0.98 |
| defects | 7.07 % | 0.14 % | +6.30 % [+1.37 %, +14.38 %] | 33 / 5 / 2 | 4.2e-07 | +0.95 |
| ssim | 0.9651 | 0.9881 | +0.0227 [+0.0155, +0.0267] | 37 / 1 / 2 | 1.5e-07 | +0.96 |
| bytes | 262.0 KB | 33.4 KB | +236.9 KB [+165.2 KB, +359.2 KB] | 40 / 0 / 0 | 1.8e-12 | +1.00 |

### this version vs potrace-8 — all pictures (45 pictures)

| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |
|---|---|---|---|---|---|---|
| similarity | 98.13 % | 99.57 % | +0.91 % [+0.40 %, +1.42 %] | 39 / 1 / 5 | 1.5e-08 | +0.87 |
| defects | 9.54 % | 0.17 % | +6.78 % [+2.77 %, +13.87 %] | 38 / 5 / 2 | 5.3e-08 | +0.95 |
| ssim | 0.9609 | 0.9864 | +0.0227 [+0.0155, +0.0266] | 39 / 1 / 5 | 2.0e-05 | +0.73 |
| bytes | 307.0 KB | 40.9 KB | +265.2 KB [+208.0 KB, +507.9 KB] | 45 / 0 / 0 | 5.7e-14 | +1.00 |

