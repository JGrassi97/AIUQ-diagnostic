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


def main() -> None:

        # Read config
        args = parse_arguments()
        config = read_config(args.config)

        _START_TIME     = config.get("START_TIME", "")
        _END_TIME       = config.get("END_TIME", "")
        _OUT_VARS       = config.get("OUT_VARS", [])
        _OUTPUT_PATH        = config.get("OUTPUT_PATH", "")
        _RNG_KEY            = config.get("RNG_KEY", "")

        output_vars = normalize_out_vars(_OUT_VARS)

        dat_list = []
        for var in output_vars:

                OUTPUT_BASE_PATH = f"{_OUTPUT_PATH}/{var}/{str(_RNG_KEY)}"
                _INCRE_FILE = f"{OUTPUT_BASE_PATH}/aifs-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-squared_error.nc"
                _COUNTER_FILE = f"{_OUTPUT_PATH}/rmse-counter.nc"

                rmse = xr.open_dataset(_INCRE_FILE)[var]

                # Add member dimension
                rmse = rmse.expand_dims(member=[str(_RNG_KEY)])

                # Change dat time with increasing number of days
                lead_time = np.arange(0, len(rmse.time.dt.day))

                rmse['time'] = lead_time

                dat_list.append(rmse)
                os.remove(_INCRE_FILE)

        dat_list = xr.merge(dat_list)

        if not os.path.exists(_COUNTER_FILE):
                dats = dat_list
                dats.to_netcdf(_COUNTER_FILE)

        else:
                dats = xr.open_dataset(_COUNTER_FILE)
                dats_new = dats + dat_list
                dats.close()
                dats_new.to_netcdf(_COUNTER_FILE)

    
if __name__ == "__main__":
    main()