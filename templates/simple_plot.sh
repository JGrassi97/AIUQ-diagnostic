HPCROOTDIR=%HPCROOTDIR%
EXPID=%DEFAULT.EXPID%
JOBNAME=%JOBNAME%

SIF_PATH=%PATHS.SIF_FOLDER%/image_eerie.sif

JOBNAME_WITHOUT_EXPID=$(echo ${JOBNAME} | sed 's/^[^_]*_//')

logs_dir=${HPCROOTDIR}/LOG_${EXPID}
configfile=$logs_dir/config_${JOBNAME_WITHOUT_EXPID}
PLATFORM_NAME=%PLATFORM.NAME%

OUTPUT_PATH=%HPCROOTDIR%/outputs
GRID_FILE=%PATHS.SUPPORT_FOLDER%/aifs_grid.txt

# Load Singularity module only on MareNostrum5
if [ "$PLATFORM_NAME" = "MARENOSTRUM5" ]; then
    ml singularity
fi

singularity exec --nv \
    --bind $HPCROOTDIR \
    --env HPCROOTDIR=$HPCROOTDIR \
    --env configfile=$configfile \
    ${SIF_PATH} \
    python3 $HPCROOTDIR/runscripts/simple_plot.py -c $configfile