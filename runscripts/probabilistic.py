"""

"""

# Built-in/Generics
import os
import shutil
import yaml

# Third party
import numpy as np
import xarray as xr
import zarr

# Local
from AIUQst_lib.functions import parse_arguments, read_config, normalize_out_vars
from AIUQst_lib.pressure_levels import check_pressure_levels
from AIUQst_lib.cards import read_ic_card, read_std_version
from AIUQst_lib.variables import reassign_long_names_units, define_ics_mappers


def _preprocess_one_file(ds):
    """Helper function to correctly set time dimension when ingesting"""
    vt0 = ds["valid_time"].isel(valid_time=0)
    ds = ds.expand_dims(time=[vt0.values])
    return ds


def _preprocess_longitude(ds):
    """Helper function to preprocess longitude and set it in [-180, 180)"""
    ds["longitude"] = (ds["longitude"] + 180) % 360 - 180
    ds = ds.sortby(ds.longitude)
    ds = ds.interpolate_na("longitude", method="nearest", fill_value="extrapolate")
    return ds


def crps_ensemble_xarray(da, truth):
    """
    Compute the CRPS for an ensemble forecast in xarray using:
    CRPS = E|X - y| - 0.5 E|X - X'|
    """
    # term1 = E|X - y|
    term1 = np.abs(truth - da).mean(dim="member")

    # term2 = 0.5 * E|X - X'|
    diffs = np.abs(da - da.rename(member="member2"))
    term2 = 0.5 * diffs.mean(dim=("member", "member2"))

    return term1 - term2


def _ensure_member_dim(da, member_name):
    """Add member dimension only when missing."""
    if "member" in da.dims:
        return da
    return da.expand_dims(member=[member_name])


def main() -> None:
    # Read config
    args = parse_arguments()
    config = read_config(args.config)

    _START_TIME = config.get("START_TIME", "")
    _END_TIME = config.get("END_TIME", "")
    _HPCROOTDIR = config.get("HPCROOTDIR", "")
    _OUT_VARS = config.get("OUT_VARS", [])
    _OUTPUT_PATH = config.get("OUTPUT_PATH", "")
    _MEMBERS = config.get("MEMBERS", "")

    output_vars = normalize_out_vars(_OUT_VARS)

    # Truth path
    _TRUTH_PATH = os.path.join(_HPCROOTDIR, "truth", _START_TIME, "truth_store.zarr")

    for var in output_vars:
        OUTPUT_BASE_PATH = f"{_OUTPUT_PATH}/{var}"
        _INCRE_FILE = f"{OUTPUT_BASE_PATH}/out-{_START_TIME}-{_END_TIME}-probabilistic.nc"

        # Load all generated members
        members = _MEMBERS.split()

        models = []
        for member in members:
            _MODEL_FILE = f"{OUTPUT_BASE_PATH}/{str(member)}/out-{_START_TIME}-{_END_TIME}-{member}-{var}.nc"
            ds = xr.open_dataset(_MODEL_FILE)

            if "lon" in ds.coords:
                ds = ds.rename({"lon": "longitude"})
            if "lat" in ds.coords:
                ds = ds.rename({"lat": "latitude"})

            ds = _preprocess_one_file(ds)
            ds = _preprocess_longitude(ds)

            target = {}
            if "temperature" in ds.data_vars:
                target["temperature"] = "t"
            if "u_component_of_wind" in ds.data_vars:
                target["u_component_of_wind"] = "u"
            if "v_component_of_wind" in ds.data_vars:
                target["v_component_of_wind"] = "v"
            if "geopotential" in ds.data_vars:
                target["geopotential"] = "z"
            ds = ds.rename(target)

            # Keep valid_time as the forecast time axis, and drop init-time (length=1) to avoid "dummy"
            da = ds[var]
            if "time" in da.dims and da.sizes["time"] == 1:
                da = da.isel(time=0, drop=True)
            da = da.rename({"valid_time": "time"}).expand_dims(member=[member])

            models.append(da)
            ds.close()

        model = xr.concat(models, dim="member")

        # Open truth and interpolate on model grid
        truth = xr.open_zarr(_TRUTH_PATH, chunks={"time": 1})[var]
        truth["longitude"] = (truth["longitude"] + 180) % 360 - 180
        truth = truth.sortby(truth.longitude)
        truth = truth.isel(level=~truth["level"].to_index().duplicated())
        truth = truth.interp(
            longitude=model.longitude,
            latitude=model.latitude,
            level=model.level,
            time=model.time,
            method="linear",
        ).sortby("level")

        # Ensemble spread statistics (independent of truth members)
        ens_std = model.std(dim="member", ddof=0).rename(f"{var}_std")
        ens_std_real = truth.std(dim="member", ddof=0).rename(f"{var}_std_truth") if "member" in truth.dims else None

        model_mean = model.mean(dim="member")
        model_std = model.std(dim="member", ddof=0)

        # This framework needs truth member spread to define the "spread contribution"
        if "member" not in truth.dims:
            raise ValueError(
                f"Truth for variable '{var}' has no 'member' dimension. "
                "Cannot separate bias / spread / residual contributions without truth ensemble spread."
            )

        truth_mean = truth.mean(dim="member")
        truth_std = truth.std(dim="member", ddof=0)

        eps = 1e-6
        model_std = xr.where(model_std < eps, eps, model_std)
        truth_std = xr.where(truth_std < eps, eps, truth_std)

        # 1. Forecast centered on truth mean: fixes only bias
        model_centred = (model - model_mean) + truth_mean

        # 2. Forecast with truth std but model mean: fixes only spread
        model_rescaled = ((model - model_mean) / model_std) * truth_std + model_mean

        # 3. Forecast with truth std and truth mean: fixes both bias and spread
        model_normalized = ((model - model_mean) / model_std) * truth_std + truth_mean

        n = xr.ones_like(ens_std).rename(f"{var}_n")

        crps_results = []

        # If truth has members, compute CRPS against each truth member
        truth_members_iter = truth["member"].values

        for m in truth_members_iter:
            truth_sel = truth.sel(member=m)
            truth_member_name = str(m)
            if "member" in truth_sel.dims:
                truth_sel = truth_sel.squeeze("member", drop=True)

            # Reference CRPS of truth ensemble against one truth member
            crps_truth = crps_ensemble_xarray(truth, truth_sel).rename(f"{var}_crps_truth").expand_dims(
                member=[truth_member_name]
            )

            # Raw and counterfactual CRPS
            crps = crps_ensemble_xarray(model, truth_sel).rename(f"{var}_crps").expand_dims(
                member=[truth_member_name]
            )
            crps_centered = crps_ensemble_xarray(model_centred, truth_sel).rename(f"{var}_crps_centered").expand_dims(
                member=[truth_member_name]
            )
            crps_rescaled = crps_ensemble_xarray(model_rescaled, truth_sel).rename(f"{var}_crps_rescaled").expand_dims(
                member=[truth_member_name]
            )
            crps_normalized = crps_ensemble_xarray(model_normalized, truth_sel).rename(f"{var}_crps_normalized").expand_dims(
                member=[truth_member_name]
            )

            # Symmetric attribution of the explained discrepancy
            bias_contrib = (
                0.5 * ((crps - crps_centered) + (crps_rescaled - crps_normalized))
            ).rename(f"{var}_crps_bias_contrib")

            spread_contrib = (
                0.5 * ((crps - crps_rescaled) + (crps_centered - crps_normalized))
            ).rename(f"{var}_crps_spread_contrib")

            # Unexplained remainder after correcting mean and spread
            residual_contrib = crps_normalized.rename(f"{var}_crps_residual_contrib")

            # Optional normalized fractions of total discrepancy
            total_contrib = (bias_contrib + spread_contrib + residual_contrib)
            total_safe = xr.where(np.abs(total_contrib) < eps, np.nan, total_contrib)

            bias_frac = (bias_contrib / total_safe).rename(f"{var}_crps_bias_frac")
            spread_frac = (spread_contrib / total_safe).rename(f"{var}_crps_spread_frac")
            residual_frac = (residual_contrib / total_safe).rename(f"{var}_crps_residual_frac")

            crps_results.extend([
                crps_truth,
                crps,
                crps_centered,
                crps_rescaled,
                crps_normalized,
                _ensure_member_dim(bias_contrib, truth_member_name),
                _ensure_member_dim(spread_contrib, truth_member_name),
                _ensure_member_dim(residual_contrib, truth_member_name),
                _ensure_member_dim(bias_frac, truth_member_name),
                _ensure_member_dim(spread_frac, truth_member_name),
                _ensure_member_dim(residual_frac, truth_member_name),
            ])

        crps_all = xr.merge(crps_results, join="outer")

        merge_list = [
            ens_std,
            n,
            crps_all,
        ]
        if ens_std_real is not None:
            merge_list.insert(1, ens_std_real)

        ds_out = xr.merge(merge_list)
        ds_out.to_netcdf(_INCRE_FILE)

        model.close()
        truth.close()


if __name__ == "__main__":
    main()