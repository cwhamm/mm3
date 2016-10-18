#!/usr/bin/python
from __future__ import print_function
def warning(*objs):
    print(time.strftime("%H:%M:%S Warning:", time.localtime()), *objs, file=sys.stderr)
def information(*objs):
    print(time.strftime("%H:%M:%S", time.localtime()), *objs, file=sys.stdout)

# import modules
import sys
import os
import time
import inspect
import getopt
import yaml
from pprint import pprint # for human readable file output
try:
    import cPickle as pickle
except:
    import pickle
import numpy as np
import matplotlib.pyplot as plt
from skimage.exposure import rescale_intensity # for displaying in GUI
import multiprocessing
from multiprocessing import Pool

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
import mm3_helpers as mm3

### functions
# funtion which makes the UI plot
def fov_choose_channels_UI(fov_id, crosscorrs, specs):
    '''Creates a plot with the channels with guesses for empties and full channels,
    and requires the user to choose which channels to use for analysis and which to
    average for empties and subtraction.

    Parameters
    fov_file : str
        file name of the hdf5 file name in originals
    fov_xcorrs : dictionary
        dictionary for cross correlation values for all fovs.

    Returns
    bgdr_peaks : list
        list of peak id's (int) of channels to be used for subtraction
    spec_file_pkl : pickle file
        saves the lists cell_peaks, bgrd_peaks, and drop_peaks to a pkl file

    '''

    information("Starting channel picking for FOV %d." % fov_id)

    # define functions here so they have access to variables
    # for UI. change specification of channel
    def onclick_cells(event):
        peak_id = int(event.inaxes.get_title())

        # reset image to be updated based on user clicks
        ax_id = sorted_peaks.index(peak_id) * 3 + 1
        new_img = last_imgs[sorted_peaks.index(peak_id)]
        ax[ax_id].imshow(new_img, cmap=plt.cm.gray, interpolation='nearest')

        # if it says analyze, change to empty
        if specs[fov_id][peak_id] == 1:
            specs[fov_id][peak_id] = 0
            ax[ax_id].imshow(np.dstack((ones_array*0.1, ones_array*0.1, ones_array)), alpha=0.25)
            #information("peak %d now set to empty." % peak_id)

        # if it says empty, change to don't analyze
        elif specs[fov_id][peak_id] == 0:
            specs[fov_id][peak_id] = -1
            ax[ax_id].imshow(np.dstack((ones_array, ones_array*0.1, ones_array*0.1)), alpha=0.25)
            #information("peak %d now set to ignore." % peak_id)

        # if it says don't analyze, change to analyze
        elif specs[fov_id][peak_id] == -1:
            specs[fov_id][peak_id] = 1
            ax[ax_id].imshow(np.dstack((ones_array*0.1, ones_array, ones_array*0.1)), alpha=0.25)
            #information("peak %d now set to analyze." % peak_id)

        plt.draw()

        return

    # set up figure for user assited choosing
    fig = plt.figure(figsize=(20,13))
    ax = [] # for axis handles

    # plot the peaks peak by peak using sorted list
    sorted_peaks = sorted([peak_id for peak_id in crosscorrs[fov_id].keys()])
    npeaks = len(sorted_peaks)
    last_imgs = [] # list that holds last images for updating figure

    for n, peak_id in enumerate(sorted_peaks, start=1):
        peak_xc = crosscorrs[fov_id][peak_id] # get cross corr data from dict

        # load image data needed
        # channel_filename = p['experiment_name'] + '_xy%03d_p%04d.tif' % (fov_id, peak_id)
        channel_filename = p['experiment_name'] + '_xy%03d_p%04d_c0.tif' % (fov_id, peak_id)
        channel_filepath = chnl_dir + channel_filename # chnl_dir read from scope above
        with tiff.TiffFile(channel_filepath) as tif:
            image_data = tif.asarray()
        first_img = rescale_intensity(image_data[0,:,:]) # phase image at t=0
        last_img = rescale_intensity(image_data[-1,:,:]) # phase image at end
        last_imgs.append(last_img) # append for updating later
        del image_data # clear memory (maybe)

        # append an axis handle to ax list while adding a subplot to the figure which has a
        # column for each peak and 3 rows

        # plot the first image in each channel in top row
        ax.append(fig.add_subplot(3, npeaks, n))
        ax[-1].imshow(first_img, cmap=plt.cm.gray, interpolation='nearest')
        ax = format_channel_plot(ax, peak_id) # format axis and title
        if n == 1:
            ax[-1].set_ylabel("first time point")

        # plot middle row using last time point with highlighting for empty/full
        ax.append(fig.add_subplot(3, npeaks, n + npeaks))
        ax[-1].imshow(last_img, cmap=plt.cm.gray, interpolation='nearest')

        # color image based on if it is thought empty or full
        ones_array = np.ones_like(last_img)
        if specs[fov_id][peak_id] == 1: # 1 means analyze, show green
            ax[-1].imshow(np.dstack((ones_array*0.1, ones_array, ones_array*0.1)), alpha=0.25)
        else: # otherwise show blue, means use for empty
            ax[-1].imshow(np.dstack((ones_array*0.1, ones_array*0.1, ones_array)), alpha=0.25)

        # format
        ax = format_channel_plot(ax, peak_id)
        if n == 1:
            ax[-1].set_ylabel("last time point")

        # finally plot the cross correlations a cross time
        ax.append(fig.add_subplot(3, npeaks, n + 2*npeaks))
        ccs = peak_xc['ccs'] # list of cc values

        ax[-1].plot(ccs, range(len(ccs)))
        ax[-1].set_xlim((0.8,1))
        ax[-1].get_xaxis().set_ticks([])
        if not n == 1:
            ax[-1].get_yaxis().set_ticks([])
        else:
            ax[-1].set_ylabel("time index, CC on X")
        ax[-1].set_title('avg=%1.2f' % peak_xc['cc_avg'], fontsize = 8)

    # show the plot finally
    fig.suptitle("FOV %d" % fov_id)
    plt.show(block=False)

    # enter user input
    # ask the user to correct cell/nocell calls
    cells_handler = fig.canvas.mpl_connect('button_press_event', onclick_cells)
    raw_input("Click colored channels to toggle between analyze (green), use for empty (blue), and ignore (red).\nPress enter when done and go to the next FOV (do not close window).") # raw input waits for enter key
    fig.canvas.mpl_disconnect(cells_handler)

    plt.close()

    return specs

# function for better formatting of channel plot
def format_channel_plot(ax, peak_id):
    '''Removes axis and puts peak as title from plot for channels'''
    ax[-1].get_xaxis().set_ticks([])
    ax[-1].get_yaxis().set_ticks([])
    ax[-1].set_title(str(peak_id), fontsize = 8)
    return ax

### For when this script is run from the terminal ##################################
if __name__ == "__main__":
    # hardcoded parameters
    load_crosscorrs = True

    # get switches and parameters
    try:
        opts, args = getopt.getopt(sys.argv[1:],"f:o:s:")
        # switches which may be overwritten
        specify_fovs = False
        user_spec_fovs = []
        start_with_fov = -1
        param_file = ""
    except getopt.GetoptError:
        warning('No arguments detected (-f -s -o).')

    for opt, arg in opts:
        if opt == '-o':
            try:
                specify_fovs = True
                for fov_to_proc in arg.split(","):
                    user_spec_fovs.append(int(fov_to_proc))
            except:
                warning("Couldn't convert argument to an integer:",arg)
                raise ValueError
        if opt == '-s':
            try:
                start_with_fov = int(arg)
            except:
                warning("Couldn't convert argument to an integer:",arg)
                raise ValueError
        if opt == '-f':
            param_file_path = arg # parameter file path

    # Load the project parameters file
    if len(param_file_path) == 0:
        raise ValueError("A parameter file must be specified (-f <filename>).")
    information('Loading experiment parameters.')
    with open(param_file_path, 'r') as param_file:
        p = yaml.safe_load(param_file) # load parameters into dictionary

    mm3.init_mm3_helpers(param_file_path) # initialized the helper library

    # set up how to manage cores for multiprocessing
    cpu_count = multiprocessing.cpu_count()
    if cpu_count == 32:
        num_analyzers = 20
    elif cpu_count == 8:
        num_analyzers = 14
    else:
        num_analyzers = cpu_count*2 - 2

    # assign shorthand directory names
    ana_dir = p['experiment_directory'] + p['analysis_directory']
    chnl_dir = p['experiment_directory'] + p['analysis_directory'] + 'channels/'

    # load channel masks
    try:
        with open(ana_dir + '/channel_masks.pkl', 'r') as cmask_file:
            channel_masks = pickle.load(cmask_file)
    except:
        warning('Could not load channel mask file.')
        raise ValueError

    # make list of FOVs to process (keys of channel_mask file)
    fov_id_list = sorted([fov_id for fov_id in channel_masks.keys()])

    # remove fovs if the user specified so
    if specify_fovs:
        fov_id_list[:] = [fov for fov in fov_id_list if fov in user_spec_fovs]
    if start_with_fov > 0:
        fov_id_list[:] = [fov for fov in fov_id_list if fov_id >= start_with_fov]

    information("Found %d FOVs to process." % len(fov_id_list))

    ### Cross correlations ########################################################################
    if load_crosscorrs: # load precalculate ones if indicated
        information('Loading precalculated cross-correlations.')

        with open(ana_dir + 'crosscorrs.pkl', 'r') as xcorrs_file:
            crosscorrs = pickle.load(xcorrs_file)

    else:
        # a nested dict to hold cross corrs per channel per fov.
        crosscorrs = {}

        # for each fov find cross correlations (sending to pull)
        for fov_id in fov_id_list:
            information("Calculating cross correlations for FOV %d." % fov_id)

            # nested dict keys are peak_ids and values are cross correlations
            crosscorrs[fov_id] = {}

            # initialize pool for analyzing image metadata
            pool = Pool(num_analyzers)

            # find all peak ids in the current FOV
            for peak_id in sorted(channel_masks[fov_id].keys()):
                # determine the channel file name and path
                #channel_filename = p['experiment_name'] + '_xy%03d_p%04d.tif' % (fov_id, peak_id)
                channel_filename = p['experiment_name'] + '_xy%03d_p%04d_c0.tif' % (fov_id, peak_id)
                channel_filepath = chnl_dir + channel_filename

                information("Calculating cross correlations for peak %d." % peak_id)

                # linear loop
                # crosscorrs[fov_id][peak_id] = mm3.channel_xcorr(channel_filepath)

                # multiprocessing verion
                crosscorrs[fov_id][peak_id] = pool.apply_async(mm3.channel_xcorr,
                                                               args=(channel_filepath,))

            information('Waiting for cross correlation pool to finish for FOV %d.' % fov_id)

            pool.close() # tells the process nothing more will be added.
            pool.join() # blocks script until everything has been processed and workers exit

            information("Finished cross correlations for FOV %d." % fov_id)

        # get results from the pool and put the results in the dictionary if succesful
        xcorr_scores = [] # array holds all values for
        for fov_id, peaks in crosscorrs.iteritems():
            for peak_id, result in peaks.iteritems():
                if result.successful():
                    # put the results, with the average, and a guess if the channel
                    # is full into the dictionary
                    crosscorrs[fov_id][peak_id] = {'ccs' : result.get(),
                                                   'cc_avg' : np.average(result.get()),
                                                   'full' : np.average(result.get()) < p['channel_picking_threshold']}
                else:
                    crosscorrs[fov_id][peak_id] = False # put a false there if it's bad

        # write cross-correlations to pickle and text
        information("Writing cross correlations file.")
        with open(ana_dir+ "/crosscorrs.pkl", 'w') as xcorrs_file:
            pickle.dump(crosscorrs, xcorrs_file)
        with open(ana_dir + "/crosscorrs.txt", 'w') as xcorrs_file:
            pprint(crosscorrs, stream=xcorrs_file)

    ### User selection (channel picking) #####################################################
    information('Initializing specifications file.')
    # nested dictionary of {fov : {peak : spec ...}) for if channel should
    # be analyzed, used for empty, or ignored.
    specs = {}
    # update dictionary on initial guess from cross correlations
    for fov_id, peaks in crosscorrs.items():
        specs[fov_id] = {}
        for peak_id, xcorrs in peaks.items():
            if xcorrs['full'] == True:
                specs[fov_id][peak_id] = 1
            else:
                specs[fov_id][peak_id] = 0

    information('Starting channel picking.')
    # go through the fovs again, same as above
    for fov_id in fov_id_list:
        specs = fov_choose_channels_UI(fov_id, crosscorrs, specs)

    # write specfications to pickle and text
    information("Writing specifications file.")
    with open(ana_dir+ "/specs.pkl", 'w') as specs_file:
        pickle.dump(specs, specs_file)
    with open(ana_dir + "/specs.txt", 'w') as specs_file:
        pprint(specs, stream=specs_file)

    information("Finished.")