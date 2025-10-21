from nanonisTCP import nanonisTCP
from nanonisTCP.ZController import ZController
from nanonisTCP.Motor import Motor
from nanonisTCP.AutoApproach import AutoApproach
from nanonisTCP.Scan import Scan
from nanonisTCP.Current import Current
from nanonisTCP.LockIn import LockIn
from nanonisTCP.Bias import Bias
from nanonisTCP.Signals import Signals
from nanonisTCP.Util import Util
from nanonisTCP.FolMe import FolMe
from nanonisTCP.BiasSpectr import BiasSpectr
from nanonisTCP.TipShaper import TipShaper
import numpy as np
from datetime import datetime
import time
from time import sleep
from pathlib import Path
from scipy.signal import convolve2d
import os

# Establish a TCP/IP connection
TCP_IP = "192.168.236.1"                           # Local host
#TCP_IP = "127.0.0.1"
TCP_PORT = 6501                                    # Check available ports in NANONIS > File > Settings Options > TCP Programming Interface
version_number = 13520

def scan_control(tcp_ip, tcp_port, version_number, action: str = "stop", scan_direction: str = "down", verbose: bool = True, monitor: bool = True, sampling_time: float = 4, velocity_threshold: float = .4):
    # logfile = get_session_path() + "\\logfile.txt"

    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        scan = Scan(NTCP)
        
        if scan_direction != "down": scan_direction = "up"
        if action == "start":
            scan.Action(action, scan_direction)
            #if verbose: logprint("Scan started in the " + scan_direction + " direction.", logfile = logfile)
        elif action == "stop":
            scan.Action(action)
            #if verbose: logprint("Scan stopped.", logfile = logfile)
        elif action == "pause":
            scan.Action(action)
            #if verbose: logprint("Scan paused.", logfile = logfile)
        elif action == "resume":
            scan.Action(action)
            #if verbose: logprint("Scan resumed.", logfile = logfile)

    finally:
        NTCP.close_connection()
        sleep(.05)
    
    #if action == "start" or action == "resume":
    #    if monitor: # Continue monitoring the progress of the scan until it is done
    #        txyz = tip_tracker(sampling_time = sampling_time, velocity_threshold = velocity_threshold, timeout = 100000, exit_when_still = True, N_no_motion = 4, verbose = verbose, monitor_roughness = False)

def change_bias(V = None, dt: float = .01, dV: float = .02, dz: float = 1E-9, verbose: bool = True):
    #logfile = get_session_path() + "\\logfile.txt"
    
    if V == None:
        #if verbose: logprint("No new bias set. Returning.", logfile = logfile)
        return
    
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        bias = Bias(NTCP)
        zcontroller = ZController(NTCP)
        
        V_old = bias.Get() # Read data from Nanonis
        feedback = zcontroller.OnOffGet()
        tip_height = zcontroller.ZPosGet()
        
        polarity_difference = int(np.abs(np.sign(V) - np.sign(V_old)) / 2) # Calculate the polarity and voltage slew values
        if V > V_old: delta_V = dV
        else: delta_V = -dV
        slew = np.arange(V_old, V, delta_V)

        if bool(feedback) and bool(polarity_difference): # If the bias polarity is switched, switch off the feedback and lift the tip by dz for safety
            zcontroller.OnOffSet(False)
            sleep(.05) # If the tip height is set too quickly, the controller won't be off yet
            zcontroller.ZPosSet(tip_height + dz)
            #if verbose: logprint("Bias polarity change detected while in feedback. Tip retracted by = " + str(round(dz * 1E9, 3)) + " nm during slew.", logfile = logfile)

        for V_t in slew: # Perform the slew to the new bias voltage
            bias.Set(V_t)
            sleep(dt)
        bias.Set(V)
        
        if bool(feedback) and bool(polarity_difference): zcontroller.OnOffSet(True) # Turn the feedback back on
        
        #if verbose: logprint("Bias changed from V = " + str(round(V_old, 3)) + " V to V = " + str(round(V, 3)) + " V.", logfile = logfile)

    finally:
        NTCP.close_connection()
        sleep(.05)
        return V_old