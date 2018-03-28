import math

import numpy as np
from scipy.signal import detrend

DENSITY_ICE = 917.

SMP_CONE_DIAMETER = 5

_DEFAULT_WINDOW = 2.5
_DEFAULT_WINDOW_OVERLAP = 1.2


def shotnoise_from_evalSMP(spatial_res, force_arr, area_cone=(SMP_CONE_DIAMETER / 2.) ** 2 * math.pi):
    # this version is taken from evalSMP and returns 5 parameters (instead of 4): lambda, f0, delta, L and median(F)
    """Returns the parameters lambda, f0, delta, L of the (uniform
    strength) shot noise model according to Loewe, van Herwijnen CRST
    70, 62-70 (2012)
    dz: spatial resolution
    f_z: force array
    a_cone: projected SMP tip area (mm^2)
    """

    # Auxiliary parameters
    n = force_arr.size

    # Mean and variance of the signal
    k1 = np.mean(force_arr)
    k2 = np.var(force_arr)

    # Detrend signal, note that the detrending is not foreseen in LvH (!!) but recommended by Martin Proksch
    force_arr = detrend(force_arr - k1, type='linear')

    # Covariance/auto-correlation
    c_f = np.correlate(force_arr, force_arr, mode='full')  # eq. 8 in LvH 2012

    # Retrieve shot noise parameters

    # Equation 11 in publication
    delta = -(3. / 2) * c_f[n - 1] / (c_f[n] - c_f[n - 1]) * spatial_res

    # Equations 12 in publication
    # lambda_ = Intensity
    lambda_ = (4. / 3) * (k1 ** 2) / k2 / delta
    f0 = (3. / 2) * k2 / k1

    # According to equation 2 in publication
    L = (area_cone / lambda_) ** (1. / 3)

    return lambda_, f0, delta, L


def calc_density_ssa_proksch2015(median_force, element_size):
    """Calculation of density and ssa

    This function calculates density and ssa (specific surface area)
    according to publication Proksch, 2015, Journal of Geophysical
    Research.

    https://agupubs.onlinelibrary.wiley.com/doi/epdf/10.1002/2014JF003266

    :param median_force: median of force
    :param element_size: element size
    :return: Tuple containing density and ssa
    """

    L = element_size
    fm = median_force
    rho_ice = DENSITY_ICE

    # Equation 9 in publication
    a1 = 420.47
    a2 = 102.47
    a3 = -121.15
    a4 = -169.96
    rho = a1 + a2 * np.log(fm) + a3 * np.log(fm) * L + a4 * L

    # Equation 11 in publication
    c1 = 0.131
    c2 = 0.355
    c3 = 0.0291
    lc = c1 + c2 * L + c3 * np.log(fm)

    # Equation 12 in publication
    SSA = 4 * (1 - (rho / rho_ice)) / lc

    return rho, SSA


def agg_force_windows(samples, window, overlap, agg=np.median):
    """
    :param samples:
    :param window: Window size in Millimeter. Default to 2.5 mm.
    :param overlap: Overlap length in Millimeter. Default to 0.5 mm.
    :param agg: Aggregation function, default is ```np.median``.
    :return:
    """

    distance_arr = samples[:, 0]

    # Calculate average step size
    block_length = window * overlap
    block_center = distance_arr[0]

    blocks = []
    while block_center < distance_arr[-1]:
        block_begin = block_center - block_length / 2.
        block_end = block_center + block_length / 2.
        within_block = np.logical_and(distance_arr >= block_begin, distance_arr < block_end)
        d = block_center
        f = agg(samples[within_block][:, 1])
        blocks.append((d, f))
        block_center = block_center + window
    return np.array(blocks)


def chunkup(samples, window, overlap_factor):
    distance_arr = samples[:, 0]

    block_length = window * overlap_factor

    blocks = []
    center = distance_arr[0]
    while center < distance_arr[-1]:
        # Calculate where block begins and ends
        begin = center - block_length / 2.
        end = center + block_length / 2.

        # Filter for samples with a block and add it to the list of
        # blocks along with its center (the blocks center distance)
        within_block = np.logical_and(distance_arr >= begin, distance_arr < end)
        block_samples = samples[within_block]
        blocks.append((center, block_samples))

        center = center + window
    return blocks


def model_shotnoise(samples, window=_DEFAULT_WINDOW, overlap_factor=_DEFAULT_WINDOW_OVERLAP):
    spatial_res = np.mean(np.diff(samples[:, 0]))
    chunks = chunkup(samples, window, overlap_factor)
    result = []
    for center, chunk in chunks:
        force_chunk = chunk[:, 1]
        shotnoise = shotnoise_from_evalSMP(spatial_res, force_chunk)
        r = (center,) + shotnoise
        result.append(r)
    return np.array(result)


def model_ssa_and_density(samples, window=_DEFAULT_WINDOW, overlap_factor=_DEFAULT_WINDOW_OVERLAP):
    # Shot noise model is to base
    shotnoise = model_shotnoise(samples, window, overlap_factor)
