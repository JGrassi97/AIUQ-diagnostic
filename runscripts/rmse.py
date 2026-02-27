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


    
    # To add in config
    _TRUTH_PATH    = os.path.join(_HPCROOTDIR, 'truth', _START_TIME, 'truth_store.zarr')

    for var in output_vars:
        OUTPUT_BASE_PATH = f"{_OUTPUT_PATH}/{var}/{str(_RNG_KEY)}"
        _MODEL_FILE = f"{OUTPUT_BASE_PATH}/out-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-{var}.nc"
        _INCRE_FILE = f"{OUTPUT_BASE_PATH}/out-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-incrementers.nc"

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

        truth = xr.open_zarr(_TRUTH_PATH, chunks={"time":1})[var]
        # Set longitude from 0 to 360 to -180 to 180 and sort by longitude
        truth['longitude'] = (truth['longitude'] + 180) % 360 - 180
        truth = truth.sortby(truth.longitude)
        truth = truth.isel(level=~truth["level"].to_index().duplicated())
        truth = truth.interp(longitude=model.longitude, latitude=model.latitude, level=model.level, time=model.time, method='linear').sortby('level')

        # Compute incrementers
        err     = (model - truth).rename(f"{var}_err")                   # For the ME
        abs_err = np.abs(err).rename(f"{var}_absolute_error")   # For the MAE
        s_err   = (err ** 2).rename(f"{var}_squared_error")     # For the RMSE
        c_err = (err ** 3).rename(f"{var}_cubed_error")         # 
        q_err = (err ** 4).rename(f"{var}_quartic_error")       #
        y     = truth.rename(f"{var}_truth")                             #
        yhat  = model.rename(f"{var}_model")                             #
        y2    = (y ** 2).rename(f"{var}_truth_sq")            #   
        yhat2 = (yhat ** 2).rename(f"{var}_model_sq")         #
        yyhat = (y * yhat).rename(f"{var}_truth_x_model")     #

        # Counter
        n = xr.ones_like(err).rename(f"{var}_n")

        # Save incrementers
        ds_out = xr.merge([err, abs_err, s_err, c_err, q_err, y, yhat, y2, yhat2, yyhat, n])
        
        ds_out.to_netcdf(_INCRE_FILE)

        model.close()
        os.remove(_MODEL_FILE)                    # Remove model output

    
    truth.close()

    
    
if __name__ == "__main__":
    main()