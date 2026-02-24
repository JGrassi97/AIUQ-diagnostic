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

        # Combine path with file names
        all_files = [os.path.join(_OUTPUT_PATH, file) for file in all_files]

        # Select only nc
        all_files = [file for file in all_files if file.endswith('.nc')]

        ds = xr.open_mfdataset(
                all_files,
                combine="by_coords",
                engine="netcdf4",
                data_vars="all",
                coords="all",
                join="outer",
                compat="override",
                combine_attrs="override",
                )

        print("DATA_VARS:", list(ds.data_vars))
        print("COORDS:", list(ds.coords))

        ds.to_zarr(os.path.join(_OUTPUT_PATH, "ngcm-diagnostic.zarr"), consolidated=True)
        ds.close()

        # Remove individual files
        for file in all_files:
                os.remove(f"{_OUTPUT_PATH}/{file}")