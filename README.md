# AIUQ-diagnostic

AIUQ-diagnostic inheretis the job graph from AIUQ-engine, which allows the inference with AI models. Right now, AIUQ-engine is updated to the version [v0.1.1](https://github.com/JGrassi97/AIUQ/tree/v0.1.1), please refer to the version documentation for a list of models/ics available. The jobs graph is here exapanded allowing to compute diagnostic metrics in streaming, and saving only the counters and final results. In this way, it is possible to evaluate very large ensemble of AI models for long simulations with few archiviation space.

The metrics described above are computed for each grid point and and lead time, but the initialization time dimension is lost during the aggregation.

### Deterministic metrics
These metrics are computed comparing the single forecast realization with the ground truth. If the ground truth is made of multiple members, these metrics are computed over all the members.

### Probabilistic metrics
These metrics require an ensemble of realization to be computed. If the ground truth is made of multiple members, these metrics are computed over all the members.

```
autosubmit expid \
  --description "AIUQ-diagnostic" \
  --HPC MareNostrum5ACC \
  --minimal_configuration \
  --git_as_conf conf/bootstrap/ \
  --git_repo https://github.com/JGrassi97/AIUQ-diagnostic.git \
  --git_branch main
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
  USER_CODE: ...

# If you use eerie
EERIE:
  HOST: ...
  PATH: ...
```


### Developers guide
#### Update the engine:
```
git submodule update --remote --merge  
```
