# AIUQ-Diagnostic

AIUQ-Diagnostic extends the job graph of **AIUQ-Engine**, enabling the computation of diagnostic metrics on top of AI-based forecast inference workflows.

AIUQ-Engine is currently updated to version [v0.1.1](https://github.com/JGrassi97/AIUQ/tree/v0.1.1) Please refer to that version’s documentation for the list of available models and initial conditions (ICs).

---
AIUQ-Diagnostic expands the standard inference pipeline by adding **streaming diagnostic metric computation**.

Instead of storing full forecast fields, the system:
- Computes metrics on-the-fly
- Stores only incremental counters
- Saves final aggregated results

This design allows:
- Evaluation of very large AI model ensembles
- Long simulation periods
- Minimal storage requirements

All metrics are computed:
- At each **grid point**
- For each **lead time**

Note that, during aggregation, the **initialization time dimension is removed**.

---

#### Deterministic Metrics

Deterministic metrics compare:
- A **single forecast realization** against the corresponding **ground truth**

If the ground truth contains multiple members, metrics are computed against **all members**

Currently supported metrics:
- Mean Error (ME)
- Mean Absolute Error (MAE)
- Root Mean Square Error (RMSE)

#### Probabilistic Metrics

Probabilistic metrics require:
- An **ensemble of forecast realizations**

If the ground truth contains multiple members, metrics are computed across **all truth members**

Currently supported metrics:
- Ensemble spread
- Continuosly Ranked Probability Score

---

## New features in v0.1.0

- Configurable truth members for EERIE workflows via `EERIE.MEMBERS`.
- Deterministic pipeline support for `REDUCE` mode.
- Probabilistic robustness improvements for CRPS processing (safe member-dimension handling).
- Simplified probabilistic outputs focused on core and counterfactual CRPS fields.
- Ground-truth copy is now resilient to missing source files (warn and skip instead of failing the job).
- AIUQ-engine submodule remains aligned to v0.1.1.


## Usage 

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

  REDUCE: "false"       # true / false
  
  # Here reported from https://github.com/PCMDI/cmip6-cmor-tables/blob/087fe45d21c082e28723e0f930e4266abe91b853/Tables/CMIP6_coordinate.json#L1640

PATHS:
  SUPPORT_FOLDER: /gpfs/scratch/ehpc536/AIUQ
  SIF_FOLDER: "%PATHS.SUPPORT_FOLDER%/sif"

PLATFORM:
  NAME: MARENOSTRUM5  # FELIPE / MARENOSTRUM5
  USER_CODE: ...

# If you use eerie
EERIE:
  MEMBERS: "1 2 3"
  HOST: ...
  PATH: ...
```


### Developers guide
#### Update the engine:
```
git submodule update --remote --merge  
```
