# TA-software
Software for the transient absorption setup.

### pyTA ###
Measurement setup and data acquisition.

_Thanks to the OE group at Cambridge for some of the original code._

### hdf5-converter ###
Conversion of data files (.hdf5) to useful things.

### usage ###
Open an anaconda command prompt and `cd` to the TA-software folder. Then activate the environment and launch the software by running:
```bat
conda activate pyTA
cd pyTA
python pyTA.py
```
Then to use the hdf5 conversion tool, run:
```bat
cd ..
cd hdf5-converter
python hdf5-converter.py
```
When finished run `conda deactivate`.

### important things to fix ###

 - Fix the quality control algorithm in `dtt.py` so that bad data is properly rejected but we don't get stuck in a loop of retaking the data point. Not sure yet what the solution is.
 
### nice things to have ###
 - log scaling of kinetic plot should be implemented at some point
 - move the hdf5-conversion tool into a new tab on the main software panel
