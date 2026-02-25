"""

"""

# Built-in/Generics
import os 
import shutil
import yaml

# Third party
import gcsfs
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
    _HPCROOTDIR     = config.get("HPCROOTDIR", "")
    _OUT_VARS       = config.get("OUT_VARS", [])
    _IC             = config.get("IC_NAME", "")
    _STD_VERSION    = config.get("STD_VERSION", "")
    _OUT_LEVS       = config.get("OUT_LEVS", "")

    if _OUT_LEVS != 'original':
        desired_levels = [
            int(plev)
            for plev in _OUT_LEVS.strip('[]').split(',')
        ]

    # IC settings
    ic_card = read_ic_card(_HPCROOTDIR, _IC)
    standard_dict = read_std_version(_HPCROOTDIR, _STD_VERSION)

    # Create the mappers between model requirement and IC variables
    ic_names, rename_dict, long_names_dict, units_dict, missing_vars = define_ics_mappers(
        ic_card['variables'], 
        standard_dict['variables']['data']
        )
    
    output_vars = normalize_out_vars(_OUT_VARS)
    rename_dict = {k : v for k, v in rename_dict.items() if k in output_vars}
    long_names_dict = {k : v for k, v in long_names_dict.items() if k in list(rename_dict.values())}
    units_dict = {k : v for k, v in units_dict.items() if k in list(rename_dict.values())}

    # To add in config
    _TRUTH_PATH_TEMP    = os.path.join(_HPCROOTDIR, 'truth', _START_TIME, 'truth_store_temp.zarr')
    _TRUTH_PATH    = os.path.join(_HPCROOTDIR, 'truth', _START_TIME, 'truth_store.zarr')

    truth_temp = xr.open_zarr(_TRUTH_PATH_TEMP, chunks={"time":48})

    truth_temp = (
        truth_temp
        .rename(rename_dict)
        .resample(time="1D").mean()
        .pipe(reassign_long_names_units, long_names_dict, units_dict)
    )

    # # Adjust longitudes to -0 - 360
    truth_temp['longitude'] = truth_temp['longitude'] % 360
    truth_temp = truth_temp.sortby('longitude')
    
    # Final part - Saving in zarr
    final = truth_temp.chunk({"time": 1})        # Chunking by time for efficient access

    shutil.rmtree(                          # Remove existing data if any - avoid conflicts
        _TRUTH_PATH,
        ignore_errors=True)
    
    os.makedirs(_TRUTH_PATH, exist_ok=True)  # Ensure the directory existss
    
    final.to_zarr(                          # Save to zarr format - using version 2
        f"{_TRUTH_PATH}",                   # Zarr version 3 has some issues with BytesBytesCodec
        mode="w",                           # See https://github.com/pydata/xarray/issues/10032 as reference    
        zarr_format=2)
    
    truth_temp.close()  # Close the temporary zarr store to free up resources

    shutil.rmtree(                          # Remove existing data if any - avoid conflicts
        _TRUTH_PATH_TEMP,
        ignore_errors=True)
    
if __name__ == "__main__":
    main()