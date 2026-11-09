Graphics Replicability Stamp Initiative (GRSI) submission
=========================================================

Title
    SHREC 2026: Reconstruction of High-Frequency Geometry in Synthetic Heritage

Authors
    Cristián Llull, Ivan Sipiran, Francisca Gil, Nelson Baloian, Anthony Belessis, Vlassis Fotis,
    George Ioannakis, Efthymios Koukoulis, Konstantinos Moustakas, Sotiris Papatheodorou,
    Ioannis Pratikakis, Ioannis Romanelis, Kriti Singh, Eleftheria Solomonidi, Christoforos Vlachos,
    Vaia Zachari

Venue
    Computers & Graphics 139 (2026) 104726, https://doi.org/10.1016/j.cag.2026.104726

Operating system
    Linux x86_64 (Ubuntu 22.04 LTS or newer). Developed and tested on Debian GNU/Linux 12.
    Only bash, tar, sha256sum and wget (or curl) are required from the system; install.sh
    downloads everything else into the repository folder, without root access.

Hardware
    Any x86_64 CPU and < 1 GB of RAM. No GPU needed. Optionally, an NVIDIA GPU with a driver
    supporting CUDA 11.8 runs the CUDA nearest-neighbour kernel used for the paper
    (bash install.sh --cuda).

Reproduced result
    Table 4 of the paper (CD, FACD, HFACD and HFACD2 of the eight reconstructions of four objects).

Commands (from the repository root)
    bash install.sh            # ~2 min: private Miniforge + Python environment in ./.miniforge, ./.env
    bash reproduce_table4.sh   # ~7 min on 8 CPU cores: downloads the data (~480 MB), computes the
                               # FACD weights and distances, writes results/table4.md and compares
                               # every value with the paper (prints "RESULT: PASS").

    reproduce_table4.sh takes no parameters and also runs install.sh if it has not been run.
    See README.md, section "Reproducing Table 4", for the expected output and the output formats.
