# AIUQ-diagnostic
Diagnostic system for uncertainty quantification of AI-based weather forecasting models.




```
autosubmit expid \
  --description "AIUQ-diagnostic" \
  --HPC MareNostrum5ACC \
  --minimal_configuration \
  --git_as_conf conf/bootstrap/ \
  --git_repo https://github.com/JGrassi97/AIUQ-diagnostic.git \
  --git_branch main
```


### Update the engine:
```
git submodule update --remote --merge  
```

### Create the config.yml
```
# <EXPID>/conf/main.yml

MODEL:
  # Main settings
  NAME: aifs                                        # aifs / neuralgcm / aurora
  CHECKPOINT_NAME: aifs-ens-crps-1.0.ckpt           # checkpoint name as written in the table above
  ICS: era5                                         # eerie / era5
  USE_LOCAL_ICS: "false"                            # true / false

# See autosubmit documentation
EXPERIMENT:
  MEMBERS: "1 2"
  CHUNKSIZEUNIT: day
  DATELIST: 198501[01] # 198412[10 20 30] 198501[10 20 30] 198502[10 20]
  CHUNKSIZE: 2
  NUMCHUNKS: 1
  CALENDAR: standard

  # The following fields are not part of standard Autosubmit experiment
  OUT_VARS:       
    - t
    - z
  OUT_FREQ: daily         # original / daily
  OUT_RES: "1"              # original / 0.25 / 0.5 / 1 / 1.5 / 2
  OUT_LEVS: [1000, 850, 700, 500, 250, 100]              # List of values in hPa or 'original' - 
  
  # Here reported from https://github.com/PCMDI/cmip6-cmor-tables/blob/087fe45d21c082e28723e0f930e4266abe91b853/Tables/CMIP6_coordinate.json#L1640

PATHS:
  SUPPORT_FOLDER: /gpfs/scratch/ehpc536/AIUQ
  SIF_FOLDER: "%PATHS.SUPPORT_FOLDER%/sif"

PLATFORM:
  NAME: MARENOSTRUM5  # FELIPE / MARENOSTRUM5

# If you use eerie
EERIE:
  HOST: ...
  PATH: ...
```