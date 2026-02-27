# """

# """

# # Built-in/Generics
# import os 
# import shutil
# import yaml

# # Third party
# import numpy as np
# import xarray as xr
# import zarr

# # Local
# from AIUQst_lib.functions import parse_arguments, read_config, normalize_out_vars
# from AIUQst_lib.pressure_levels import check_pressure_levels
# from AIUQst_lib.cards import read_ic_card, read_std_version
# from AIUQst_lib.variables import reassign_long_names_units, define_ics_mappers


# def main() -> None:

#         # Read config
#         args = parse_arguments()
#         config = read_config(args.config)

#         _START_TIME     = config.get("START_TIME", "")
#         _END_TIME       = config.get("END_TIME", "")
#         _OUT_VARS       = config.get("OUT_VARS", [])
#         _OUTPUT_PATH        = config.get("OUTPUT_PATH", "")
#         #_RNG_KEY            = config.get("RNG_KEY", "")
#         _MEMBERS             = config.get("MEMBERS", "")

#         output_vars = normalize_out_vars(_OUT_VARS)

#         dat_list = []
#         for key in _MEMBERS.split():
#                 for var in output_vars:

#                         OUTPUT_BASE_PATH = f"{_OUTPUT_PATH}/{var}/{str(key)}"
#                         _INCRE_FILE = f"{OUTPUT_BASE_PATH}/aifs-{_START_TIME}-{_END_TIME}-{key}-squared_error.nc"
#                         _COUNTER_FILE = f"{_OUTPUT_PATH}/rmse-counter.nc"

#                         rmse = xr.open_dataset(_INCRE_FILE)[var]

#                         # Add member dimension
#                         rmse = rmse.expand_dims(member=[str(key)])

#                         # Change dat time with increasing number of days
#                         lead_time = np.arange(0, len(rmse.time.dt.day))

#                         rmse['time'] = lead_time

#                         dat_list.append(rmse)
#                         os.remove(_INCRE_FILE)

#         dat_list = xr.merge(dat_list)

#         if not os.path.exists(_COUNTER_FILE):
#                 dats = dat_list
#                 dats.to_netcdf(_COUNTER_FILE)

#         else:
#                 dats = xr.open_dataset(_COUNTER_FILE)
#                 dats_new = dats + dat_list
#                 dats.close()
#                 dats_new.to_netcdf(_COUNTER_FILE)

    
# if __name__ == "__main__":
#     main()



# Built-in/Generics
import os

# Third party
import numpy as np
import xarray as xr

# Local
from AIUQst_lib.functions import parse_arguments, read_config, normalize_out_vars


def _to_lead_time(ds: xr.Dataset) -> xr.Dataset:
    """
    Se vuoi trasformare time in lead_time (0..T-1) in modo consistente.
    Meglio farlo una volta sola qui, invece di patcharlo su singoli DataArray.
    """
    if "time" in ds.coords:
        lt = xr.DataArray(np.arange(ds.sizes["time"]), dims=("time",), name="lead_time")
        ds = ds.assign_coords(lead_time=lt).swap_dims({"time": "lead_time"}).drop_vars("time")
    return ds


def main() -> None:
    args = parse_arguments()
    config = read_config(args.config)

    _START_TIME   = config.get("START_TIME", "")
    _END_TIME     = config.get("END_TIME", "")
    _OUT_VARS     = config.get("OUT_VARS", [])
    _OUTPUT_PATH  = config.get("OUTPUT_PATH", "")
    _MEMBERS      = config.get("MEMBERS", "")

    output_vars = normalize_out_vars(_OUT_VARS)

    # Un counter per var (molto più semplice e meno rischi di collisioni tra var)
    # Se vuoi un unico file per tutte le var, si può fare, ma serve nomi univoci.
    for var in output_vars:
        counter_file = f"{_OUTPUT_PATH}/{var}/metrics-counter.nc"

        ds_members = []
        for key in _MEMBERS.split():
            base = f"{_OUTPUT_PATH}/{var}/{str(key)}"
            incre_file = f"{base}/aifs-{_START_TIME}-{_END_TIME}-{key}-squared_error.nc"  # (nome tuo)
            # ^ Consiglio: rinominalo in "...-incrementers.nc" per chiarezza

            if not os.path.exists(incre_file):
                continue

            ds = xr.open_dataset(incre_file)

            # aggiungi dimensione member
            ds = ds.expand_dims(member=[str(key)])

            # se vuoi lead_time al posto di time (opzionale)
            ds = _to_lead_time(ds)

            ds_members.append(ds)

            ds.close()
            os.remove(incre_file)

        if not ds_members:
            continue

        # concat su member: dataset shape (member, lead_time/time, level, lat, lon, ...)
        ds_all = xr.concat(ds_members, dim="member")

        # somma su member per aggiornare il counter
        ds_batch = ds_all.sum(dim="member")

        # aggiorna counter su disco
        if not os.path.exists(counter_file):
            ds_batch.to_netcdf(counter_file)
        else:
            ds_counter = xr.open_dataset(counter_file)
            # allineamento coords per sicurezza
            ds_counter, ds_batch = xr.align(ds_counter, ds_batch, join="outer")
            ds_new = ds_counter.fillna(0) + ds_batch.fillna(0)
            ds_counter.close()
            ds_new.to_netcdf(counter_file)

        ds_all.close()
        ds_batch.close()


if __name__ == "__main__":
    main()