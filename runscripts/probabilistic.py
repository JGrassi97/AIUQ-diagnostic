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
        """ Helper function to preprocess the longitude and set in -180/180"""

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
    _OUTPUT_PATH    = config.get("OUTPUT_PATH", "")
    _RNG_KEY        = config.get("RNG_KEY", "")

    output_vars = normalize_out_vars(_OUT_VARS)

    # To add in config
    _TRUTH_PATH    = os.path.join(_HPCROOTDIR, 'truth', _START_TIME, 'truth_store.zarr')

    for var in output_vars:

        OUTPUT_BASE_PATH = f"{_OUTPUT_PATH}/{var}/{str(_RNG_KEY)}"
        _MODEL_FILE = f"{OUTPUT_BASE_PATH}/out-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-{var}.nc"
        _INCRE_FILE = f"{OUTPUT_BASE_PATH}/out-{_START_TIME}-{_END_TIME}-{_RNG_KEY}-deterministic.nc"

        model = xr.open_dataset(_MODEL_FILE)

        if 'lon' in model.coords:
            model = model.rename({'lon': 'longitude'})
        if 'lat' in model.coords:
            model = model.rename({'lat': 'latitude'})
        
        model = _preprocess_one_file(model)
        model = _preprocess_longitude(model)

        target = {}
        if 'temperature' in model.data_vars:
            target['temperature'] = 't'
        if 'u_component_of_wind' in model.data_vars:
            target['u_component_of_wind'] = 'u'
        if 'v_component_of_wind' in model.data_vars:
            target['v_component_of_wind'] = 'v'
        if 'geopotential' in model.data_vars:
            target['geopotential'] = 'z'

        model = model.rename(target)

        lead_time = model['valid_time'] - model['time']
        lead_time = lead_time.astype('timedelta64[h]') / np.timedelta64(1, 'h')

        model = model.rename({'time':'dummy'}).drop_vars(['dummy']).rename({'valid_time': 'time'})[var]

        truth = xr.open_zarr(_TRUTH_PATH, chunks={"time":1})[var]

        # # If truth has a member dimension, we need to do member average
        # if 'member' in truth.dims:
        #     truth = truth.mean(dim='member')

        # Set longitude from 0 to 360 to -180 to 180 and sort by longitude
        truth['longitude'] = (truth['longitude'] + 180) % 360 - 180
        truth = truth.sortby(truth.longitude)
        truth = truth.isel(level=~truth["level"].to_index().duplicated())
        truth = truth.interp(longitude=model.longitude, latitude=model.latitude, level=model.level, time=model.time, method='linear').sortby('level')


        results = []

        if "member" in truth.dims:
            members_iter = truth["member"].values
        else:
            members_iter = [None]   # caso deterministico: un solo giro

        for m in members_iter:

            if m is None:
                new_name = f"deterministic_{_RNG_KEY}"
                truth_sel = truth
            else:
                new_name = f"{m}_{_RNG_KEY}"
                truth_sel = truth.sel(member=m)
                # qui puoi fare squeeze solo se davvero rimane member di size=1
                if "member" in truth_sel.dims:
                    truth_sel = truth_sel.squeeze("member", drop=True)

            # ora truth_sel NON deve avere member, così err non eredita member
            err = (model - truth_sel).rename(f"{var}_err").expand_dims(member=[new_name])

            abs_err = np.abs(err).rename(f"{var}_absolute_error")
            s_err   = (err ** 2).rename(f"{var}_squared_error")
            c_err   = (err ** 3).rename(f"{var}_cubed_error")
            q_err   = (err ** 4).rename(f"{var}_quartic_error")

            n = xr.ones_like(err).rename(f"{var}_n")

            ds = xr.merge([err, abs_err, s_err, c_err, q_err, n])
            results.append(ds)

        ds_out = xr.concat(results, dim="member")
        ds_out.to_netcdf(_INCRE_FILE)

        model.close()
        os.remove(_MODEL_FILE)                    # Remove model output

    
    truth.close()

    
    
if __name__ == "__main__":
    main()