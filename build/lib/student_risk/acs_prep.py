#%%
import subprocess
import os
from osgeo import ogr

#%%
driver = ogr.GetDriverByName("OpenFileGDB")

#%%
gdb = driver.Open("C:\\Users\\nathan.lindstedt\\Downloads\\ACS_2020_5YR_ZCTA.gdb.zip")

with gdb:
    features = []

    for featsClass_idx in range(gdb.GetLayerCount()):
        featsClass = gdb.GetLayerByIndex(featsClass_idx)
        features.append(featsClass.GetName())

    my_indices = [0, 1, 2, 14, 16, 18, 23, 30]

    filtered_features = [features[i] for i in my_indices]

    for feature in filtered_features:
        cmd_lst = ["C:\\Program Files\\QGIS 3.16\\bin\\ogr2ogr.exe", "-skipfailures", "-f", "CSV", f"C:\\Users\\nathan.lindstedt\\Desktop\\acs_raw\\acs_2020_5yr_zcta_{feature}.csv", "C:\\Users\\nathan.lindstedt\\Downloads\\ACS_2020_5YR_ZCTA.gdb.zip", f"{feature}"]
        subprocess.check_call(cmd_lst)
