# Sample: evaluating one reconstruction

This directory contains the small Figure 1 sample archive and a worked example
for evaluating one reconstruction. The four Table 4 objects are not stored here:
they are downloaded on demand (~480 MB, see `download/README.md`), so the
submission stays small and every number comes from the published archive.

The subset contains four objects. This example evaluates the SuGaR
reconstruction (`SAMplify_SuGaR.obj`) of the first one:

```bash
bash installation/install_dependencies.sh    # once, ~2 min
bash download/download_evaluation_subset.sh  # ~480 MB

.env/bin/python scripts/evaluate_reconstruction.py \
    --ground_truth   data/SHREC2026_FACD_Table4/90_1920x1080_relief_heightmap_5_one_face_wide/gt.obj \
    --reconstruction data/SHREC2026_FACD_Table4/90_1920x1080_relief_heightmap_5_one_face_wide/SAMplify_SuGaR.obj \
    --output_csv results/sample_evaluation.csv
```

Expected values (paper Table 4):

| Metric | Value |
|---|---|
| CD | 0.001107 |
| FACD | 0.151228 |
| HFACD | 0.010094 |
| HFACD2 | 0.132688 |

The weights are computed from `gt.obj` the first time the script runs. If
`gt_curvature.json` is already next to the ground truth, it is reused. To use
the weights distributed with the paper instead, add
`--weights data/SHREC2026_FACD_Table4/<object>/gt_curvature_paper.json`.

The CPU KD-tree uses float64 distances while the printed table used the
float32 CUDA kernel, so a few values may differ in the last decimals. See
`results/README.md` for the exact tolerances used by the Table 4 check.

## Evaluating your own reconstruction

Put the ground truth and your reconstruction anywhere and run:

```bash
.env/bin/python scripts/evaluate_reconstruction.py \
    --ground_truth   /path/to/gt.obj \
    --reconstruction /path/to/reconstruction.ply \
    --output_csv     results/my_evaluation.csv
```

The reconstruction must already be registered to the ground-truth frame
(paper Sec. 3.3). A JSON weights file can be supplied with `--weights`; it maps
`{"<0-based vertex index>": weight}`.

## Reproducing the README teaser (Figure 1)

`sample/figure_01.tar.gz` (~13 MB compressed, ~76 MB extracted) contains the
mesh and the FACD weights of relief 1, one_face, the object in the README
teaser. It is not one of the four Table 4 objects, so it is shipped here to
keep the figure reproducible without the full dataset. The data is a small
excerpt of the authors' synthetic dataset; see the License section of the main
README.

```bash
bash scripts/reproduce_figure_01.sh
```

The script extracts the archive to a temporary directory, renders
`results/figure_01.png`, and compares it pixel by pixel with
`docs/teaser_250x250.png`.

Archive contents:

```
figure_01/figure_01.obj
figure_01/figure_01_curvature.json
```

SHA-256 of `sample/figure_01.tar.gz`:
`0ed49a761a1746c0fec0217d9a687a82369d8171cad846ceb81c8fadd5e4498b`.
