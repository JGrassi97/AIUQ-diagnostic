import xarray as xr
import os
import numpy as np

import sys

from AIUQst_lib.functions import parse_arguments, read_config, normalize_out_vars



if __name__ == "__main__":

        # Read config
        args = parse_arguments()
        config = read_config(args.config)

        _OUTPUT_PATH        = config.get("OUTPUT_PATH", "")

        all_files = os.listdir(_OUTPUT_PATH)

        # Select only nc
        all_files = [file for file in all_files if file.endswith('.nc')]

        # Open and merge
        with xr.open_mfdataset([f"{_OUTPUT_PATH}/{file}" for file in all_files], combine='by_coords', engine='netcdf4') as dataset:
                dataset.to_zarr(f"{_OUTPUT_PATH}/ngcm-diagnostic.zarr", consolidated=True)

        # Remove individual files
        for file in all_files:
                os.remove(f"{_OUTPUT_PATH}/{file}")

        