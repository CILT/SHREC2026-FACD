# Results

`results/` is the output directory of the replication scripts. Generated files
are ignored by Git; this README documents what the scripts write here.

## Reproducing Table 4

```bash
bash scripts/reproduce_table_04.sh
```

| File | Content |
|---|---|
| `table4.md`, `table4.tex` | Table 4 (best in bold, second best in italics/underlined, worst with `*`). |
| `table4_distances.csv` | One row per (`experiment_id`, `method`): `cd`, `hcd`, `hcd_2`, `facd`, `hfacd`, `hfacd_2`, `num_source_pts` (reconstruction), `num_target_pts` (ground truth). |
| `table4_compare.csv` | For every cell of Table 4: computed value, value in the paper, absolute and relative difference. |

The check passes when every value matches the paper to its printed precision
(6 decimals) or within 0.1 % relative, and when the best, second-best and worst
methods of every row are identical to the paper. The expected final lines are:

```
Compared 128 values with the paper:
  123 identical to the printed 6 decimals, 5 within 0.1% (largest relative difference among them 7.14e-04), 0 differ, 0 missing.
  Best / second best / worst method identical in 16 of 16 rows.
RESULT: PASS - Table 4 of the paper is reproduced.
```

The script exits with code 1 and prints `RESULT: FAIL` if a value or a ranking
differs. The five non-identical values are explained in the main `README.md`
(recomputed weights in one corner of one mesh, and float32 CUDA vs. float64
KD-tree arithmetic).

## Evaluating a single reconstruction

`scripts/evaluate_reconstruction.py` writes one CSV row to
`results/evaluation.csv` (or the path given with `--output_csv`) with the
columns `ground_truth`, `reconstruction`, `method`, `cd`, `hcd`, `hcd_2`,
`facd`, `hfacd`, `hfacd_2`, `num_source_pts`, `num_target_pts`, `device` and
`weights`.

## Reproducing Figure 1

`scripts/reproduce_figure_01.sh` writes `results/figure_01.png`, the 250×250
FACD weight map of relief 1, one_face (the README teaser), and compares it
pixel by pixel with `docs/teaser_250x250.png`.
