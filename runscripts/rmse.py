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
        ds['longitude'] = (ds['longitude'] + 180) % 360 - 180
        ds = ds.sortby(ds.longitude)
        ds = ds.interpolate_na('longitude', method='nearest', fill_value='extrapolate')
        return ds

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
    _OUTPUT_PATH        = config.get("OUTPUT_PATH", "")
    _RNG_KEY            = config.get("RNG_KEY", "")

    if _OUT_LEVS != 'original':
        desired_levels = [
            int(plev)
            for plev in _OUT_LEVS.strip('[]').split(',')
        ]

    output_vars = normalize_out_vars(_OUT_VARS)

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
    _TRUTH_PATH    = os.path.join(_HPCROOTDIR, 'truth', _START_TIME, 'truth_store.zarr')
    truth = xr.open_zarr(_TRUTH_PATH, chunks={"time":1})
    # Set longitude from 0 to 360 to -180 to 180 and sort by longitude
    truth['longitude'] = (truth['longitude'] + 180) % 360 - 180
    truth = truth.sortby(truth.longitude)
    truth = truth.isel(level=~truth["level"].to_index().duplicated())

    for var in output_vars:

        OUTPUT_BASE_PATH = f"{_OUTPUT_PATH}/{var}/{str(_RNG_KEY)}"
        _MODEL_FILE = f"{OUTPUT_BASE_PATH}/aifs-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-{var}.nc"
        _INCRE_FILE = f"{OUTPUT_BASE_PATH}/aifs-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-squared_error.nc"

        model = xr.open_dataset(_MODEL_FILE)

        if 'lon' in model.coords:
            model = model.rename({'lon': 'longitude'})
        if 'lat' in model.coords:
            model = model.rename({'lat': 'latitude'})
        
        model = _preprocess_one_file(model)
        model = _preprocess_longitude(model)

        lead_time = model['valid_time'] - model['time']
        lead_time = lead_time.astype('timedelta64[h]') / np.timedelta64(1, 'h')

        model = model.rename({'time':'dummy'}).drop_vars(['dummy']).rename({'valid_time': 'time'})[var]

        truth = truth.interp(longitude=model.longitude, latitude=model.latitude, level=model.level, time=model.time, method='linear').sortby('level')

        # Compute incrementer
        s_err = np.square(model - truth)

        # Save incrementer
        s_err.to_netcdf(_INCRE_FILE)
    
    truth.close()


    shutil.rmtree(                          # Remove truth
        _TRUTH_PATH,
        ignore_errors=True)
    
    
if __name__ == "__main__":
    main()