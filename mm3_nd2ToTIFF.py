#!/usr/bin/python
from __future__ import print_function
def warning(*objs):
    print(time.strftime("%H:%M:%S Error:", time.localtime()), *objs, file=sys.stderr)
def information(*objs):
    print(time.strftime("%H:%M:%S", time.localtime()), *objs, file=sys.stdout)

# import modules
import sys
import os
import time
import inspect
import getopt
import yaml
import traceback
import fnmatch
import glob
import math
import copy
import json
try:
    import cPickle as pickle
except:
    import pickle
import numpy as np
import pims_nd2

# user modules
# realpath() will make your script run, even if you symlink it
cmd_folder = os.path.realpath(os.path.abspath(
                              os.path.split(inspect.getfile(inspect.currentframe()))[0]))
if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

# This makes python look for modules in ./external_lib
cmd_subfolder = os.path.realpath(os.path.abspath(
                                 os.path.join(os.path.split(inspect.getfile(
                                 inspect.currentframe()))[0], "external_lib")))
if cmd_subfolder not in sys.path:
    sys.path.insert(0, cmd_subfolder)

import tifffile as tiff

### Main script
if __name__ == "__main__":

    # hard coded parameters
    number_of_rows = 1
    # crop out the area between these two y points. Leave empty for no cropping.
    # if there is more than one row, make a list of pairs
    #vertical_crop = [25, 375]
    vertical_crop = [400, 680] # [y1, y2]

    # number between 0 and 9, 0 is no compression, 9 is most compression.
    tif_compress = 1

    # parameters will be overwritten by switches
    param_file = ""
    specify_fovs = [102] #[15, 16]
    start_fov = -1
    external_directory = ""
    fov_naming_start = 102 # where to start with giving out FOV its for tiff saving

    # switches
    try:
        opts, args = getopt.getopt(sys.argv[1:], "f:o:s:x:n:")
    except getopt.GetoptError:
        warning('No arguments detected (-f -o -s -x -n).')

    for opt, arg in opts:
        if opt == '-f':
            param_file_path = arg
        if opt == '-o':
            arg.replace(" ", "")
            [specify_fovs.append(int(argsplit)) for argsplit in arg.split(",")]
        if opt == '-s':
            try:
                start_fov = int(arg)
            except:
                warning("Could not convert start parameter (%s) to an integer." % arg)
                raise ValueError
        if opt == '-x':
            external_directory = arg
        if opt == '-n':
            try:
                fov_naming_start = int(arg)
            except:
                raise ValueError("Could not convert FOV numbering offset (%s) to an integer." % arg)
            if fov_naming_start < 0:
                raise ValueError("FOV offset (%s) should probably be positive." % fov_num_offset)

    # Load the project parameters file
    if len(param_file_path) == 0:
        raise ValueError("A parameter file must be specified (-f <filename>).")
    information ('Loading experiment parameters.')
    with open(param_file_path, 'r') as param_file:
        p = yaml.safe_load(param_file) # load parameters into dictionary

    # assign shorthand directory names
    TIFF_dir = p['experiment_directory'] + p['image_directory'] # source of images

    # set up image and analysis folders if they do not already exist
    if not os.path.exists(TIFF_dir):
        os.makedirs(TIFF_dir)

    # Load ND2 files into a list for processing
    if len(external_directory) > 0:
        nd2files = glob.glob(external_directory + "*.nd2")
        information("Found %d files to analyze from external file." % len(nd2files))
    else:
        nd2files = glob.glob(p['experiment_directory'] + "*.nd2")
        information("Found %d files to analyze in experiment directory." % len(nd2files))

    for nd2_file in nd2files:
        file_prefix = nd2_file.split(".nd")[0].split("/")[-1] # used for tiff name saving
        information('Extracting %s ...' % file_prefix)

        # load the nd2. the nd2f file object has lots of information thanks to pims
        with pims_nd2.ND2_Reader(nd2_file) as nd2f:
            starttime = nd2f.metadata['time_start_jdn'] # starttime is jd

            # get the color names out. Kinda roundabout way.
            planes = [nd2f.metadata[md]['name'] for md in nd2f.metadata if md[0:6] == u'plane_' and not md == u'plane_count']

            # this insures all colors will be saved when saving tiff
            if len(planes) > 1:
                nd2f.bundle_axes = [u'c', u'y', u'x']

            # get timepoints for extraction. Check is for multiple FOVs or not
            if len(nd2f) == 1:
                extraction_range = [0,]
            else:
                extraction_range = range(0, len(nd2f) - 1)

            # loop through time points
            for t_id in extraction_range:
                # timepoint output name (1 indexed rather than 0 indexed)
                t = t_id + 1
                # set counter for FOV output name
                fov = fov_naming_start

                for fov_id in range(0, nd2f.sizes[u'm']): # for every FOV
                    # fov_id is the fov index according to elements, fov is the output fov ID

                    # skip FOVs as specified above
                    if len(specify_fovs) > 0 and not (fov_id + 1) in specify_fovs:
                        continue
                    if start_fov > -1 and fov_id + 1 < start_fov:
                        continue

                    # set the FOV we are working on in the nd2 file object
                    nd2f.default_coords[u'm'] = fov_id

                    # get time picture was taken
                    seconds = copy.deepcopy(nd2f[t_id].metadata['t_ms']) / 1000.
                    minutes = seconds / 60.
                    hours = minutes / 60.
                    days = hours / 24.
                    acq_time = starttime + days

                    # get physical location FOV on stage
                    x_um = nd2f[t_id].metadata['x_um']
                    y_um = nd2f[t_id].metadata['y_um']

                    # make dictionary which will be the metdata for this TIFF
                    metadata_t = { 'fov': fov,
                                   't' : t,
                                   'jd': acq_time,
                                   'x': x_um,
                                   'y': y_um,
                                   'planes': planes}
                    metadata_json = json.dumps(metadata_t)

                    # get the pixel information
                    image_data = nd2f[t_id]

                    # crop tiff if specified. Lots of flags for if there are double rows or
                    # multiple colors
                    if vertical_crop:
                        # add extra axis to make below slicing simpler.
                        if len(image_data.shape) < 3:
                            image_data = np.expand_dims(image_data, axis=0)

                        # for just a simple crop
                        if number_of_rows == 1:
                            image_data = image_data[:,vertical_crop[0]:vertical_crop[1],:]

                        # for dealing with two rows of channel
                        elif number_of_rows == 2:
                            # cut and save top row
                            image_data_one = image_data[:,vertical_crop[0][0]:vertical_crop[0][1],:]
                            tif_filename = file_prefix + "_t%04dxy%03d.tif" % (t, fov)
                            information('Saving %s.' % tif_filename)
                            tiff.imsave(TIFF_dir + tif_filename, image_data_one, description=metadata_json, compress=tif_compress)

                            # cut and save bottom row
                            fov += 1 # add one to naming of FOV
                            metadata_t['fov'] = fov # update metdata
                            metadata_json = json.dumps(metadata_t)
                            image_data_two = image_data[:,vertical_crop[1][0]:vertical_crop[1][1],:]
                            tif_filename = file_prefix + "_t%04dxy%03d.tif" % (t, fov)
                            information('Saving %s.' % tif_filename)
                            tiff.imsave(TIFF_dir + tif_filename, image_data_two, description=metadata_json, compress=tif_compress)

                            # increase FOV counter
                            fov += 1
                            # Continue to next FOV and not execute code below (extra saving)
                            continue

                    # save the tiff
                    tif_filename = file_prefix + "_t%04dxy%03d.tif" % (t, fov)
                    information('Saving %s.' % tif_filename)
                    tiff.imsave(TIFF_dir + tif_filename, image_data, description=metadata_json,
                                compress=tif_compress)

                    # increase FOV counter
                    fov += 1