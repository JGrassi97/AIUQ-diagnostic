import xarray as xr
import os
import numpy as np
import matplotlib.pyplot as plt

import sys

from AIUQst_lib.functions import parse_arguments, read_config, normalize_out_vars


def _preprocess_one_file(ds):
        """Helper function to correctly set time dimension when ingesting"""

        vt0 = ds["valid_time"].isel(valid_time=0)
        ds = ds.expand_dims(time=[vt0.values])
        return ds


def _preprocess_longitude(ds):
        ds['longitude'] = (ds['longitude'] + 180) % 360 - 180
        ds = ds.sortby(ds.longitude)
        ds = ds.interpolate_na('longitude', method='nearest', fill_value='extrapolate')
        return ds

if __name__ == "__main__":
    
    # Read config
    args = parse_arguments()
    config = read_config(args.config)

    _OUTPUT_PATH        = config.get("OUTPUT_PATH", "")
    _OUT_VARS           = config.get("OUT_VARS", [])
    _OUT_FREQ           = config.get("OUT_FREQ", "")
    _OUT_RES            = config.get("OUT_RES", "")
    _OUT_LEVS           = config.get("OUT_LEVS", "")
    _RNG_KEY            = config.get("RNG_KEY", 1)
    _START_TIME         = config.get("START_TIME", "")
    _END_TIME           = config.get("END_TIME", "")

    # Format output variables and select
    output_vars = normalize_out_vars(_OUT_VARS)
    for var in output_vars:

        OUTPUT_BASE_PATH = f"{_OUTPUT_PATH}/{var}/{str(_RNG_KEY)}"
        os.makedirs(OUTPUT_BASE_PATH, exist_ok=True)
        OUTPUT_FILE = f"{OUTPUT_BASE_PATH}/ngcm-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-{var}.nc"
        
        dataset = xr.open_dataset(OUTPUT_FILE, preprocess=_preprocess_one_file)
        dataset = _preprocess_longitude(dataset)

        image_path = f"{OUTPUT_BASE_PATH}/ngcm-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-{var}.png"
        dataset[var].isel(time=0).plot()
        plt.savefig(image_path)
        plt.close()