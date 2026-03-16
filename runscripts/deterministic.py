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
    """Helper function to preprocess the longitude and set in -180/180"""
    ds["longitude"] = (ds["longitude"] + 180) % 360 - 180
    ds = ds.sortby(ds.longitude)
    ds = ds.interpolate_na("longitude", method="nearest", fill_value="extrapolate")
    return ds


def main() -> None:
    # Read config
    args = parse_arguments()
    config = read_config(args.config)

    _START_TIME = config.get("START_TIME", "")
    _END_TIME = config.get("END_TIME", "")
    _HPCROOTDIR = config.get("HPCROOTDIR", "")
    _OUT_VARS = config.get("OUT_VARS", [])
    _OUTPUT_PATH = config.get("OUTPUT_PATH", "")
    _RNG_KEY = config.get("RNG_KEY", "")

    output_vars = normalize_out_vars(_OUT_VARS)

    # To add in config
    _TRUTH_PATH = os.path.join(_HPCROOTDIR, "truth", _START_TIME, "truth_store.zarr")

    for var in output_vars:
        OUTPUT_BASE_PATH = f"{_OUTPUT_PATH}/{var}/{str(_RNG_KEY)}"
        _MODEL_FILE = f"{OUTPUT_BASE_PATH}/out-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-{var}.nc"
        _INCRE_FILE = f"{OUTPUT_BASE_PATH}/out-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-deterministic.nc"

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

        # Keep only the variable of interest
        model = ds[var]

        # Remove the init-time dimension if it is singleton, without using "dummy"
        if "time" in model.dims and model.sizes["time"] == 1:
            model = model.isel(time=0, drop=True)

        # Use valid_time as the forecast time axis
        if "valid_time" in model.dims:
            model = model.rename({"valid_time": "time"})

        truth = xr.open_zarr(_TRUTH_PATH, chunks={"time": 1})[var]

        # Set longitude from 0-360 to -180-180 and sort by longitude
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

        results = []

        if "member" in truth.dims:
            members_iter = truth["member"].values
        else:
            members_iter = [None]

        for m in members_iter:
            if m is None:
                new_name = f"deterministic_{_RNG_KEY}"
                truth_sel = truth
            else:
                new_name = f"{m}_{_RNG_KEY}"
                truth_sel = truth.sel(member=m)
                if "member" in truth_sel.dims:
                    truth_sel = truth_sel.squeeze("member", drop=True)

            err = (model - truth_sel).rename(f"{var}_err").expand_dims(member=[new_name])

            abs_err = np.abs(err).rename(f"{var}_absolute_error")
            s_err = (err ** 2).rename(f"{var}_squared_error")
            c_err = (err ** 3).rename(f"{var}_cubed_error")
            q_err = (err ** 4).rename(f"{var}_quartic_error")

            n = xr.ones_like(err).rename(f"{var}_n")

            ds_out_one = xr.merge([err, abs_err, s_err, c_err, q_err, n])
            results.append(ds_out_one)

        ds_out = xr.concat(results, dim="member")
        ds_out.to_netcdf(_INCRE_FILE)

        ds.close()
        os.remove(_MODEL_FILE)

    truth.close()


if __name__ == "__main__":
    main()