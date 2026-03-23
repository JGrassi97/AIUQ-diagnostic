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
    _EERIE_MEMBERS  = os.environ.get("EERIE_MEMBERS", "1 2 3")

    if _OUT_LEVS != 'original':
        desired_levels = [
            int(plev)
            for plev in _OUT_LEVS.strip('[]').split(',')
        ]

    # IC settings
    ic_card = read_ic_card(_HPCROOTDIR, _IC)
    standard_dict = read_std_version(_HPCROOTDIR, _STD_VERSION)

    # Temporary fix for naming inconsistencies
    output_vars = normalize_out_vars(_OUT_VARS)

    # To add in config
    _TRUTH_PATH_TEMP    = os.path.join(_HPCROOTDIR, 'truth', 'temp' , _START_TIME)
    _TRUTH_PATH    = os.path.join(_HPCROOTDIR, 'truth', _START_TIME, 'truth_store.zarr')
    eerie_members = _EERIE_MEMBERS.split()

    data = []
    for var in output_vars:
        for member in eerie_members:
            path = f'{_TRUTH_PATH_TEMP}/{var}/{member}'

            files = os.listdir(path)
            files = [f for f in files if f.endswith('.nc')]
            files = [os.path.join(path, f) for f in files]

            valid_files = []
            for f in files:
                try:
                    # Force a full read to catch corrupted files early.
                    with xr.open_dataset(f) as ds:
                        ds.load()
                    valid_files.append(f)
                except Exception as e:
                    print(f"[WARNING] File corrotto saltato: {f} ({e})")

            if not valid_files:
                print(f"[WARNING] Nessun file valido per {var} membro {member}")
                continue

            dat = xr.open_mfdataset(valid_files)
            dat = dat.sel(isobaricInhPa=desired_levels)
            dat = dat.rename({'isobaricInhPa': 'level'})
            dat = dat.drop_vars('time_bnds')

            # Add member dimension
            dat = dat.expand_dims('member').assign_coords(member=[member])
            data.append(dat)

    data = xr.merge(data)

    # # Adjust longitudes to -0 - 360
    data['longitude'] = data['longitude'] % 360
    data = data.sortby('longitude')
    
    # Final part - Saving in zarr
    final = data.chunk({"time": 1})        # Chunking by time for efficient access

    shutil.rmtree(                          # Remove existing data if any - avoid conflicts
        _TRUTH_PATH,
        ignore_errors=True)
    
    os.makedirs(_TRUTH_PATH, exist_ok=True)  # Ensure the directory existss
    
    final.to_zarr(                          # Save to zarr format - using version 2
        f"{_TRUTH_PATH}",                   # Zarr version 3 has some issues with BytesBytesCodec
        mode="w",                           # See https://github.com/pydata/xarray/issues/10032 as reference    
        zarr_format=2)
    
    data.close()  # Close the temporary zarr store to free up resources

    shutil.rmtree(                          # Remove existing data if any - avoid conflicts
        _TRUTH_PATH_TEMP,
        ignore_errors=True)
    
if __name__ == "__main__":
    main()