import numpy as np
import xarray as xr
from scipy.spatial.transform import Rotation
from skimage.transform import AffineTransform


def affine_from_translation(translation):
    """
    Return matrix in homogeneous coords representing a translation.
    """
    ndim = len(translation)
    M = np.concatenate([translation, [1]], axis=0)
    M = np.concatenate([np.eye(ndim + 1)[:, :ndim], M[:, None]], axis=1)
    return M


def affine_from_linear_affine(linear_affine):
    """
    Return matrix in homogeneous coords representing a translation.
    """
    ndim = 3 if len(linear_affine) == 12 else 2

    M = np.eye(ndim + 1)
    M[:ndim, :ndim] = linear_affine[: ndim**2].reshape((ndim, ndim))
    M[:ndim, ndim] = linear_affine[-ndim:]

    return M


def linear_affine_from_affine(affine):
    """
    Return linear representation of affine matrix from affine matrix.
    """
    ndim = affine.shape[-1] - 1

    linear_affine = np.zeros(ndim**2 + ndim, dtype=float)

    linear_affine[: ndim**2] = affine[:ndim, :ndim].flatten()
    linear_affine[-ndim:] = affine[:ndim, ndim]

    return linear_affine


def random_scale(ndim, scale=0.1):
    return 1 + np.random.random(ndim) * scale - scale / 2


def random_translation(ndim=2, scale=10):
    return np.random.random(ndim) * scale - scale / 2


def random_rotation(ndim=2, scale=0.1):
    return np.random.random(ndim - 1) * scale - scale / 2


def random_affine(
    ndim=2,
    translation_scale=10,
    rotation_scale=0.1,
    scale_scale=0.1,
):
    return AffineTransform(
        translation=random_translation(ndim, translation_scale),
        rotation=random_rotation(ndim, rotation_scale),
        scale=random_scale(ndim, scale_scale),
    ).params


def invert_coordinate_order(affine):
    """ """
    ndim = affine.shape[-1] - 1
    M = np.eye(ndim + 1)
    M[:ndim, :ndim] = affine[:ndim, :ndim][::-1, ::-1]
    M[:ndim, ndim] = affine[:ndim, ndim][::-1]
    return M


def translation_from_affine(affine):
    """
    Return matrix in homogeneous coords representing a translation.
    """
    ndim = len(affine) - 1
    t = affine[:ndim, ndim]
    return t


def affine_from_rotation(angle, direction, point=None):
    """
    Return matrix in homogeneous coords to rotate around axis
    defined by point and direction.
    """

    R = Rotation.from_rotvec(angle * np.array(direction)).as_matrix()

    M = np.identity(4)
    M[:3, :3] = R
    if point is not None:
        # rotation not around origin
        point = np.array(point[:3], dtype=np.float64, copy=False)
        M[:3, 3] = point - np.dot(R, point)

    return M


def identity_transform(ndim, t_coords=None):
    if t_coords is None:
        params = xr.DataArray(np.eye(ndim + 1), dims=["x_in", "x_out"])
    else:
        params = xr.DataArray(
            len(t_coords) * [np.eye(ndim + 1)],
            dims=["t", "x_in", "x_out"],
            coords={"t": t_coords},
        )

    return params


def affine_to_xaffine(affine, t_coords=None):
    if t_coords is None:
        params = xr.DataArray(affine, dims=["x_in", "x_out"])
    else:
        params = xr.DataArray(
            len(t_coords) * [affine],
            dims=["t", "x_in", "x_out"],
            coords={"t": t_coords},
        )

    return params


def matmul_xparams(xparams1, xparams2):
    return xr.apply_ufunc(
        np.matmul,
        xparams1,
        xparams2,
        input_core_dims=[["x_in", "x_out"]] * 2,
        output_core_dims=[["x_in", "x_out"]],
        dask="parallelized",
        vectorize=True,
        join="inner",
    )


def invert_xparams(xparams):
    return xr.apply_ufunc(
        np.linalg.inv,
        xparams,
        input_core_dims=[["x_in", "x_out"]],
        output_core_dims=[["x_in", "x_out"]],
        vectorize=False,
        # dask='allowed',
        dask="parallelized",
    )


def get_xparam_from_param(params):
    """
    Homogeneous matrix to xparams
    """

    ndim = params.shape[-1] - 1

    xparam = xr.DataArray(
        params,
        dims=["x_in", "x_out"],
        coords={
            "x_in": ["z", "y", "x"][-ndim:] + ["1"],
            "x_out": ["z", "y", "x"][-ndim:] + ["1"],
        },
    )

    return xparam


def rebase_affine(xaffine, base_affine):
    """
    Take two xr.DataArrays of affine transforms and
    - align their coordinates
    - fill missing values with identity
    - chain transforms
    """

    ndim = len(xaffine.coords["x_in"]) - 1

    xaffines_aligned = xr.align(xaffine, base_affine, join="outer")
    xaffines_aligned_filled = [
        xaff.fillna(identity_transform(ndim)) for xaff in xaffines_aligned
    ]

    rebased = matmul_xparams(
        xaffines_aligned_filled[0], xaffines_aligned_filled[1]
    )

    return rebased


def get_spatial_dims_from_params(xparams):
    return [dim for dim in xparams.dims if dim in ["x_in", "x_out"]]


def get_non_spatial_dims_from_params(xparams):
    return [
        dim
        for dim in xparams.dims
        if dim not in get_spatial_dims_from_params(xparams)
    ]
