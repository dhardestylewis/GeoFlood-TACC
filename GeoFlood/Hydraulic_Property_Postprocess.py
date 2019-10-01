import os
import pandas as pd
import ConfigParser
import inspect


def main():

    ##CONFIGURATION
    config = ConfigParser.RawConfigParser()
    config.read(os.path.join(os.path.dirname(
        os.path.dirname(
            inspect.stack()[0][1])),
                             'GeoFlood.cfg'))
    geofloodHomeDir = config.get('Section', 'geofloodhomedir')
    projectName = config.get('Section', 'projectname')
    #geofloodHomeDir = "H:\GeoFlood"
    #projectName = "Test_Stream"
    DEM_name = config.get('Section', 'dem_name')
    #DEM_name = "DEM"

    geofloodResultsDir = os.path.join(geofloodHomeDir, projectName)
    Name_path = os.path.join(geofloodResultsDir, DEM_name)

    ##INPUT
    hydropropotxt = os.path.join(geofloodResultsDir, "hydroprop-basetable.csv")
    manning_n = os.path.join(geofloodResultsDir, "COMID_Roughness.csv") 
    networkmaptxt = Name_path + "_networkMapping.csv"

    ##OUTPUT
    handpropotxt = os.path.join(geofloodResultsDir, "hydroprop-fulltable.csv")

    ##EXECUTION
    df_result = pd.read_csv(hydropropotxt)
    df_network = pd.read_csv(networkmaptxt)
    if manning_n.isdigit():
        df_result['Roughness'] = manning_n
    else:
        df_n = pd.read_csv(manning_n)
        df_network = pd.merge(df_network, df_n,
                              on='COMID')
        df_result = pd.merge(df_result, df_network,
                             left_on='CatchId',
                             right_on='HYDROID')
    df_result = df_result.drop('HYDROID', axis=1).rename(columns=lambda x: x.strip(" "))
    df_result['TopWidth (m)'] = df_result['SurfaceArea (m2)']/df_result['LENGTHKM']/1000
    df_result['WettedPerimeter (m)'] = df_result['BedArea (m2)']/df_result['LENGTHKM']/1000
    df_result['WetArea (m2)'] = df_result['Volume (m3)']/df_result['LENGTHKM']/1000
    df_result['HydraulicRadius (m)'] = df_result['WetArea (m2)']/df_result['WettedPerimeter (m)']
    df_result['HydraulicRadius (m)'].fillna(0, inplace=True)
    df_result['Discharge (m3s-1)'] = df_result['WetArea (m2)']* \
    pow(df_result['HydraulicRadius (m)'],2.0/3)* \
    pow(df_result['SLOPE'],0.5)/df_result['Roughness']
    df_result['FloodAreaRatio'] = df_result['SurfaceArea (m2)']/df_result['AREASQKM']/1000000
    df_result.to_csv(handpropotxt,index=False)


if __name__ == "__main__":
    main()
