import os
import errno
import sys
import shutil
import subprocess
from time import clock
from pygeonet_rasterio import *


def grass(demFileName, geonetResultsDir, pmGrassGISfileName):

    # Software
    if sys.platform.startswith('win'):
        # MS Windows
        grass7bin = r'C:\Program Files\GRASS GIS 7.6\grass76.bat'
        # uncomment when using standalone WinGRASS installer
        # grass7bin = r'C:\Program Files (x86)\GRASS GIS 7.2.0\grass72.bat'
        # this can be avoided if GRASS executable is added to PATH
    elif sys.platform.startswith('darwin'):
        # Mac OS X
        # TODO: this have to be checked, maybe unix way is good enough
        grass7bin = r'/Applications/GRASS/GRASS-7.6.app'
    elif sys.platform.startswith('linux'):
        grass7bin = r'grass76'
    else:
        raise OSError('Platform not configured.')

    # Query GRASS 7 itself for its GISBASE
    startcmd = [grass7bin, '--config', 'path']

    p = subprocess.Popen(startcmd, shell=False,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        print >>sys.stderr, 'ERROR: %s' %err
        print >>sys.stderr, "ERROR: Cannot find GRASS GIS 7 " \
              "start script (%s)" % startcmd
        sys.exit(-1)
    if sys.platform.startswith('linux'):
        gisbase = out.strip('\n')
    elif sys.platform.startswith('win'):
        if out.find("OSGEO4W home is") != -1:
            gisbase = out.strip().split('\n')[1]
        else:
            gisbase = out.strip('\n')
        os.environ['GRASS_SH'] = os.path.join(gisbase, 'mysys', 'bin', 'sh.exe')
    else:
        gisbase = out.strip('\n\r')

    # Set environment variables
    os.environ['GISBASE'] = gisbase
    os.environ['PATH'] += os.pathsep + os.path.join(gisbase, 'extrabin')
    # add path to GRASS addons
    home = os.path.expanduser("~")
    os.environ['PATH'] += os.pathsep + os.path.join(home, '.grass7', 'addons', 'scripts')

    # Define GRASS-Python environment
    gpydir = os.path.join(gisbase, "etc", "python")
    sys.path.append(gpydir)

    # Set GISDBASE environment variable
    if sys.platform.startswith('win'):
        gisdb = os.path.join(home, "Documents", "grassdata")
    else:
        gisdb = os.path.join(home, "grassdata")
    os.environ['GISDBASE'] = gisdb
    # Make Grass GIS DataBase if doesn't already exist
    if not os.path.exists(gisdb):
        try:
            os.makedirs(gisdb)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    # Linux: set path to GRASS libs
    path = os.getenv('LD_LIBRARY_PATH') 
    dir = os.path.join(gisbase, 'lib')
    if path:
        path = dir + os.pathsep + path
    else:
        path = dir
    os.environ['LD_LIBRARY_PATH'] = path

    # Language
    os.environ['LANG'] = 'en_US'
    os.environ['LOCALE'] = 'C'

    # Location
    location = 'geonet'
    os.environ['LOCATION_NAME'] = location
    grassGISlocation = os.path.join(gisdb, location)
    if os.path.exists(grassGISlocation):
        print "Cleaning existing Grass location"
        shutil.rmtree(grassGISlocation)

    # Mapset
    mapset = 'PERMANENT'
    os.environ['MAPSET'] = mapset

    # import GRASS Python bindings
    import grass.script as g
    import grass.script.setup as gsetup

    # Launch session
    gsetup.init(gisbase, gisdb, location, mapset)

    geotiff = pmGrassGISfileName
    print 'Making the geonet location'
    g.run_command('g.proj', georef=geotiff, location = location)
    print 'Existing Mapsets after making locations:'
    g.read_command('g.mapsets', flags = 'l')
    print 'Setting GRASSGIS environ'
    gsetup.init(gisbase, gisdb, location, mapset)
    ##    g.gisenv()

    # Mapset
    mapset = 'geonetuser'
    os.environ['MAPSET'] = mapset
    print 'Making mapset now'
    g.run_command('g.mapset', flags = 'c', mapset = mapset,\
                  location = location, dbase = gisdb)
    # gsetup initialization 
    gsetup.init(gisbase, gisdb, location, mapset)

    # Manage extensions
    extensions = ['r.stream.basins', 'r.stream.watersheds']
    extensions_installed = g.read_command('g.extension', 'a').splitlines()
    for extension in extensions:
        if extension not in extensions_installed:
            g.run_command('g.extension', extension=extension)

    # Read the filtered DEM
    print 'Import filtered DEM into GRASSGIS and '\
          'name the new layer with the DEM name'
    geotiffmapraster = demFileName.split('.')[0]
    print 'GRASSGIS layer name: ',geotiffmapraster
    g.run_command('r.in.gdal', input=geotiff, \
                  output=geotiffmapraster,overwrite=True)
    #Flow computation for massive grids (float version)
    print "Calling the r.watershed command from GRASS GIS"
    subbasinThreshold = 1500
    print ('using swap memory option for large size DEM')
    g.run_command('r.watershed',flags ='am',overwrite=True,\
                  elevation=geotiffmapraster, \
                  threshold=subbasinThreshold, \
                  drainage = 'dra1v23')
    g.run_command('r.watershed',flags ='am',overwrite=True,\
                  elevation=geotiffmapraster, \
                  threshold=subbasinThreshold, \
                  accumulation='acc1v23')
    print 'Identify outlets by negative flow direction'
    g.run_command('r.mapcalc',overwrite=True,\
                  expression='outletmap = if(dra1v23 >= 0,null(),1)')
    print 'Convert outlet raster to vector'
    g.run_command('r.to.vect',overwrite=True,\
                  input = 'outletmap', output = 'outletsmapvec',\
                  type='point')
    print 'Delineate basins according to outlets'
    g.run_command('r.stream.basins',overwrite=True,\
                  direction='dra1v23',points='outletsmapvec',\
                  basins = 'outletbasins')
    # Save the outputs as TIFs
    outlet_filename = geotiffmapraster + '_outlets.tif'
    g.run_command('r.out.gdal',overwrite=True,\
                  input='outletmap', type='Float32',\
                  output=os.path.join(geonetResultsDir,
                                      outlet_filename),\
                  format='GTiff')
    outputFAC_filename = geotiffmapraster + '_fac.tif'
    g.run_command('r.out.gdal',overwrite=True,\
                  input='acc1v23', type='Float64',\
                  output=os.path.join(geonetResultsDir,
                                      outputFAC_filename),\
                  format='GTiff')
    outputFDR_filename = geotiffmapraster + '_fdr.tif'
    g.run_command('r.out.gdal',overwrite=True,\
                  input = "dra1v23", type='Int32',\
                  output=os.path.join(geonetResultsDir,
                                      outputFDR_filename),\
                  format='GTiff')
    outputBAS_filename = geotiffmapraster + '_basins.tif'
    g.run_command('r.out.gdal',overwrite=True,\
                  input = "outletbasins", type='Int16',\
                  output=os.path.join(geonetResultsDir,
                                      outputBAS_filename),\
                  format='GTiff')

def main():
#    demFileName = "OC1mTest"
#    geonetResultsDir = "C:\Users\pp7545\Documents\GeoNet3\Outputs\GIS\OnionCreek_1m_test"
    demFileName = Parameters.demFileName
    geonetResultsDir = Parameters.geonetResultsDir
    pmGrassGISfileName = os.path.join(geonetResultsDir, "PM_filtered_grassgis.tif")
    grass(demFileName, geonetResultsDir, pmGrassGISfileName)

if __name__ == '__main__':
    t0 = clock()
    main()
    t1 = clock()
    print "time taken to complete flow accumulation:", t1-t0, " seconds"
    sys.exit(0)
