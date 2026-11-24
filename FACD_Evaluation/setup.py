# Builds the optional C++/CUDA KNN extension `localchamferdist._C`.
# Adapted from chamferdist (https://github.com/krrish94/chamferdist).
#
#   cd FACD_Evaluation && python setup.py build_ext --inplace
#
# Without it, localchamferdist falls back to an exact scipy KD-tree search.
import os
import runpy

import torch
from setuptools import setup
from torch.utils.cpp_extension import CUDA_HOME, CppExtension, CUDAExtension


def get_extensions():
    include_dirs = [os.path.abspath("localchamferdist")]
    main_source = os.path.join("localchamferdist", "ext.cpp")
    sources = [os.path.join("localchamferdist", "knn_cpu.cpp")]
    source_cuda = [os.path.join("localchamferdist", "knn.cu")]
    sources = [main_source] + sources

    extension = CppExtension

    extra_compile_args = {"cxx": ["-std=c++17"]}
    define_macros = []

    force_cuda = os.getenv("FORCE_CUDA", "0") == "1"
    if (torch.cuda.is_available() and CUDA_HOME is not None) or force_cuda:
        extension = CUDAExtension
        sources += source_cuda
        define_macros += [("WITH_CUDA", None)]
        nvcc_args = [
            "-DCUDA_HAS_FP16=1",
            "-D__CUDA_NO_HALF_OPERATORS__",
            "-D__CUDA_NO_HALF_CONVERSIONS__",
            "-D__CUDA_NO_HALF2_OPERATORS__",
        ]
        nvcc_flags_env = os.getenv("NVCC_FLAGS", "")
        if nvcc_flags_env != "":
            nvcc_args.extend(nvcc_flags_env.split(" "))

        CC = os.environ.get("CC", None)
        if CC is not None:
            CC_arg = "-ccbin={}".format(CC)
            if CC_arg not in nvcc_args:
                if any(arg.startswith("-ccbin") for arg in nvcc_args):
                    raise ValueError("Inconsistent ccbins")
                nvcc_args.append(CC_arg)

        extra_compile_args["nvcc"] = nvcc_args

    ext_modules = [
        extension(
            "localchamferdist._C",
            sources,
            include_dirs=include_dirs,
            define_macros=define_macros,
            extra_compile_args=extra_compile_args,
        )
    ]

    return ext_modules


__version__ = runpy.run_path("localchamferdist/version.py")["__version__"]

setup(
    name="localchamferdist",
    version=__version__,
    description="Chamfer and Feature-Aware Chamfer Distance (FACD) in PyTorch",
    packages=["localchamferdist"],
    package_data={"localchamferdist": ["*.cu", "*.cuh", "*.h"]},
    install_requires=[],
    ext_modules=get_extensions(),
    cmdclass={"build_ext": torch.utils.cpp_extension.BuildExtension},
)
