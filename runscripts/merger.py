"""

"""

# Built-in/Generics
import os
import uuid

# Third party
import numpy as np
import xarray as xr

# Local
from AIUQst_lib.functions import parse_arguments, read_config, normalize_out_vars


def safe_write_netcdf(ds: xr.Dataset, path: str) -> None:
    tmp = f"{path}.tmp-{uuid.uuid4().hex}"
    # scrivi su tmp
    ds.to_netcdf(tmp, mode="w")
    # rimpiazza atomico
    os.replace(tmp, path)

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
            incre_file = f"{base}/out-{_START_TIME}-{_END_TIME}-{key}-incrementers.nc"  # (nome tuo)

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



        # aggiorna counter su disco
        if not os.path.exists(counter_file):
            safe_write_netcdf(ds_all, counter_file)
        else:
            ds_counter = xr.open_dataset(counter_file)
            ds_counter, ds_all = xr.align(ds_counter, ds_all, join="outer")
            ds_new = ds_counter.fillna(0) + ds_all.fillna(0)
            ds_counter.close()

            safe_write_netcdf(ds_new, counter_file)


if __name__ == "__main__":
    main()