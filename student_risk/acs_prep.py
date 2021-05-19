#%%
import subprocess
import os
from osgeo import ogr

#%%
driver = ogr.GetDriverByName("OpenFileGDB")

#%%
gdb = driver.Open("C:\\Users\\nathan.lindstedt\\Desktop\\shapefiles\\zcta\\ACS_2016_5YR_ZCTA.gdb.zip")

# %%
features = []

for featsClass_idx in range(gdb.GetLayerCount()):
    featsClass = gdb.GetLayerByIndex(featsClass_idx)
    features.append(featsClass.GetName())

# %%

cmd_lst = ["C:\\Program Files\\QGIS 3.14\\bin\\ogr2ogr.exe", "-overwrite", "-skipfailures", "-f", "CSV", "C:\\Users\\nathan.lindstedt\\Desktop\\acs_raw\\acs_2016_5yr_zctz_race.csv", "C:\\Users\\nathan.lindstedt\\Desktop\\shapefiles\\zcta\\ACS_2016_5YR_ZCTA.gdb.zip", "X02_RACE"]

#%%
subprocess.check_call(["C:\\Program Files\\QGIS 3.14\\bin\\ogr2ogr.exe", "-overwrite", "-skipfailures", "-f", "CSV", "C:\\Users\\nathan.lindstedt\\Desktop\\acs_raw\\acs_2016_5yr_zctz_race.csv", "C:\\Users\\nathan.lindstedt\\Desktop\\shapefiles\\zcta\\ACS_2016_5YR_ZCTA.gdb.zip", "X02_RACE"])

# %%
