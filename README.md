# SHREC 2026: Reconstruction of high-frequency geometry in synthetic heritage

- Novel synthetic Khachkar dataset for evaluating untextured 3D stone surfaces.
- FACD metric penalizes smoothing bias to evaluate fine 3D micro-topography.
- Evaluation of 8 reconstruction paradigms shows that global averages misrank methods.


## FACD: Feature-Aware Chamfer Distance

### Compute FACD


# Citation

If you find FACD -- Feature-Aware Chamfer Distance useful, please cite:
```
@article{llull2026FACD,
    title = {SHREC 2026: Reconstruction of high-frequency geometry in synthetic heritage},
    journal = {Computers & Graphics},
    volume = {139},
    pages = {104726},
    year = {2026},
    issn = {0097-8493},
    doi = {https://doi.org/10.1016/j.cag.2026.104726},
    url = {https://www.sciencedirect.com/science/article/pii/S0097849326001974},
    author = {Cristián Llull and Ivan Sipiran and Francisca Gil and Nelson Baloian and Anthony Belessis and Vlassis Fotis and George Ioannakis and Efthymios Koukoulis and Konstantinos Moustakas and Sotiris Papatheodorou and Ioannis Pratikakis and Ioannis Romanelis and Kriti Singh and Eleftheria Solomonidi and Christoforos Vlachos and Vaia Zachari},
    keywords = {3D shape retrieval, 3D reconstruction, Cultural heritage},
}


```

If you find `chamferdist` work useful, you might want to cite the *original* implementation from which this codebase was borrowed (stolen!) - PyTorch3D.

```
@article{ravi2020pytorch3d,
    author = {Nikhila Ravi and Jeremy Reizenstein and David Novotny and Taylor Gordon
                  and Wan-Yen Lo and Justin Johnson and Georgia Gkioxari},
    title = {Accelerating 3D Deep Learning with PyTorch3D},
    journal = {arXiv:2007.08501},
    year = {2020},
}
```

