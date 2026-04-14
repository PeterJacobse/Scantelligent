import sys, os
from time import sleep
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_hardware("nanonis")

    def run(self):
        self.logprint("Hello from experiment 1", message_type = "message")
        
        self.check_abort_request()
        self.logprint(f"Is an abort requested? {self.abort_requested}", message_type = "message")

        sleep(2)
        self.check_abort_request()
        self.logprint(f"Is an abort requested? {self.abort_requested}", message_type = "message")
        
        self.experiment_finished()
    
    def cleanup(self):
        self.logprint("Cleaning things up")

