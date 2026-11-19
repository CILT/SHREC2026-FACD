# Camera alignment for the VGGT reconstructions

This directory contains the robust Sim(3) camera alignment used for the VGGT
reconstructions in the paper (Sec. 3.3). The evaluation archive already contains
the aligned results, so running this code is **not required to reproduce
Table 4**; it is required to regenerate the aligned VGGT models from the raw
VGGT outputs. It is included so that the registration step is documented and
reproducible.

## Relation to Table 4

The four VGGT reconstructions evaluated in Table 4 were aligned with this
script:

| Table 4 method | File in `SHREC2026_FACD_Table4.tar.gz` |
|---|---|
| `vggt_frame` | `vggt_frame.ply` |
| `vggt` | `vggt_sparse_aligned.ply` |
| `vggt_100k` | `vggt_sparse_100000_aligned.ply` |
| `vggt_high_def` | `vggt_sparse_res1920_1000000_aligned.ply` |

The distributed files are the aligned outputs; re-running the alignment is not
needed to reproduce the table.

## Contents

- `align_umeyama_iterations.py` — robust Umeyama Sim(3) with iterative
  trimming. It matches GT and reconstruction cameras by image name, repeatedly
  re-estimates the transform and discards the worst pair until `keep_ratio`
  (0.8, i.e. α = 0.2) remains, and optionally applies the transform to a
  reconstruction and writes the 4×4 matrix.
- `colmap_read_write_model.py` — COLMAP model reader (COLMAP, ETH Zurich and
  UNC Chapel Hill, BSD 3-Clause; copyright and license header retained).

## Optional environment

The main Table 4 environment does not include Open3D (it is not needed for
FACD). The alignment script was run with Open3D 0.17.0 and NumPy 1.x. Install
these separately, for example:

```bash
conda create -p .align-env python=3.10
.align-env/bin/python -m pip install -r alignment/requirements.txt
```

## Usage

```bash
.align-env/bin/python alignment/align_umeyama_iterations.py \
    --gt_cams /path/to/gt/images.txt \
    --rec_cams /path/to/reconstruction/cameras.json \
    --input_model /path/to/reconstruction/points.ply \
    --out_model results/aligned.ply \
    --out_transform results/T_rec_to_gt.txt \
    --keep_ratio 0.8
```

Inputs:

- `--gt_cams`, `--rec_cams`: COLMAP `.txt` / `.bin` or a JSON list of
  `{"image": ..., "extrinsic": 3x4}` entries. The two camera sets must share
  image names.
- `--input_model`: optional `.ply` mesh or point cloud to transform.
- `--keep_ratio`: fraction of camera pairs kept; the paper uses 0.8 (drops the
  worst 20 %).
- Outputs: the aligned model (if `--input_model` is given), the 4×4 Sim(3)
  matrix, and the inlier/global RMSE printed to the console.

For the batch wrapper used to process the full reconstruction directory, see
`VGGT/run_alignment_umeyama_iterations.sh` in
[https://github.com/CILT/3d-evaluation](https://github.com/CILT/3d-evaluation).

## License

`align_umeyama_iterations.py` is covered by the repository MIT License
(`../LICENSE`). `colmap_read_write_model.py` is derived from COLMAP (ETH
Zurich and UNC Chapel Hill) and is distributed under the BSD 3-Clause license;
its copyright and license header is retained in the file.
