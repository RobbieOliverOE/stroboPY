# general
import sys
import os
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication, QMessageBox, QGraphicsPixmapItem, QFileDialog
from PyQt5.QtCore import pyqtSlot, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage

# gui
from gui import Ui_stroboPYgui as stroboPYgui

# graphics
import pyqtgraph as pg
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

# data processing
import numpy as np
from dtt import DataProcessing
from sweeps import SweepProcessing
import pickle

# hardware
from cameras import StresingCameras, Acquisition, AndorCamera, MockAndorCamera
from Sepia2 import Sepia2

# metadata
import datetime

# hack to get app to display icon properly (Windows OS only?)
import ctypes
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('stroboPY')


class Application(QtWidgets.QMainWindow):
    
    # This is the usb device index of the Sepia 2, assumed always 0
    # May change if on a machine with multiple Sepia 2 attached
    s2_iDevIdx = 0;
    # The slot indices for the oscillator (SOMD) and two laser controllers (SLM)
    # Currently assumed constant
    s2_cont_slotId = 000;
    s2_osc_slotId = 100;
    s2_pump_slotId = 200;
    s2_probe_slotId = 300;
    # Store summed images collected during acquisition
    acquisition_i_off = dict()
    acquisition_i_on = dict()
    acquisition_i_off_ct = dict()
    acquisition_i_on_ct = dict()
    
    def __init__(self, last_instance_filename, last_instance_values=None, mock=False):
        super(Application, self).__init__()
        self.mock = mock
        self.ui = stroboPYgui()
        self.ui.setupUi(self)
        self.setWindowIcon(QtGui.QIcon('icon2.png'))
        if not self.mock:
            # Check that the library is available instantly
            self.sepia2 = Sepia2()
        self.ui.tabs.setCurrentIndex(0)
        # @todo temp disabled, till I understand the checks that reenable the tabs
        #self.ui.diagnostics_tab.setEnabled(False)
        #self.ui.acquisition_tab.setEnabled(False)
        self.last_instance_filename = last_instance_filename
        self.last_instance_values = last_instance_values
        self.camera_connected = False
        self.sepia2_connected = False
        self.ui.acquisition_tab.setEnabled(False)
        self.ui.diagnostics_tab.setEnabled(False)
        self.timeunits = 'ps'
        self.xlabel = 'Wavelength / Pixel'
        self.datafolder = os.path.join(os.path.expanduser('~'), 'Documents')
        self.timefile_folder = os.path.join(os.path.expanduser('~'), 'Documents')
        self.metadata = {}
        self.idle = True
        self.finished_acquisition = False
        self.init_binning_dd()
        self.init_baseosc_trigger_dd()
        self.initialize_gui_values()
        self.initialise_gui()
        self.setup_gui_connections()
        if self.mock:
            self.init_mock()
        self.show()
        self.write_app_status('application launched', colour='blue')
        
    def closeEvent(self, event):
        if self.camera_connected or self.sepia2_connected:
            event.ignore()
            self.message_unsafe_exit()
        else:
            self.read_gui_values()
            self.save_gui_values_pickle()
            self.save_gui_values_dict(os.getcwd(), 'metadata_closing.txt')
            event.accept()
            
    def write_app_status(self, message, colour, timeout=0):
        self.ui.statusBar.clearMessage()
        self.ui.statusBar.setStyleSheet('QStatusBar{color:'+colour+';}')
        self.ui.statusBar.showMessage(message, msecs=timeout)
        return
        
    def initialize_gui_values(self):
        # dropdown menus
        self.ui.a_distribution_dd.addItem('Exponential')
        self.ui.a_distribution_dd.addItem('Linear')
        self.ui.a_distribution_dd.addItem('From file')
        self.ui.h_camera_dd.addItem('Andor Zyla 5.5')
        self.ui.h_camera_dd.addItem('Andor Zyla 4.2')
        self.ui.h_camera_dd.addItem('VIS')
        self.ui.h_camera_dd.addItem('NIR')
        self.ui.a_steporder_dd.addItem('Linear')
        # self.ui.a_steporder_dd.addItem('Random')
        # self.ui.a_steporder_dd.addItem('Bidirectional')
        # @todo sort out Random and Bidirectional stepping orders!
        # progress bars
        self.ui.a_measurement_progress_bar.setValue(0)
        self.ui.a_sweep_progress_bar.setValue(0)
        # other stuff
        self.ui.a_filename_le.setText('newfile')
        self.use_logscale = False
        # file
        self.load_gui_values(self.last_instance_values)
        # Can't stop whilst idle
        self.ui.a_stop_btn.setEnabled(False)
        self.ui.d_stop_btn.setEnabled(False)
        
    def setup_gui_connections(self):
        # acquisition file stuff
        self.ui.a_folder_btn.clicked.connect(self.exec_folder_browse_btn)
        self.ui.a_filename_le.textChanged.connect(self.update_filepath)
        # metadata deprecated for stroboPY, now absorbed into last_instance_values
        # self.ui.a_metadata_pump_wavelength.textChanged.connect(self.metadata_changed)
        # self.ui.a_metadata_pump_power.textChanged.connect(self.metadata_changed)
        # self.ui.a_metadata_pump_spotsize.textChanged.connect(self.metadata_changed)
        # self.ui.a_metadata_probe_wavelength.textChanged.connect(self.metadata_changed)
        # self.ui.a_metadata_probe_power.textChanged.connect(self.metadata_changed)
        # acquisition times options
        self.ui.a_distribution_dd.currentIndexChanged.connect(self.update_times)
        self.ui.a_distribution_dd.currentIndexChanged.connect(self.update_use_timefile)
        self.ui.a_tstart_sb.valueChanged.connect(self.update_times)
        self.ui.a_tend_sb.valueChanged.connect(self.update_times)
        self.ui.a_num_tpoints_sb.valueChanged.connect(self.update_times)
        self.ui.a_timefile_btn.clicked.connect(self.exec_timefile_folder_btn)
        self.ui.a_timefile_list.currentIndexChanged.connect(self.update_times_from_file)
        self.update_times()
        # acquisition launch
        #self.ui.a_run_btn.clicked.connect(self.exec_run_btn)
        #self.ui.a_stop_btn.clicked.connect(self.exec_stop_btn)
        self.ui.a_run_btn.clicked.connect(self.run_acquisition)
        self.ui.a_stop_btn.clicked.connect(self.stop_acquisition)
        # acquisition acquire
        self.ui.a_baseosctrigger_dd.currentIndexChanged.connect(self.set_baseosctrigger)
        self.ui.a_divider.valueChanged.connect(self.set_divider)
        self.ui.a_rise_fall_exp_time.valueChanged.connect(self.set_pulsesbursts)
        self.ui.a_probe_exp_time.valueChanged.connect(self.set_pulsesbursts)
        self.ui.a_probe_on_off_pairs.valueChanged.connect(self.set_on_off_pairs)
        self.ui.a_pump_outenabled_cb.stateChanged.connect(self.set_outenabled)
        self.ui.a_pump_pulsed_cb.stateChanged.connect(self.set_pulsed_pump)
        self.ui.a_pump_intensity.valueChanged.connect(self.set_intensity_pump)
        self.ui.a_probe_outenabled_cb.stateChanged.connect(self.set_outenabled)
        self.ui.a_probe_pulsed_cb.stateChanged.connect(self.set_pulsed_probe)
        self.ui.a_probe_intensity.valueChanged.connect(self.set_intensity_probe)
        self.update_p2p_time_rate() # Display the correct time/rate immediately
        # acquisition slider
        self.ui.a_timedelay_slider.valueChanged.connect(self.acquisition_slider_changed)
        # diagnostics time
        self.ui.d_move_to_time_btn.clicked.connect(self.exec_d_move_to_time)
        self.ui.d_jogleft.clicked.connect(self.d_jog_earlier)
        self.ui.d_jogright.clicked.connect(self.d_jog_later)
        self.ui.d_set_current_btn.clicked.connect(self.exec_d_set_current_btn)
        self.ui.d_time.valueChanged.connect(self.set_delay_diagnostics)
        # diagnostics acquire
        self.ui.d_t0.valueChanged.connect(self.set_delay_diagnostics)
        self.ui.d_baseosctrigger_dd.currentIndexChanged.connect(self.set_baseosctrigger)
        self.ui.d_divider.valueChanged.connect(self.set_divider)
        self.ui.d_rise_fall_exp_time.valueChanged.connect(self.set_pulsesbursts)
        self.ui.d_probe_exp_time.valueChanged.connect(self.set_pulsesbursts)
        self.ui.d_probe_on_off_pairs.valueChanged.connect(self.set_on_off_pairs)
        self.ui.d_pump_outenabled_cb.stateChanged.connect(self.set_outenabled)
        self.ui.d_pump_pulsed_cb.stateChanged.connect(self.set_pulsed_pump)
        self.ui.d_pump_intensity.valueChanged.connect(self.set_intensity_pump)
        self.ui.d_probe_outenabled_cb.stateChanged.connect(self.set_outenabled)
        self.ui.d_probe_pulsed_cb.stateChanged.connect(self.set_pulsed_probe)
        self.ui.d_probe_intensity.valueChanged.connect(self.set_intensity_probe)
        # diagnostics launch
        self.ui.d_run_btn.clicked.connect(self.exec_d_run_btn)
        self.ui.d_stop_btn.clicked.connect(self.exec_d_stop_btn)
        # hardware cameras
        self.ui.h_connect_camera_btn.clicked.connect(self.connect_camera)
        self.ui.h_disconnect_camera_btn.clicked.connect(self.disconnect_camera)
        # hardware sepia2
        self.ui.h_sepia2_connect_btn.clicked.connect(self.connect_sepia2)
        self.ui.h_sepia2_disconnect_btn.clicked.connect(self.disconnect_sepia2)
        # tabs
        self.ui.tabs.tabBarClicked.connect(self.sync_tabs)
        # These undocumented signals capture when the images are zoomed or translated
        # @todo Implement these for the new ImageView plots
        # self.ui.a_kinetic_graph.sigRangeChanged.connect(self.sync_acquisition_plotwidgets)
        # self.ui.a_last_shot_graph.sigRangeChanged.connect(self.sync_acquisition_plotwidgets)
        # self.ui.a_spectra_graph.sigRangeChanged.connect(self.sync_acquisition_plotwidgets) 
        
    def initialise_gui(self):
        self.update_use_timefile()
        self.update_times()
        # self.update_xlabel()
        self.update_filepath()

    def init_binning_dd(self):
        # Define the mapping
        # 0 is 1x1, 1 is 2x2, 2 is 3x3, 3 is 4x4, 4 is 8x8
        self.iBinningMap = {
            '1x1': 0,
            '2x2': 1,
            '3x3': 2,
            '4x4': 3,
            '8x8': 4,
            }
        # setup the two drop downs
        for k,v in self.iBinningMap.items():
            self.ui.a_pixel_binning_dd.addItem(k)
            self.ui.d_pixel_binning_dd.addItem(k)

    def init_baseosc_trigger_dd(self):
        # Define the mapping to convert them back to iFreqTrigMode
        self.iFreqTrigModeMap = {
            # External triggers will never be used for oscillator
            #"rising  edge (ext.)": 0,
            #"falling edge (ext.)": 1,
            "80.00 MHz (int. A)": 2,
            "64.00 MHz (int. B)": 3,
            "50.00 MHz (int. C)": 4,
        }
        # setup the two drop downs
        for k,v in self.iFreqTrigModeMap.items():
            self.ui.a_baseosctrigger_dd.addItem(k)
            self.ui.d_baseosctrigger_dd.addItem(k)
        
    def init_mock(self):
        """
        Initialise mock mode
        Disables attempts to connect to Sepia2 and mocks camera returning images during acquisition.
        Also initialises UI as though both Sepia2 and Camera are connected.
        """
        # Disable connect camera/sepia2 buttons
        self.ui.h_sepia2_usb.setEnabled(False)
        self.ui.h_sepia2_controllerslot.setEnabled(False)
        self.ui.h_sepia2_oscillatorslot.setEnabled(False)
        self.ui.h_sepia2_pumpslot.setEnabled(False)
        self.ui.h_sepia2_probeslot.setEnabled(False)
        self.ui.h_sepia2_disconnect_btn.setEnabled(False)
        self.ui.h_sepia2_connect_btn.setEnabled(False)
        self.ui.h_sepia2_status.setText("Mocked")
        self.ui.h_connect_camera_btn.setEnabled(False)
        self.ui.h_camera_dd.setEnabled(False)
        self.ui.h_use_ir_gain.setEnabled(False)
        self.ui.h_disconnect_camera_btn.setEnabled(False)
        self.ui.h_camera_status.setText('Mocked')
        # Enable Acquisition and Diagnostics tab buttons
        self.ui.acquisition_tab.setEnabled(True)
        self.ui.diagnostics_tab.setEnabled(True)
        # Attach mock camera
        self.camera = MockAndorCamera(bit_depth_mode=0, shutter_mode=0)        
        pass

    def sync_tabs(self, tab_clicked_index):
        """
        Whole tab UI element synchronisation
        """
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            # Sync content from diagnostics tab to acquisition, when leaving diagnostics tab
            self.sync_to_acquisition_tab()
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            # Sync content from acquisition tab to diagnostics, when leaving acquisition tab
            self.sync_to_diagnostics_tab()

    def sync_to_acquisition_tab(self):
            # AOI and binning
            self.ui.a_AOI_height.setValue(self.ui.d_AOI_height.value())
            self.ui.a_AOI_width.setValue(self.ui.d_AOI_width.value())
            self.ui.a_pixel_binning_dd.setCurrentIndex(self.ui.d_pixel_binning_dd.currentIndex())
            # Acquire
            self.ui.a_t0.setValue(self.ui.d_t0.value())
            self.ui.a_baseosctrigger_dd.setCurrentIndex(self.ui.d_baseosctrigger_dd.currentIndex())
            self.ui.a_divider.setValue(self.ui.d_divider.value())
            # Pulses/Bursts
            self.ui.a_rise_fall_exp_time.setValue(self.ui.d_rise_fall_exp_time.value())
            self.ui.a_probe_exp_time.setValue(self.ui.d_probe_exp_time.value())
            self.ui.a_probe_on_off_pairs.setValue(self.ui.d_probe_on_off_pairs.value())
            # Pump
            self.ui.a_pump_outenabled_cb.setChecked(self.ui.d_pump_outenabled_cb.isChecked())
            self.ui.a_pump_pulsed_cb.setChecked(self.ui.d_pump_pulsed_cb.isChecked())
            self.ui.a_pump_intensity.setValue(self.ui.d_pump_intensity.value())
            # Probe
            self.ui.a_probe_outenabled_cb.setChecked(self.ui.d_probe_outenabled_cb.isChecked())
            self.ui.a_probe_pulsed_cb.setChecked(self.ui.d_probe_pulsed_cb.isChecked())
            self.ui.a_probe_intensity.setValue(self.ui.d_probe_intensity.value())
    def sync_to_diagnostics_tab(self):
            # AOI and binning
            self.ui.d_AOI_height.setValue(self.ui.a_AOI_height.value())
            self.ui.d_AOI_width.setValue(self.ui.a_AOI_width.value())
            self.ui.d_pixel_binning_dd.setCurrentIndex(self.ui.a_pixel_binning_dd.currentIndex())
            # Acquire
            self.ui.d_t0.setValue(self.ui.a_t0.value())
            self.ui.d_baseosctrigger_dd.setCurrentIndex(self.ui.a_baseosctrigger_dd.currentIndex())
            self.ui.d_divider.setValue(self.ui.a_divider.value())
            # Pulses/Bursts
            self.ui.d_rise_fall_exp_time.setValue(self.ui.a_rise_fall_exp_time.value())
            self.ui.d_probe_exp_time.setValue(self.ui.a_probe_exp_time.value())
            self.ui.d_probe_on_off_pairs.setValue(self.ui.a_probe_on_off_pairs.value())
            # Pump
            self.ui.d_pump_outenabled_cb.setChecked(self.ui.a_pump_outenabled_cb.isChecked())
            self.ui.d_pump_pulsed_cb.setChecked(self.ui.a_pump_pulsed_cb.isChecked())
            self.ui.d_pump_intensity.setValue(self.ui.a_pump_intensity.value())
            # Probe
            self.ui.d_probe_outenabled_cb.setChecked(self.ui.a_probe_outenabled_cb.isChecked())
            self.ui.d_probe_pulsed_cb.setChecked(self.ui.a_probe_pulsed_cb.isChecked())
            self.ui.d_probe_intensity.setValue(self.ui.a_probe_intensity.value())
            
    def sync_acquisition_plotwidgets(self, updated_widget):
        """
        When user interacts to zoom/pan plot widget in acquisition tab
        Synchronise the zoom/pan of other plot widgets
        """
        # Disconnect plotwidget connections, to prevent recursion when others are triggered
        self.ui.a_kinetic_graph.sigRangeChanged.disconnect(self.sync_acquisition_plotwidgets)
        self.ui.a_last_shot_graph.sigRangeChanged.disconnect(self.sync_acquisition_plotwidgets)
        self.ui.a_spectra_graph.sigRangeChanged.disconnect(self.sync_acquisition_plotwidgets)
        # Trigger all to update range
        rect = updated_widget.viewRect()
        self.ui.a_last_shot_graph.setRange(rect=rect)
        self.ui.a_spectra_graph.setRange(rect=rect)
        self.ui.a_kinetic_graph.setRange(rect=rect)
        # Reconnect plot widget connections to capture next interaction
        self.ui.a_kinetic_graph.sigRangeChanged.connect(self.sync_acquisition_plotwidgets)
        self.ui.a_last_shot_graph.sigRangeChanged.connect(self.sync_acquisition_plotwidgets)
        self.ui.a_spectra_graph.sigRangeChanged.connect(self.sync_acquisition_plotwidgets)

    """
    Sepia 2 connect/disconnect
    """
    def connect_sepia2(self):
        if self.mock:
            return
        # Connect to the device if required
        if not self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            self.ui.h_sepia2_status.setText('Connecting... please wait')
            QApplication.processEvents() # Allows UI to update before interface interaction has completed
            # Disable vars
            self.ui.h_sepia2_usb.setEnabled(False)
            self.ui.h_sepia2_controllerslot.setEnabled(False)
            self.ui.h_sepia2_oscillatorslot.setEnabled(False)
            self.ui.h_sepia2_pumpslot.setEnabled(False)
            self.ui.h_sepia2_probeslot.setEnabled(False)
            self.ui.h_sepia2_connect_btn.setEnabled(False)
            # Update vars
            self.s2_iDevIdx = self.ui.h_sepia2_usb.value()
            self.s2_cont_slotId = self.ui.h_sepia2_controllerslot.value()
            self.s2_osc_slotId = self.ui.h_sepia2_oscillatorslot.value()
            self.s2_pump_slotId = self.ui.h_sepia2_pumpslot.value()
            self.s2_probe_slotId = self.ui.h_sepia2_probeslot.value()
            try:
                self.sepia2.USB_OpenDevice(self.s2_iDevIdx)
                # This is required by some fns, so just call it always
                self.sepia2.FWR_GetModuleMap(self.s2_iDevIdx, False)
                # @todo Could confirm the provided slots contain the correct module types here??
                self.ui.h_sepia2_status.setText('Connected')
            except Exception as e:
                self.ui.h_sepia2_status.setText('Connection failed (is it turned on?)')
                self.ui.h_sepia2_connect_btn.setEnabled(True)
                self.ui.h_sepia2_usb.setEnabled(True)
                self.ui.h_sepia2_controllerslot.setEnabled(True)
                self.ui.h_sepia2_oscillatorslot.setEnabled(True)
                self.ui.h_sepia2_pumpslot.setEnabled(True)
                self.ui.h_sepia2_probeslot.setEnabled(True)
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2
            # Setup initial Sepia2 settings from current GUI.
            self.ui.h_sepia2_disconnect_btn.setEnabled(True)
            self.ui.h_sepia2_status.setText('Initialising parameters...')
            QApplication.processEvents() # Allows UI to update before interface interaction has completed
            try:
                self.set_softlock(True) # Always start with the laser soft locked
                self.set_sequencing_running(False) # Also always start with the sequencer disabled
                self.set_delay(0)
                self.set_miscellaneous()
                self.set_outenabled()
                self.set_on_off_pairs()
                self.set_intensity_pump()
                self.set_intensity_probe()
                self.set_pulsed_pump()
                self.set_pulsed_probe()
                self.ui.h_sepia2_status.setText('Connected & initialised')
                if self.camera_connected: # if not, do these when connecting camera
                    self.set_baseosctrigger()
                    self.set_divider()
                    self.set_pulsesbursts()
            except Exception as e:
                self.ui.h_sepia2_status.setText('Initialisation failed (see log)')
                raise
        if self.camera_connected:
            self.ui.acquisition_tab.setEnabled(True)
            self.ui.diagnostics_tab.setEnabled(True)
        self.sepia2_connected = True
    def disconnect_sepia2(self):
        if self.mock:
            return
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            self.sepia2.USB_CloseDevice(self.s2_iDevIdx)
        self.ui.h_sepia2_status.setText('Ready to connect')
        # Enable vars
        self.ui.h_sepia2_disconnect_btn.setEnabled(False)
        self.ui.h_sepia2_usb.setEnabled(True)
        self.ui.h_sepia2_controllerslot.setEnabled(True)
        self.ui.h_sepia2_oscillatorslot.setEnabled(True)
        self.ui.h_sepia2_pumpslot.setEnabled(True)
        self.ui.h_sepia2_probeslot.setEnabled(True)
        self.ui.h_sepia2_connect_btn.setEnabled(True)
        self.ui.acquisition_tab.setEnabled(False)
        self.ui.diagnostics_tab.setEnabled(False)
        self.sepia2_connected = False
    
    """
    Camera connect/disconnect
    """
    def connect_camera(self):
        if self.mock:
            return
        self.ui.h_connect_camera_btn.setEnabled(False)
        self.ui.h_camera_dd.setEnabled(False)
        self.ui.h_use_ir_gain.setEnabled(False)
        self.ui.h_camera_status.setText('Connecting... please wait')
        QApplication.processEvents() # Allows UI to update before interface interaction has completed
        # Based on selected camera type, iinit some config
        cameratype = self.ui.h_camera_dd.currentText()
        if cameratype == 'NIR':
            self.use_ir_gain = self.ui.h_use_ir_gain.isChecked()
            self.num_pixels = 512 # @todo, original pyTA invoked self.num_pixels but stroboPY invokes self.camera.num_pixels. Watch out for errors.
        elif cameratype == 'VIS':
            self.use_ir_gain = False
            self.num_pixels = 1024
        elif cameratype == 'Andor Zyla 5.5' or cameratype == 'Andor Zyla 4.2':
            self.use_ir_gain = False
            self.waves = []
        try:
            # Actually perform the camera connection
            if cameratype == 'Andor Zyla 5.5':
                self.camera = AndorCamera(bit_depth_mode=2, shutter_mode=1, cameratype=cameratype) # recall shutter_mode = 1 is global shutter
            elif cameratype == 'Andor Zyla 4.2':
                self.camera = AndorCamera(bit_depth_mode=2, shutter_mode=0, cameratype=cameratype)
            else: 
                self.camera = StresingCameras(self.ui.h_camera_dd.currentText(), self.use_ir_gain)
                self.camera.initialise()
        except Exception as e:
            self.ui.h_connect_camera_btn.setEnabled(True)
            self.ui.h_camera_dd.setEnabled(True)
            self.ui.h_use_ir_gain.setEnabled(True)
            self.ui.h_camera_status.setText('Connection failed (is it turned on?)')
            raise # Kill the rest of the event loop, can't continue with no connection to Sepia2
        self.ui.h_camera_status.setText('Initialising parameters...')
        # Set number of pixels for the Andor cameras
        if cameratype == 'Andor Zyla 5.5' or cameratype == 'Andor Zyla 4.2':
            self.camera.cam.set_attribute_value('FastAOIFrameRateEnable', True)
            self.camera.cam.set_attribute_value('VerticallyCentreAOI', True)
            x = 128
            self.camera.cam.set_attribute_value('AOIHeight', x)
            self.camera.cam.set_attribute_value('AOIWidth', x)
            self.camera.cam.set_attribute_value('AOILeft', int((2560/2)-(x/2)))
            self.camera.cam.set_attribute_value('AOIWidth', x)
            # @todo incorporate these into the GUI properly!
            self.camera.SetParams(binning = 0) # binning control
            # 0 is 1x1, 1 is 2x2, 2 is 3x3, 3 is 4x4, 4 is 8x8
            self.camera.num_pixels = [self.camera.cam.get_attribute_value('AOIHeight'),self.camera.cam.get_attribute_value('AOIWidth')]
            # @todo Have to re-define num_pixels as it thinks it's still the maximum of (2160,2560) otherwise. Fix this
            print(self.camera.num_pixels) # NOTE! This is AOIWidth/AOIHeight
        # @todo can this fail? will it leave us in a broken state can't connect/disconnect
        try:
            if self.sepia2_connected: # if not, do these when connecting Sepia II
                self.set_baseosctrigger()
                self.set_divider()
                self.set_pulsesbursts()
        except Exception as e:
            self.ui.h_connect_camera_btn.setEnabled(True)
            self.ui.h_camera_dd.setEnabled(True)
            self.ui.h_use_ir_gain.setEnabled(True)
            self.ui.h_camera_status.setText('Initialisation failed (see log)')
            raise # Kill the rest of the event loop, can't continue with no connection to Sepia2
        # Update the interface
        self.ui.h_camera_status.setText('Connected & initialised')
        self.ui.h_disconnect_camera_btn.setEnabled(True)
        self.camera_connected = True
        if self.sepia2_connected:
            self.ui.acquisition_tab.setEnabled(True)
            self.ui.diagnostics_tab.setEnabled(True)
    def disconnect_camera(self):
        if self.mock:
            return
        self.ui.h_disconnect_camera_btn.setEnabled(False)
        self.camera.close()
        self.ui.h_camera_status.setText('Ready to connect')
        self.ui.h_connect_camera_btn.setEnabled(True)
        self.ui.h_camera_dd.setEnabled(True)
        self.ui.h_use_ir_gain.setEnabled(True)
        self.camera_connected = False
        if not self.sepia2_connected:
            self.ui.acquisition_tab.setEnabled(False)
            self.ui.diagnostics_tab.setEnabled(False)
    
    """
    Setters
    All these methods:
    * Synchronise matching interface elements
    * Update relevant Sepia2 settings (if connected)
    * Update relevant camera settings
    """
    def set_softlock(self, softlock):
        '''
        Sets Sepia II soft lock on (softlock = 1) or off (softlock = 0)
        Ignored for mock mode
        @param softlock Desired value of the soft lock register
        '''
        if self.mock:
            return
        else:
            try:
                self.sepia2.SCM_SetLaserSoftLock(self.s2_iDevIdx, self.s2_cont_slotId, softlock)
            except Exception as e:
                self.append_history('set_softlock('+str(bool(softlock))+') failed:')
                self.append_history(str(e))
                
    def set_sequencing_running(self, running):
        '''
        Sets Sepia II sequencing free running (running = 1) or disabled (running = 0)
        Ignored for mock mode
        @param running Desired value for sequencing
        @note Invokes bAUXInCtrl, which has 4 options total
        Just converted into something more legible here
        '''
        if self.mock:
            return
        else:
            if running == True:
                bAUXInCtrl = 0
            elif running == False:
                bAUXInCtrl = 3
            else:
                bAUXInCtrl = -1 # Illegal; just leads to error message
            try:
                self.sepia2.SOMD_SetAUXIOSequencerCtrl(self.s2_iDevIdx, self.s2_osc_slotId, True, bAUXInCtrl)
            except Exception as e:
                self.append_history('set_sequencing_running('+str(bool(running))+') failed:')
                self.append_history(str(e))
    
    def set_camera_AOI(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_AOI_height.setValue(self.ui.d_AOI_height.value())
            self.ui.a_AOI_width.setValue(self.ui.d_AOI_width.value())
            self.ui.a_pixel_binning_dd.setCurrentIndex(self.ui.d_pixel_binning_dd.currentIndex())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.a_divider.setValue(self.ui.d_divider.value())
            self.ui.d_AOI_height.setValue(self.ui.a_AOI_height.value())
            self.ui.d_AOI_width.setValue(self.ui.a_AOI_width.value())
            self.ui.d_pixel_binning_dd.setCurrentIndex(self.ui.a_pixel_binning_dd.currentIndex())
        # @todo Rest of this...
        
    def set_baseosctrigger(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_baseosctrigger_dd.setCurrentIndex(self.ui.d_baseosctrigger_dd.currentIndex())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_baseosctrigger_dd.setCurrentIndex(self.ui.a_baseosctrigger_dd.currentIndex())
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:
                self.sepia2.SOMD_SetFreqTrigMode(self.s2_iDevIdx, self.s2_osc_slotId, self.iFreqTrigModeMap[self.ui.a_baseosctrigger_dd.currentText()], False)
            except Exception as e:
                self.append_history("set_baseosctrigger() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2
        self.update_p2p_time_rate()
        self.set_pulsesbursts()

    def set_divider(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_divider.setValue(self.ui.d_divider.value())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_divider.setValue(self.ui.a_divider.value())
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:
                self.sepia2.SOMD_SetBurstValues(self.s2_iDevIdx, self.s2_osc_slotId, self.ui.a_divider.value(), False, 1)
            except Exception as e:
                self.append_history("set_divider() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2
        self.update_p2p_time_rate()
        self.set_pulsesbursts()

    def set_pulsesbursts(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_rise_fall_exp_time.setValue(self.ui.d_rise_fall_exp_time.value())
            self.ui.a_probe_exp_time.setValue(self.ui.d_probe_exp_time.value())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_rise_fall_exp_time.setValue(self.ui.a_rise_fall_exp_time.value())
            self.ui.d_probe_exp_time.setValue(self.ui.a_probe_exp_time.value())
        # Re-calculate number of bursts to input, from the inputted exposure times
        self.update_pulsesbursts()
        # Change the Camera exposure time to match
        # Camera exposure time = Rise Time + Lasing Time + Fall Time
        # Calculate this in update_pulsesbursts()...
        self.camera.SetParams(exposure = self.camera_exp_time_s)
        # Calculate extra fall pulses required, aim for 10% higher of that+10 for peace of mind
        self.camera_framerate_Hz = self.camera.cam.get_attribute_value("FrameRate") # in Hz
        # Print camera framerate, for reference
        self.append_history('Camera framerate:  %.2f Hz'%(self.camera_framerate_Hz))
        # self.append_history('Camera frame period: %.6f s'%(self.camera.cam.get_frame_period())) # This is just 1/framerate, but seems glitchier... gave errors when I tried it by itself
        self.fall_extra_pulsesbursts = int(np.ceil(1.1*((self.camera_framerate_Hz)**(-1)-self.camera_exp_time_s)*self.p2p_rate + 10))
        self.camera.dump_settings(path=self.datafolder)
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:
                r_val = self.rise_fall_pulsesbursts
                g_val = self.probe_pulsesbursts
                b_val = self.rise_fall_pulsesbursts + self.fall_extra_pulsesbursts # self.ui.a_fall_pulsesbursts.value()
                burst_array = (r_val, g_val, b_val, r_val, g_val, b_val, 0, 0)
                self.sepia2.SOMD_SetBurstLengthArray(self.s2_iDevIdx, self.s2_osc_slotId, burst_array)
                self.append_history('set_pulsesbursts() successful')
            except Exception as e:
                self.append_history("set_pulsesbursts() failed:")
                self.append_history(str(e))
                self.append_history('Please check Acquire Options!')
                # self.message_error_set_pulsesbursts(str(e))
                # raise # Kill the rest of the event loop, can't continue with no connection to Sepia2
                # @todo is commenting out this raise problematic?
            print('self.fall_extra_pulsesbursts = ' + str(self.fall_extra_pulsesbursts))
    
    def set_on_off_pairs(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_probe_on_off_pairs.setValue(self.ui.d_probe_on_off_pairs.value())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_probe_on_off_pairs.setValue(self.ui.a_probe_on_off_pairs.value())
        # Update number of shots
        self.num_shots = 2*self.ui.a_probe_on_off_pairs.value() # 2 shots per pair

    def set_delay_diagnostics(self):
        # special case, assumes UI has been updated by human
        # This only matters for diagnostics mode
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.set_delay(self.ui.d_time.value())

    def set_delay(self, t_sw):
        if self.mock:
            return
        """
        Triggered automatically by diagnostics tab, triggered as part of acquisition routine.
        t_0 is time zero
        t_sw is the value shown in time options
        t_sw = t_pass - t_0
        """
        t_0 = self.ui.a_t0.value()
        # Synchronise GUI (@todo, this may vary between tabs as they have independent timing
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_t0.setValue(self.ui.d_t0.value())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_t0.setValue(self.ui.a_t0.value())
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            print('Starting to set new delay')
            try:
                mask_1 = 0b00000001
                # mask_2 = 0b00000010 # Note, these refer to 'Combi'
                mask_2_5 = 0b00010010 # Combi 2 and 5
                # rise/red (1)
                self.sepia2.SOMD_SetSeqOutputInfos(self.s2_iDevIdx, self.s2_osc_slotId, 0, False, mask_1, False, 0, 0)
                # probe/green (2 & 3) note 2 is probe, 3 is pump
                # timezero is ps (coarse == 700ps, fine == 22.5ps)
                # IMPORTANT! NEED PUMP TO ARRIVE BEFORE PROBE
                # NOTE LEADING MINUS SIGN ON THE NEXT LINE - BECAUSE WE ARE DELAYING THE PUMP RELATIVE TO THE PROBE
                t_pass = - ( t_sw + t_0 )
                fCoarseDly_int = t_pass // 700 # integer division; note this represents integer multiples of 0.7ns
                bFineDly = round((t_pass - (fCoarseDly_int*700)) / 22.5) # fine delay to be applied, in a.u.
                fCoarseDly = 0.7 * fCoarseDly_int
                # note that fCoarseDly is neccessarily passed to SOMD_SetSeqOutputInfos() as a float (in ns units)
                # it's not passed as a integer in the way that bFineDly is (1a.u. == 22.5ps)
                self.sepia2.SOMD_SetSeqOutputInfos(self.s2_iDevIdx, self.s2_osc_slotId, 1, True, mask_1, False, fCoarseDly, bFineDly)
                self.sepia2.SOMD_SetSeqOutputInfos(self.s2_iDevIdx, self.s2_osc_slotId, 2, False, mask_1, False, 0, 0)
                # fall/blue (4)
                self.sepia2.SOMD_SetSeqOutputInfos(self.s2_iDevIdx, self.s2_osc_slotId, 3, False, mask_1, False, 0, 0)
                # unused (5,6,7,8)
                self.sepia2.SOMD_SetSeqOutputInfos(self.s2_iDevIdx, self.s2_osc_slotId, 4, False, mask_2_5, False, 0, 0)
                self.sepia2.SOMD_SetSeqOutputInfos(self.s2_iDevIdx, self.s2_osc_slotId, 5, False, mask_1, False, 0, 0)
                self.sepia2.SOMD_SetSeqOutputInfos(self.s2_iDevIdx, self.s2_osc_slotId, 6, False, mask_1, False, 0, 0)
                self.sepia2.SOMD_SetSeqOutputInfos(self.s2_iDevIdx, self.s2_osc_slotId, 7, False, mask_1, False, 0, 0)
            except Exception as e:
                self.append_history("set_delay() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2  
            print('Finished setting new delay')

    def set_miscellaneous(self):
        if self.mock:
            return
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:
                # (not covered by stroboPY GUI)
                """
                  0: free running
                  1: running / restarting, if AUX IN is on logical High level,
                  2: running / restarting, if AUX IN is on logical Low level.
                  3: disabled / restarting on neither level at AUX IN.
                """
                bAUXInCtrl = 0 # free running
                # bAUXInCtrl = 1 # running / restarting, if AUX IN is on logical High level
                self.sepia2.SOMD_SetAUXIOSequencerCtrl(self.s2_iDevIdx, self.s2_osc_slotId, True, bAUXInCtrl)
            except Exception as e:
                self.append_history("set_miscellaneous() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2

    def set_outenabled(self):
        # set_outenabled(self, pump_fire=1):
        if self.mock:
            return
        """
        Note this is distinct to set_softlock function
        @param pump_fire is used here for distinguishing the pump on vs. pump off sequencing with camera-to-laser driver triggering.
        1 is case for pump on, 0 is case for pump off.
        Should always be 1 in the case of laser driver-to-camera triggering...
        ...but it resulted in a stange bug, so I just removed it (09.05.2025), see comments
        """
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_pump_outenabled_cb.setChecked(self.ui.d_pump_outenabled_cb.isChecked())
            self.ui.a_probe_outenabled_cb.setChecked(self.ui.d_probe_outenabled_cb.isChecked())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_pump_outenabled_cb.setChecked(self.ui.a_pump_outenabled_cb.isChecked())
            self.ui.d_probe_outenabled_cb.setChecked(self.ui.a_probe_outenabled_cb.isChecked())
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:
                # mask_1 = 0b00000001 # sync output pulse
                # mask_2 = 0b00000010
                mask_1_4 = 0b00001001
                # Pump(row 2), Probe(row 5)
                # '|' is equivalent to 'or'
                # << and >> are operators that shift numbers in base 2
                # Hard to explain. Try typing bin(0<<4|0<<1) etc. in console
                enable_mask = (self.ui.a_probe_outenabled_cb.isChecked() << 4) | (self.ui.a_pump_outenabled_cb.isChecked() << 1)
                # pump_fire*self.ui.a_pump_outenabled_cb.isChecked() originally in the latter...
                # ... but would output 2 - no idea why
                # print('enable mask = ' + str(bin(enable_mask)))
                self.sepia2.SOMD_SetOutNSyncEnable(self.s2_iDevIdx, self.s2_osc_slotId, enable_mask, mask_1_4, True)
            except Exception as e:
                self.append_history("set_outenabled() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2

    def set_intensity_pump(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_pump_intensity.setValue(self.ui.d_pump_intensity.value())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_pump_intensity.setValue(self.ui.a_pump_intensity.value())
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:
                self.sepia2.SLM_SetIntensityFineStep(self.s2_iDevIdx, self.s2_pump_slotId, int(self.ui.a_pump_intensity.value()*10))
            except Exception as e:
                self.append_history("set_intensity_pump() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2

    def set_intensity_probe(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_probe_intensity.setValue(self.ui.d_pump_intensity.value())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_pump_intensity.setValue(self.ui.a_probe_intensity.value())
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:
                self.sepia2.SLM_SetIntensityFineStep(self.s2_iDevIdx, self.s2_probe_slotId, int(self.ui.a_probe_intensity.value()*10))
            except Exception as e:
                self.append_history("set_intensity_probe() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2

    def set_pulsed_pump(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_pump_pulsed_cb.setChecked(self.ui.d_pump_pulsed_cb.isChecked())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_pump_pulsed_cb.setChecked(self.ui.a_pump_pulsed_cb.isChecked())
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:
                """
                >>> t.SLM_DecodeFreqTrigMode(0): '80 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(1): '40 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(2): '20 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(3): '10 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(4): ' 5 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(5): ' 2.5 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(6): 'rising  edge (ext.)'
                >>> t.SLM_DecodeFreqTrigMode(7): 'falling edge (ext.)'
                """
                iFreq = 7 # falling_edge (not covered by stroboPY GUI)
                self.sepia2.SLM_SetPulseParameters(self.s2_iDevIdx, self.s2_pump_slotId, iFreq, self.ui.a_pump_pulsed_cb.isChecked())
            except Exception as e:
                self.append_history("set_pulsed_pump() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2

    def set_pulsed_probe(self):
        if self.mock:
            return
        # Synchronise GUI
        if (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.diagnostics_tab)):
            self.ui.a_probe_pulsed_cb.setChecked(self.ui.d_probe_pulsed_cb.isChecked())
        elif (self.ui.tabs.currentIndex() == self.ui.tabs.indexOf(self.ui.acquisition_tab)):
            self.ui.d_probe_pulsed_cb.setChecked(self.ui.a_probe_pulsed_cb.isChecked())
        # If connected to Sepia2, update value
        if self.sepia2.USB_IsOpenDevice(self.s2_iDevIdx):
            try:                
                """
                >>> t.SLM_DecodeFreqTrigMode(0): '80 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(1): '40 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(2): '20 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(3): '10 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(4): ' 5 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(5): ' 2.5 MHz (int.)'
                >>> t.SLM_DecodeFreqTrigMode(6): 'rising  edge (ext.)'
                >>> t.SLM_DecodeFreqTrigMode(7): 'falling edge (ext.)'
                """
                iFreq = 7 # falling_edge (not covered by stroboPY GUI)
                self.sepia2.SLM_SetPulseParameters(self.s2_iDevIdx, self.s2_probe_slotId, iFreq, self.ui.a_probe_pulsed_cb.isChecked())
            except Exception as e:
                self.append_history("set_pulsed_probe() failed:")
                self.append_history(str(e))
                raise # Kill the rest of the event loop, can't continue with no connection to Sepia2
    
    start_acquisition_thread = pyqtSignal()
    stop_acquisition_thread = pyqtSignal()
    def run_acquisition(self):
        self.append_history('Launching Run!')
        
        # Mark run as having started (e.g. disable UI)
        # @todo Disable interface options that would update Sepia?
        self.stop_request = False
        self.diagnostics_on = False
        self.running()
        self.finished_acquisition = False
        
        # Reset graphs
        self.ui.a_kinetic_graph.clear()
        self.ui.a_spectra_graph.clear()
        self.ui.a_last_shot_graph.clear()
        self.ui.a_timedelay_slider.setMaximum(0)
        self.ui.a_timedelay_label.setText("Time Delay")
        
        # Reset storage
        # This is for the time slider
        self.acquisition_i_off = dict()
        self.acquisition_i_on = dict()
        self.acquisition_i_off_ct = dict() # ct means count times: how many to average in the time slider
        self.acquisition_i_on_ct = dict() # ct means count times: how many to average in the time slider
        
        # Initialise progress bars
        self.ui.a_sweep_display.display(1)
        self.ui.a_time_display.display("")
        self.ui.a_sweep_progress_bar.setMaximum(len(self.times))
        self.ui.a_measurement_progress_bar.setMaximum(len(self.times)*self.ui.a_num_sweeps.value())
        self.ui.a_sweep_progress_bar.setValue(0)
        self.ui.a_measurement_progress_bar.setValue(0)
        
        # Initialise sweep processing
        self.read_gui_values() # refresh self.last_instance_values
        self.current_sweep = SweepProcessing(self.times,self.camera.num_pixels,self.filepath,self.last_instance_values)
        self.current_sweep.make_tif_folder()
        self.current_sweep.save_metadata()
        
        # Turn laser soft lock off
        self.set_softlock(False)
        
        # Initialise acquisition routine in separate thread
        self.acquire_thread = QtCore.QThread()
        # dcshotfactor = 1 # pyTA holdover
        #np.tile just causes the array to be appended to itself n times, creating the sweeps
        self.acquisition = Acquisition(self.camera, self, np.tile(self.times, self.ui.a_num_sweeps.value()), number_of_scans=self.num_shots)
        self.acquisition.moveToThread(self.acquire_thread)
        self.acquisition.frames_ready.connect(self.process_acquisition_frames)
        self.acquisition.acquisition_complete.connect(self.acquisition_complete)
        self.start_acquisition_thread.connect(self.acquisition.run)
        self.stop_acquisition_thread.connect(self.acquisition.stop)
        self.acquire_thread.start()
        # Actually start acquisition thread in background
        self.start_acquisition_thread.emit()
        # Return to event loop
    
    def stop_acquisition(self):
        self.append_history('Stopping')
        self.stop_acquisition_thread.emit()
    
    @pyqtSlot(float, np.ndarray, np.ndarray, int)
    def process_acquisition_frames(self, t_sw, pump_on, pump_off, first_pixel):
        """
        Triggered in event loop, each time a set of frames from an acquisition pass are available
        @param t_sw Value of time t_sw for the given set of frames
        @param pump_on Pump on frames (may contain None if frames were skipped)
        @param pump_off Pump off frames (may contain None if frames were skipped)
        @param first_pixel First pixel, 0 for Andor
        """
        print("Frames for t_sw = %f received!"%(t_sw))
        # Update UI status
        # work this all out backwards based on quantity of results delivered
        # (rather than trying to steal data from acquisition thread)
        last_measurement_progress = self.ui.a_measurement_progress_bar.value()
        new_measurement_progress = last_measurement_progress + 1
        self.ui.a_sweep_display.display((last_measurement_progress // len(self.times)) + 1)
        self.ui.a_time_display.display(t_sw)
        sweep_progress_zero = np.where(self.times == t_sw)[0][0] # 0th, 1st, 2nd, ... time point
        self.ui.a_sweep_progress_bar.setValue(sweep_progress_zero + 1)
        self.ui.a_measurement_progress_bar.setValue(new_measurement_progress)
        # Update bottom left image, with I_off (probe_off?)
        # bl_img = QImage(probe_off[0], self.camera.num_pixels[0], self.camera.num_pixels[1], QImage.Format_Grayscale16)
        # bl_pmap = QGraphicsPixmapItem(QPixmap.fromImage(bl_img))
        self.ui.a_kinetic_graph.clear()
        # self.ui.a_kinetic_graph.addItem(bl_pmap)
        # Update bottom right image with (I_on - I_off)/I_off
        # Need to do some data type fiddling here to avoid underflow
        # avoid div0 with numpy.divide(a-b, b, where=b!=0) or similar
        i_off_avg = np.mean(pump_off, axis=0)
        self.ui.a_kinetic_graph.setImage(i_off_avg.T, autoRange=0)
        print("Updated bottom-left graph")
        # print(pump_off[0])
        print('Size of array: ' + str(np.array(pump_off[0]).shape))
        # br_data = (i_on - i_off)/i_off = (i_on/i_off) - 1
        # Calculate based on RHS as less computationally expensive
        br_data = np.divide(np.array(pump_on, dtype=np.float64), np.array(pump_off, dtype=np.float64), out=np.zeros_like(pump_off, dtype=np.float64), where=np.array(pump_off, dtype=np.float64)!=0)
        br_data = np.mean(br_data, axis=0) - 1.0
        # out=np.zeros_like(pump_off, dtype=np.float64), where=pump_off!=0
        # br_data += 1 # centralise value, to avoid negatives being out of range
        # br_data *= np.iinfo(np.uint16).max/2 # scale back to within uint16 range. Note: np.iinfo(np.uint16).max = 65535
        # br_img = QImage(br_data.astype(np.uint16), self.camera.num_pixels[0], self.camera.num_pixels[1], QImage.Format_Grayscale16)
        # br_pmap = QGraphicsPixmapItem(QPixmap.fromImage(br_img))
        print("Finished mean calculation")
        # print(br_data)
        self.ui.a_spectra_graph.clear()
        self.ui.a_spectra_graph.setImage(br_data.T, autoRange=0) # note the blacks shown appear to be NaN
        print("Updated bottom-right graph")
        # Store image data for cycling - for the time slider
        # =====
        # if not t_sw in self.acquisition_i_off:
        #     self.acquisition_i_off[t_sw] = np.zeros((self.camera.num_pixels[0], self.camera.num_pixels[1]), dtype=np.int32)
        #     self.acquisition_i_off_ct[t_sw] = 0
        # if not t_sw in self.acquisition_i_on:
        #     self.acquisition_i_on[t_sw] = np.zeros((self.camera.num_pixels[0], self.camera.num_pixels[1]), dtype=np.int32)
        #     self.acquisition_i_on_ct[t_sw] = 0
        # for img in pump_off:
        #     self.acquisition_i_off[t_sw] += img
        # self.acquisition_i_off_ct[t_sw] += len(pump_off)
        # for img in pump_on:
        #     self.acquisition_i_on[t_sw] += img
        # self.acquisition_i_on_ct[t_sw] += len(pump_on)
        # # Update time_delay slider max during first sweep
        # if len(self.acquisition_i_off) - 1 > self.ui.a_timedelay_slider.maximum():
        #     self.ui.a_timedelay_slider.setMaximum(sweep_progress_zero)
        #     self.ui.a_timedelay_slider.setEnabled(True)
        # # Trigger right panel update on first result or when slider == t_sw
        # time_slider_val = self.ui.a_timedelay_slider.value()
        # if len(self.acquisition_i_off) == 1 or self.times[time_slider_val] == t_sw:
        #     self.acquisition_slider_changed(time_slider_val)
        # print("Updated slider and top-right graph")
        # =====
        
        print(sweep_progress_zero)
        self.current_sweep.add_current_data(br_data, i_off_avg, sweep_progress_zero)
        
        #says we have reached end of a sweep
        if sweep_progress_zero == len(self.times)-1:
            self.post_sweep()
        
    @pyqtSlot()
    def acquisition_complete(self):
        """
        Triggered in event loop thread when self.acquisition::run() exits
        Returns UI to enabled state
        """
        # self.post_sweep()
        self.acquire_thread.quit()
        self.append_history('Stopped')
        self.set_softlock(True)
        
        self.idling()
        pass
    
    def acquisition_slider_changed(self, index):
        """
        Triggered when user moves the time_delay slider on acquisition TabError
        This should trigger the top-right image to be updated.
        """
        t_sw = self.times[index]
        # Update label
        self.ui.a_timedelay_label.setText("Time Delay: %.3f"%(t_sw))
        # Recalculate and update top-right image
        # (i_on - i_off) / i_off (for all currently collected sweeps averaged
        i_on = self.acquisition_i_on[t_sw] 
        i_off = self.acquisition_i_off[t_sw] 
        # avoid div0 with numpy.divide(a-b, b, where=b!=0) or similar
        #i_diff = (i_on - i_off)/(i_off + 1)
        i_diff = np.divide((i_on - i_off), i_off, out=np.zeros_like(i_off, dtype=np.float64), where=i_off!=0)
        # Convert sum to average
        # @note This assumes acquisition_i_off_ct == acquisition_i_on_ct
        i_diff /= self.acquisition_i_off_ct[t_sw]
        # i_diff += 1 # centralise value, to avoid negatives being out of range
        # i_diff *= np.iinfo(np.uint16).max/2 # scale back to within uint16 range
        # i_diff_img = QImage(i_diff.astype(np.uint16), self.camera.camera.num_pixels[0], self.camera.camera.num_pixels[1], QImage.Format_Grayscale16)
        # i_diff_pmap = QGraphicsPixmapItem(QPixmap.fromImage(i_diff_img))
        self.ui.a_last_shot_graph.clear()
        self.ui.a_last_shot_graph.setImage(i_diff.T, autoRange=0)
    
    """
    GUI save/load to/from last_instance_values.txt
    """
    def read_gui_values(self):
        # Sync to ensure shared tabs are in sync
        self.sync_tabs(-1)
        self.last_instance_values = {}
        # Date and time
        self.last_instance_values['date (yyyy-mm-dd)'] = str(datetime.date.today()) # (ref)
        self.last_instance_values['time (hh:mm:ss)'] = str(datetime.datetime.now().strftime('%H:%M:%S')) # (ref)
        self.last_instance_values['timezone'] = str(datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()) # (ref)
        # Hardware tab
        # Camera Connection
        self.last_instance_values['camera selection'] = self.ui.h_camera_dd.currentIndex()
        self.last_instance_values['camera selection text'] = self.ui.h_camera_dd.currentText() # (ref) for easy reading of metadata; not read from last_instance_values.txt
        # Sepia2 Connection
        self.last_instance_values['usb index'] = self.ui.h_sepia2_usb.value()
        self.last_instance_values['controller slot'] = self.ui.h_sepia2_controllerslot.value()
        self.last_instance_values['oscillator slot'] = self.ui.h_sepia2_oscillatorslot.value()
        self.last_instance_values['pump slot'] = self.ui.h_sepia2_pumpslot.value()
        self.last_instance_values['probe slot'] = self.ui.h_sepia2_probeslot.value()        
        # Acquisition tab
        # Filename & Metadata
        self.last_instance_values['filename'] = self.ui.a_filename_le.text() # (ref)
        self.last_instance_values['filepath'] = self.ui.a_filepath_le.text() # (ref)
        self.last_instance_values['a metadata pump wavelength'] = self.ui.a_metadata_pump_wavelength.text()
        self.last_instance_values['a metadata pump power'] = self.ui.a_metadata_pump_power.text()
        self.last_instance_values['a metadata pump spotsize'] = self.ui.a_metadata_pump_spotsize.text()
        self.last_instance_values['a metadata probe wavelength'] = self.ui.a_metadata_probe_wavelength.text()
        self.last_instance_values['a metadata probe power'] = self.ui.a_metadata_probe_power.text()
        # Camera AOI
        self.last_instance_values['aoi height'] = self.ui.a_AOI_height.value()
        self.last_instance_values['aoi width'] = self.ui.a_AOI_width.value()
        self.last_instance_values['pixel binning'] = self.ui.a_pixel_binning_dd.currentIndex()
        self.last_instance_values['pixel binning text'] = self.ui.a_pixel_binning_dd.currentText() # (ref)
        # Acquire Options (shared with diagnostics)
        self.last_instance_values['t0'] = self.ui.a_t0.value()
        self.last_instance_values['baseosctrigger'] = self.ui.a_baseosctrigger_dd.currentIndex()
        self.last_instance_values['baseosctrigger text'] = self.ui.a_baseosctrigger_dd.currentText() # (ref)
        self.last_instance_values['divider'] = self.ui.a_divider.value()
        self.last_instance_values['rep. rate (MHz)'] = self.ui.a_p2p_rate.text() # (ref)
        self.last_instance_values['p2p time (ns)'] = self.ui.a_p2p_time.text() # (ref)
        # Pulses/Bursts
        self.last_instance_values['rise fall exp time (us)'] = self.ui.a_rise_fall_exp_time.value()
        self.last_instance_values['probe exp time (ms)'] = self.ui.a_probe_exp_time.value()
        self.last_instance_values['on off pairs'] = self.ui.a_probe_on_off_pairs.value()
        try: # Use a try here, as will error if a user exits the program without connecting anything
            self.last_instance_values['camera framerate (Hz)'] = '%.2f'%(self.camera_framerate_Hz) # (ref)
        except:
            pass
        # Pump
        self.last_instance_values['pump outenabled'] = self.ui.a_pump_outenabled_cb.isChecked()
        self.last_instance_values['pump pulsed'] = self.ui.a_pump_pulsed_cb.isChecked()
        self.last_instance_values['pump intensity (%)'] = self.ui.a_pump_intensity.value()
        # Probe
        self.last_instance_values['probe outenabled'] = self.ui.a_probe_outenabled_cb.isChecked()
        self.last_instance_values['probe pulsed'] = self.ui.a_probe_pulsed_cb.isChecked()
        self.last_instance_values['probe intensity (%)'] = self.ui.a_probe_intensity.value()
        # Time Options
        self.last_instance_values['distribution'] = self.ui.a_distribution_dd.currentIndex()
        self.last_instance_values['distribution text'] = self.ui.a_distribution_dd.currentText() # (ref)
        self.last_instance_values['timefile folder'] = self.timefile_folder
        self.last_instance_values['timefile path'] = self.ui.a_timefile_list.currentText()
        self.last_instance_values['tstart (ps)'] = self.ui.a_tstart_sb.value()
        self.last_instance_values['tend (ps)'] = self.ui.a_tend_sb.value()
        self.last_instance_values['num tpoints'] = self.ui.a_num_tpoints_sb.value()
        self.last_instance_values['num sweeps'] = self.ui.a_num_sweeps.value()
        # Diagnostics tab
        # Time
        self.last_instance_values['d time (ps)'] = self.ui.d_time.value()
        self.last_instance_values['d jogstep (ps)'] = self.ui.d_jogstep_sb.value()
    
    def save_gui_values_dict(self, filepath, filename):
        '''
        Perform export to human-readable txt file
        Note: sweeps.py has a separate (similar) function to save this in the measurement folder
        '''
        with open(os.path.join(filepath, filename), 'w') as f:
            for key, value in self.last_instance_values.items():
                # Write lines in '{key}: {value}' format
                f.write(f'{key}: {value}\n')
        
    def save_gui_values_pickle(self):
        '''
        Perform export to machine-readable txt file
        pickle is used as it annotates what's an integer, float, etc.
        '''
        with open(self.last_instance_filename, 'wb') as file:
            pickle.dump(self.last_instance_values, file, protocol=0)

    def load_gui_values(self, last_vals):
        """
        Sets GUI values from the passed dictionary last_vals, otherwise sets a default value
        """
        # Hardware tab
        # Camera Connection
        self.ui.h_camera_dd.setCurrentIndex(last_vals.get('camera selection',0))
        # Sepia2 Connection
        self.ui.h_sepia2_usb.setValue(last_vals.get('usb index', 0))
        self.ui.h_sepia2_controllerslot.setValue(last_vals.get('controller slot', 000))
        self.ui.h_sepia2_oscillatorslot.setValue(last_vals.get('oscillator slot', 100))
        self.ui.h_sepia2_pumpslot.setValue(last_vals.get('pump slot', 200))
        self.ui.h_sepia2_probeslot.setValue(last_vals.get('probe slot', 300))
        # Acquisition tab
        # Filename & Metadata
        self.ui.a_metadata_pump_wavelength.setText(last_vals.get('a metadata pump wavelength',""))
        self.ui.a_metadata_pump_power.setText(last_vals.get('a metadata pump power',""))
        self.ui.a_metadata_pump_spotsize.setText(last_vals.get('a metadata pump spotsize',""))
        self.ui.a_metadata_probe_wavelength.setText(last_vals.get('a metadata probe wavelength',""))
        self.ui.a_metadata_probe_power.setText(last_vals.get('a metadata probe power',""))
        # AOI and Binning (shared with diagnostics)
        self.ui.a_AOI_height.setValue(last_vals.get('aoi height', 128))
        self.ui.a_AOI_width.setValue(last_vals.get('aoi width', 128))
        self.ui.a_pixel_binning_dd.setCurrentIndex(last_vals.get('pixel binning', 0))
        # Acquire Options (shared with diagnostics)
        self.ui.a_t0.setValue(last_vals.get('t0', 0))
        self.ui.a_baseosctrigger_dd.setCurrentIndex(last_vals.get('baseosctrigger', 0))
        self.ui.a_divider.setValue(last_vals.get('divider', 40))
        # Pulses/Bursts
        self.ui.a_rise_fall_exp_time.setValue(last_vals.get('rise fall exp time (us)', 75)) # microseconds
        self.ui.a_probe_exp_time.setValue(last_vals.get('probe exp time (ms)', 1.3)) # milliseconds
        self.ui.a_probe_on_off_pairs.setValue(last_vals.get('on off pairs', 1000)) # number of pairs
        # Pump
        self.ui.a_pump_outenabled_cb.setChecked(last_vals.get('pump outenabled', False))
        self.ui.a_pump_pulsed_cb.setChecked(last_vals.get('pump pulsed', True))
        self.ui.a_pump_intensity.setValue(last_vals.get('pump intensity (%)', 0))
        # Probe
        self.ui.a_probe_outenabled_cb.setChecked(last_vals.get('probe outenabled', False))
        self.ui.a_probe_pulsed_cb.setChecked(last_vals.get('probe pulsed', True))
        self.ui.a_probe_intensity.setValue(last_vals.get('probe intensity (%)', 0))
        # Time Options
        self.ui.a_distribution_dd.setCurrentIndex(last_vals.get('distribution', 1))
        if self.ui.a_distribution_dd.currentIndex() == 2: # if 'From file'...
            self.append_history('Previously a timefile was used! Location:')
            self.append_history(os.path.join(last_vals.get('timefile folder'),last_vals.get('timefile path')))
        # @todo Code in timefile memory, and error handling if it moves or gets renamed.
        # Attempted but too many annoying exceptions
        # so it just returns to a default .tf for now even if the previous timefile is OK (i.e. not removed or renamed)
        # try:
        #     self.timefile_folder = last_vals.get('timefile folder')
        #     self.timefile = last_vals.get('timefile path')
        #     self.load_timefiles_to_list()
        #     self.update_times_from_file()
        # except Exception as e:
        #     self.append_history('Previous timefile loading failed! Re-locate it?')
        #     self.append_history(str(e))
        #     self.timefile_folder = os.getcwd()
        #     self.timefile = 'timefile_default.tf'
        self.timefile_folder = os.getcwd()
        self.timefile = 'timefile_default.tf'
        self.load_timefiles_to_list()
        self.update_times_from_file()
        self.ui.a_tstart_sb.setValue(last_vals.get('tstart (ps)', -1000))
        self.ui.a_tend_sb.setValue(last_vals.get('tend (ps)', 10000))
        self.ui.a_num_tpoints_sb.setValue(last_vals.get('num tpoints', 12))
        self.ui.a_num_sweeps.setValue(last_vals.get('num sweeps', 5))
        
        # Diagnostics tab
        # Time
        self.ui.d_time.setValue(last_vals.get('d time (ps)', 0))
        self.ui.d_jogstep_sb.setValue(last_vals.get('d jogstep (ps)', 0.01))
            
        # Sync to diagnostics as we have init acquisition
        self.sync_to_diagnostics_tab()
    
    def update_cameratype(self):
        ## @todo, this can be moved to camera connect??
        self.cameratype = self.ui.h_camera_dd.currentText()
        return

    def update_filepath(self):
        self.filename = self.ui.a_filename_le.text()
        self.filepath = os.path.join(self.datafolder, self.filename)
        self.ui.a_filepath_le.setText(self.filepath)
        return
   
    def exec_folder_browse_btn(self):
        self.datafolder = QtWidgets.QFileDialog.getExistingDirectory(None, 'Select Folder', self.datafolder)
        self.datafolder = os.path.normpath(self.datafolder)
        self.update_filepath()
        return
    
    # deprecated in stroboPY
    # def metadata_changed(self):
    #     self.metadata['pump wavelength'] = self.ui.a_metadata_pump_wavelength.text()
    #     self.metadata['pump power'] = self.ui.a_metadata_pump_power.text()
    #     self.metadata['pump size'] = self.ui.a_metadata_pump_spotsize.text()
    #     self.metadata['probe wavelengths'] = self.ui.a_metadata_probe_wavelength.text()
    #     self.metadata['probe power'] = self.ui.a_metadata_probe_power.text()
    
    # deprecated in stroboPY
    # def update_metadata(self):
    #     self.metadata_changed()
    #     #self.metadata['num shots'] = self.num_shots  # these tell you what options/values were specified in the GUI
    #     #self.metadata['calib pixel low'] = self.calib[0]
    #     #self.metadata['calib pixel high'] = self.calib[1]
    #     #self.metadata['calib wave low'] = self.calib[2]
    #     #self.metadata['calib wave high'] = self.calib[3]
    #     #self.metadata['cutoff low'] = self.cutoff[0]
    #     #self.metadata['cutoff high'] = self.cutoff[1]
        
    def update_use_timefile(self):
        self.use_timefile = (self.ui.a_distribution_dd.currentIndex() == 2)
        print('self.use_timefile = ' + str(self.use_timefile))
        if self.use_timefile:
            # self.ui.a_distribution_dd.setEnabled(False) # not using the checkbox any more, as of 21.11.2025
            self.ui.a_tstart_sb.setEnabled(False)
            self.ui.a_tend_sb.setEnabled(False)
            self.ui.a_num_tpoints_sb.setEnabled(False)
            self.ui.a_timefile_btn.setEnabled(True)
            self.ui.a_timefile_list.setEnabled(True)
        else:
            # self.ui.a_distribution_dd.setEnabled(True)
            self.ui.a_tstart_sb.setEnabled(True)
            self.ui.a_tend_sb.setEnabled(True)
            self.ui.a_num_tpoints_sb.setEnabled(True)
            self.ui.a_timefile_btn.setEnabled(False)
            self.ui.a_timefile_list.setEnabled(False)
            self.update_times()
        return
            
    def update_times(self):
        distribution = self.ui.a_distribution_dd.currentText()
        if distribution == 'From file':
            self.update_times_from_file()
            return # i.e. don't proceed with the rest of this function
        elif distribution == 'Linear':
            self.ui.a_num_tpoints_sb.setMinimum(5)
        elif distribution == 'Exponential':
            self.ui.a_num_tpoints_sb.setMinimum(25)
        else: # I think update_times is invoked several times, well before the distribution is set/recalled...
            pass # So pass the first few times it's invoked to avoid 5 changing to 25.
        start_time = self.ui.a_tstart_sb.value()
        end_time = self.ui.a_tend_sb.value()
        num_points = self.ui.a_num_tpoints_sb.value()
        times = np.linspace(start_time, end_time, num_points)
        if distribution == 'Exponential':
            times = self.calculate_times_exponential(start_time, end_time, num_points)
        self.times = times
        self.display_times()
        return
    
    def update_step_order(self):
        # Not invoked anywhere yet!
        step_order = self.ui.a_steporder_dd.currentText()
        if step_order == 'Linear':
            pass
    
    def update_p2p_time_rate(self):
        '''
        Re-calculates the pulse-to-pulse (P2P) time (cf. maximum delay time) if
        the base oscillation or the divider is changed.
        Basically P2P Time = Divider / BaseOsc
        Units are seconds (s) for now.
        Also calculates the P2P rate, which is just the inverse.
        '''
        # Define some mapping to convert into floats
        # Mainly for this update_p2p_time function
        # cf: iFreqTrigModeMap
        FloatMap = {
            # External triggers will never be used for oscillator
            #"rising  edge (ext.)": 0,
            #"falling edge (ext.)": 1,
            "80.00 MHz (int. A)": 80.0e6,
            "64.00 MHz (int. B)": 64.0e6,
            "50.00 MHz (int. C)": 50.0e6,
        }

        Divider = self.ui.a_divider.value() # Integer
        try:
            BaseOsc = FloatMap[self.ui.a_baseosctrigger_dd.currentText()] # Float
        except:
        # If it can't get a BaseOsc reading... just use 80MHz.
        # Possibly when this function is called later, it can get a sensible BaseOsc, which overwrites 80MHz
            BaseOsc = 80.0e6
        self.p2p_time = Divider/BaseOsc
        self.p2p_rate = 1/self.p2p_time
        self.display_p2p_time_rate()
        return
    
    def update_pulsesbursts(self):
        '''
        Calculates the number of pulses required in the bursts of Sepia II,
        given the rise/fall buffer and probe/lasing exposure times.
        It uses the P2P rate for this.
        Also calculates the total camera exposure time (rise + probe + fall)
        that is required.
        Watch out for the unit prefixes.
        Note that this doesn't calculate the extra pulses applied to the fall
        to account for the camera frame rate being less than 1/exposure time.
        That is calculated elsewhere.
        '''
        rise_fall_exp_time = self.ui.a_rise_fall_exp_time.value() # in us
        rise_fall_exp_time /= 1.0e6 # converted to s
        rise_fall_pulsesbursts = rise_fall_exp_time * self.p2p_rate
        self.rise_fall_pulsesbursts = int(round(rise_fall_pulsesbursts)) # Note, necessarily an integer for Sepia II
        print('self.rise_fall_pulsesbursts = ' + str(self.rise_fall_pulsesbursts))
        
        probe_exp_time = self.ui.a_probe_exp_time.value() # in ms
        probe_exp_time /= 1.0e3 # converted to s
        probe_pulsesbursts = probe_exp_time * self.p2p_rate
        self.probe_pulsesbursts = int(round(probe_pulsesbursts)) # Note, necessarily an integer for Sepia II
        print('self.probe_pulsesbursts = ' + str(self.probe_pulsesbursts))
        
        self.camera_exp_time_s = probe_exp_time + 2*rise_fall_exp_time
        
        return
    
    def display_p2p_time_rate(self):
        '''
        Just updates the display for these in the GUI...
        @todo add a 'Check' button in the GUI that outputs the P2P time, P2P rate, number of pulses in the bursts... etc.?
        Might be nice to clean up the GUI from these...
        Also less cumbersome than constantly appending the console or the history.
        '''
        self.ui.a_p2p_time.clear()
        self.ui.a_p2p_rate.clear()
        self.ui.a_p2p_time.setText('{0:.1f}'.format(self.p2p_time*1e9))
        self.ui.a_p2p_rate.setText('{0:.2f}'.format(self.p2p_rate*1e-6))
        return
    
    def exec_timefile_folder_btn(self):
        self.timefile = QtWidgets.QFileDialog.getOpenFileName(None, 'Select TimeFile', self.timefile_folder, 'TimeFiles (*.tf)')
        self.timefile_folder = os.path.dirname(self.timefile[0])
        if self.timefile_folder.endswith('/'):
            self.timefile_folder = self.timefile_folder[:-1]
        self.timefile = os.path.basename(self.timefile[0])
        self.load_timefiles_to_list()
        return
        
    def load_timefiles_to_list(self):
        # @todo Enumerating, then matching to self.timefile, yields errors if
        # we're trying to recall timefile used previously. Could do with improvement...
        self.ui.a_timefile_list.clear()
        self.timefiles = []
        for file in os.listdir(self.timefile_folder):
            if file.endswith('.tf'):
                self.timefiles.append(file)
        current_index = 0
        for i, timefile in enumerate(self.timefiles):
            self.ui.a_timefile_list.addItem(timefile)
            if timefile == self.timefile:
                current_index = i
        self.ui.a_timefile_list.setCurrentIndex(current_index)
        self.update_times_from_file()
        return
    
    def update_times_from_file(self):
        self.timefile = self.timefiles[self.ui.a_timefile_list.currentIndex()]
        self.times = np.genfromtxt(os.path.join(self.timefile_folder, self.timefile), dtype=float)
        self.display_times()
        return

    def display_times(self):
        self.ui.a_times_list.clear()
        for time in self.times:
            self.ui.a_times_list.appendPlainText('{0:.2f}'.format(time))
        return
    
    @staticmethod
    def calculate_times_exponential(start_time, end_time, num_points):
        num_before_zero = 5 # pyTA: 20
        step = 10 # pyTA: 0.1
        before_zero = np.linspace(start_time, 0, num_before_zero, endpoint=False)
        zero_onwards = np.geomspace(step, end_time+step, num_points-num_before_zero)-step
        times = np.concatenate((before_zero, zero_onwards))
        return times
    
    def update_d_time_box_limits(self):
        self.ui.d_time.setMaximum(self.delay.tmax)
        self.ui.d_time.setMinimum(self.delay.tmin)
        return
    
    # def update_xlabel(self):
    #     self.xlabel =  'Pixel Number'
    #     self.ui.a_last_shot_graph.plotItem.setLabels(bottom=self.xlabel)
    #     self.ui.a_spectra_graph.plotItem.setLabels(bottom=self.xlabel)
    #     self.ui.d_last_shot_graph.plotItem.setLabels(bottom=self.xlabel)
    #     self.ui.d_error_graph.plotItem.setLabels(bottom=self.xlabel)
    #     self.ui.d_probe_ref_graph.plotItem.setLabels(bottom=self.xlabel)
    #     return
    
    # def update_xlabel_kinetics(self):
    #     label = 'Time ({0})'.format(self.timeunits)
    #     self.ui.a_kinetic_graph.plotItem.setLabels(bottom=label)
    #     return
        
    def append_history(self, message):
        self.ui.a_history.appendPlainText(message)
        self.ui.d_history.appendPlainText(message)
        QApplication.processEvents() # Allows log to update before interface interaction has completed
        return
                       
    def create_plots(self):
        # @todo Update the following commented-out lines (due to changing from PlotWidget to ImageView)
        # self.ui.a_last_shot_graph.plotItem.setLabels(left='Distance (nm)', bottom=self.xlabel) # a for acqusition, d for diagnostics
        # self.ui.a_last_shot_graph.plotItem.showAxis('top', show=True)
        # self.ui.a_last_shot_graph.plotItem.showAxis('right', show=True)

        # self.ui.a_kinetic_graph.plotItem.setLabels(left='dtt', bottom='Time ({0})'.format(self.timeunits))
        # self.ui.a_kinetic_graph.plotItem.showAxis('top', show=True)
        # self.ui.a_kinetic_graph.plotItem.showAxis('right', show=True)
        
        # self.ui.a_spectra_graph.plotItem.setLabels(left='Distance (nm)', bottom=self.xlabel)
        # self.ui.a_spectra_graph.plotItem.showAxis('top', show=True)
        # self.ui.a_spectra_graph.plotItem.showAxis('right', show=True)
        
        self.ui.d_last_shot_graph.plotItem.setLabels(left='dtt', bottom=self.xlabel) 
        self.ui.d_last_shot_graph.plotItem.showAxis('top', show=True)
        self.ui.d_last_shot_graph.plotItem.showAxis('right', show=True)
        
        self.ui.d_error_graph.plotItem.setLabels(left='Log(Error)', bottom=self.xlabel)
        self.ui.d_error_graph.plotItem.showAxis('top', show=True)
        self.ui.d_error_graph.plotItem.showAxis('right', show=True)
        
        self.ui.d_trigger_graph.plotItem.setLabels(left='Trigger Signal', bottom='Shot Number')
        self.ui.d_trigger_graph.plotItem.showAxis('top', show=True)
        self.ui.d_trigger_graph.plotItem.showAxis('right', show=True)
        
        self.ui.d_probe_ref_graph.plotItem.setLabels(left='Counts', bottom=self.xlabel)
        self.ui.d_probe_ref_graph.plotItem.showAxis('top', show=True)
        self.ui.d_probe_ref_graph.plotItem.showAxis('right', show=True)
        
        self.probe_error_region = pg.FillBetweenItem(brush=(255, 0, 0, 50))
        #self.ui.d_probe_ref_graph.addItem(self.probe_error_region)
        self.ref_error_region = pg.FillBetweenItem(brush=(0, 0, 255, 50))
        #self.ui.d_probe_ref_graph.addItem(self.ref_error_region)
        return
    
    # def set_waves_and_times_axes(self):
    #     # wavelength/pixel axes
    #     self.waves = self.pixels_to_waves()
    #     self.plot_waves = np.linspace(0, self.camera.num_pixels-1,  self.camera.num_pixels)
    #     # time axis
    #     self.plot_times = self.times
    #     return
    
    def set_dist_and_times_axes(self):
        #set the distance (using geometric optics) and time axes
        self.dist = self.pixels_to_nms()
        self.plot_dist = self.pixels_to_nms()

        self.plot_times = self.times
        return
        
    # def create_plot_waves_and_times(self):
    #     self.set_waves_and_times_axes()

    #     if not self.diagnostics_on:
    #         self.plot_kinetic_avg = self.current_sweep.avg_data[:, self.kinetics_pixel]
    #         self.plot_kinetic_current = self.current_sweep.current_data[:, self.kinetics_pixel]
        
    #     if self.diagnostics_on is False:
    #         self.plot_dtt = self.current_sweep.avg_data[:]
            
    #     self.plot_ls = self.current_data.dtt[:]
    #     self.plot_last_shot = self.current_data.drr[:]
    #     self.plot_probe_shot_error = self.current_data.probe_shot_error[:]
        
    #     self.plot_probe_on = self.current_data.probe_on[:]
    #     self.plot_reference_on = self.current_data.reference_on[:]
    #     self.plot_probe_on_array = self.current_data.probe_on_array[:]
    #     self.plot_reference_on_array = self.current_data.reference_on_array[:]
        
    #     if self.use_cutoff is True:
    #         self.plot_waves = self.plot_waves[self.cutoff[0]:self.cutoff[1]]
            
    #         if self.diagnostics_on is False:
    #             self.plot_dtt = self.plot_dtt[:,self.cutoff[0]:self.cutoff[1]]
                
    #         self.plot_ls = self.plot_ls[self.cutoff[0]:self.cutoff[1]]
    #         self.plot_probe_shot_error = self.plot_probe_shot_error[self.cutoff[0]:self.cutoff[1]]
            
    #         self.plot_probe_on = self.plot_probe_on[self.cutoff[0]:self.cutoff[1]]
    #         self.plot_reference_on = self.plot_reference_on[self.cutoff[0]:self.cutoff[1]]
    #         self.plot_probe_on_array = self.plot_probe_on_array[:,self.cutoff[0]:self.cutoff[1]]
    #         self.plot_reference_on_array = self.plot_reference_on_array[:,self.cutoff[0]:self.cutoff[1]]        
    #     return
        
    # def create_plot_dist_and_times(self):
    #     self.set_dist_and_times_axes()

    #     if not self.diagnostics_on:
    #         self.plot_kinetic_avg = self.current_sweep.avg_data[:, self.kinetics_pixel]
    #         self.plot_kinetic_current = self.current_sweep.current_data[:, self.kinetics_pixel]
        
    #     if self.diagnostics_on is False:
    #         self.plot_dtt = self.current_sweep.avg_data[:]
            
    #     self.plot_ls = self.current_data.dtt[:]
    #     self.plot_last_shot = self.current_data.drr[:]
    #     self.plot_probe_shot_error = self.current_data.probe_shot_error[:]
        
    #     self.plot_probe_on = self.current_data.probe_on[:]
    #     self.plot_reference_on = self.current_data.reference_on[:]
    #     self.plot_probe_on_array = self.current_data.probe_on_array[:]
    #     self.plot_reference_on_array = self.current_data.reference_on_array[:]
        
    #     if self.use_cutoff is True:
    #         self.plot_waves = self.plot_waves[self.cutoff[0]:self.cutoff[1]]
            
    #         if self.diagnostics_on is False:
    #             self.plot_dtt = self.plot_dtt[:,self.cutoff[0]:self.cutoff[1]]
                
    #         self.plot_ls = self.plot_ls[self.cutoff[0]:self.cutoff[1]]
    #         # self.plot_last_shot =
    #         self.plot_probe_shot_error = self.plot_probe_shot_error[self.cutoff[0]:self.cutoff[1]]
            
    #         if self.ui.d_use_reference.isChecked() is True:
    #             self.plot_ref_shot_error = self.plot_ref_shot_error[self.cutoff[0]:self.cutoff[1]]
    #             self.plot_dtt_error = self.plot_dtt_error[self.cutoff[0]:self.cutoff[1]]
                
    #         self.plot_probe_on = self.plot_probe_on[self.cutoff[0]:self.cutoff[1]]
    #         self.plot_reference_on = self.plot_reference_on[self.cutoff[0]:self.cutoff[1]]
    #         self.plot_probe_on_array = self.plot_probe_on_array[:,self.cutoff[0]:self.cutoff[1]]
    #         self.plot_reference_on_array = self.plot_reference_on_array[:,self.cutoff[0]:self.cutoff[1]]        
    #     return
        
    # def pixels_to_waves(self):
    #     slope = (self.calib[3]-self.calib[2])/(self.calib[1]-self.calib[0])
    #     y_int = self.calib[2]-slope*self.calib[0]
    #     return np.linspace(0,self.camera.num_pixels-1,self.camera.num_pixels)*slope+y_int
    
    def pixels_to_nms(self):
        #uses geometric optics to convert pixel size to real space.
        self.pixel_size = 13.5e3 #um to nm
        self.imaging_focal_length = 500e6 #500mm to nm
        self.tube_length = 180e3 #um to nm for Olympus objectives
        self.nm_per_pixel = self.pixel_size * self.imaging_focal_length / self.tube_length
        return np.linspace(0, self.camera.num_pixels-1,self.camera.num_pixels)*self.nm_per_pixel
                
    # def ls_plot(self):
    #     self.ui.a_last_shot_graph.plotItem.plot(self.plot_waves, self.plot_ls, clear=True, pen='b')
    #     return
    
    # def lastshot_plot(self):
    #     self.ui.a_last_shot_graph.plotItem.plot(self.plot_last_shot, clear=True)
    #     return
        
    # def top_plot(self):
    #     self.ui.a_colourmap.setImage(self.plot_dtt, scale=(len(self.plot_waves)/len(self.times), 1))
    #     return
    
    # def add_time_marker(self):
    #     finite_times = self.plot_times[np.isfinite(self.plot_times)]
    #     self.time_marker = pg.InfiniteLine(finite_times[int(len(finite_times)/2)], movable=True, bounds=[min(self.plot_times), max(self.plot_times)])
    #     self.ui.a_kinetic_graph.addItem(self.time_marker)
    #     self.time_marker.sigPositionChangeFinished.connect(self.update_time_pixel)
    #     self.time_marker_label = pg.InfLineLabel(self.time_marker, text='{value:.2f}'+self.timeunits, movable=True, position=0.9)
    #     self.update_time_pixel()
    #     return
    
    # def update_time_pixel(self):
    #     self.spectrum_time = self.time_marker.value()
    #     self.time_pixel = np.where((self.plot_times-self.spectrum_time)**2 == min((self.plot_times-self.spectrum_time)**2))[0][0]
    #     if self.finished_acquisition:
    #         self.create_plot_waves_and_times()
    #         self.spec_plot()
    #     return
    
    # def add_wavelength_marker(self):
    #     self.wavelength_marker = pg.InfiniteLine(self.plot_waves[int(len(self.plot_waves)/2)], movable=True, bounds=[min(self.plot_waves), max(self.plot_waves)])
    #     self.ui.a_spectra_graph.addItem(self.wavelength_marker)
    #     self.wavelength_marker.sigPositionChangeFinished.connect(self.update_kinetics_wavelength)
    #     self.wavelength_marker_label = pg.InfLineLabel(self.wavelength_marker, text='{value:.2f}nm', movable=True, position=0.9)
    #     self.update_kinetics_wavelength()
    #     return
    
    # def update_kinetics_wavelength(self):
    #     self.kinetics_wavelength = self.wavelength_marker.value()
    #     self.kinetics_pixel = np.where((self.waves-self.kinetics_wavelength)**2 == min((self.waves-self.kinetics_wavelength)**2))[0][0]  # self.waves rather than self.plot_waves?
    #     if self.finished_acquisition:
    #         self.create_plot_waves_and_times()
    #         self.kin_plot()
    #     return
        
    # def kin_plot(self):
    #     for item in self.ui.a_kinetic_graph.plotItem.listDataItems():
    #         self.ui.a_kinetic_graph.plotItem.removeItem(item)
    #     if self.finished_acquisition:
    #         self.ui.a_kinetic_graph.plotItem.plot(self.plot_times, self.plot_kinetic_avg, pen='b', symbol='s', symbolPen='b', symbolBrush=None, symbolSize=4, clear=False)
    #     else:
    #         if self.current_sweep.sweep_index > 0:
    #             self.ui.a_kinetic_graph.plotItem.plot(self.plot_times[0:self.timestep+1], self.plot_kinetic_current[0:self.timestep+1], pen='c', symbol='s', symbolPen='c', symbolBrush=None, symbolSize=4, clear=False)
    #             self.ui.a_kinetic_graph.plotItem.plot(self.plot_times, self.plot_kinetic_avg, pen='b', symbol='s', symbolPen='b', symbolBrush=None, symbolSize=4, clear=False)
    #         else:
    #             self.ui.a_kinetic_graph.plotItem.plot(self.plot_times[0:self.timestep+1], self.plot_kinetic_current[0:self.timestep+1], pen='c', symbol='s', symbolPen='c', symbolBrush=None, symbolSize=4, clear=False)
    #     return
        
    # def spec_plot(self):
    #     for item in self.ui.a_spectra_graph.plotItem.listDataItems():
    #         self.ui.a_spectra_graph.plotItem.removeItem(item)
    #     self.ui.a_spectra_graph.plotItem.plot(self.plot_waves, self.plot_dtt[self.time_pixel,:], pen='r', clear=False)
    #     return
        
    def d_error_plot(self):
        self.ui.d_error_graph.plotItem.plot(self.plot_waves, np.log10(self.plot_probe_shot_error), pen='r', clear=True, fillBrush='r')
        self.ui.d_error_graph.plotItem.setYRange(-4, 1, padding=0)
        return
        
    def d_trigger_plot(self):
        self.ui.d_trigger_graph.plotItem.plot(np.arange(self.num_shots), self.current_data.trigger, pen=None, symbol='o', clear=True)
        return
        
    def d_probe_ref_plot(self):
        for item in self.ui.d_probe_ref_graph.plotItem.listDataItems():
            self.ui.d_probe_ref_graph.plotItem.removeItem(item)
        probe_std = np.std(self.plot_probe_on_array, axis=0)
        self.ui.d_probe_ref_graph.plotItem.plot(self.plot_waves, self.plot_probe_on, pen='r')
        pcurve1 = pg.PlotDataItem(self.plot_waves, self.plot_probe_on-2*probe_std, pen='r')
        pcurve2 = pg.PlotDataItem(self.plot_waves, self.plot_probe_on+2*probe_std, pen='r')
        self.probe_error_region.setCurves(pcurve1, pcurve2)
        self.ui.d_probe_ref_graph.addItem(self.probe_error_region)            
        return
        
    def d_ls_plot(self):
        self.ui.d_last_shot_graph.plotItem.plot(self.plot_waves, self.plot_ls, pen='b', clear=True)
        return
        
    def message_block(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Block Probe and Reference")
        msg.setInformativeText("Just press once (be patient)")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return retval
        
    def message_unblock(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Unblock Probe and Reference")
        msg.setInformativeText("Just press once (be patient)")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return retval
        
    def message_time_points(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("One or more time point exceeds limit!")
        msg.setInformativeText("Don't be greedy...")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return retval
        
    def message_error_saving(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Error Saving File")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return retval
    
    def message_error_set_pulsesbursts(self, e):
        # @todo review this and delete it entirely if it's not useful?
        # pushing messages to the log seems less annoying for the user...
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText('Error setting number of pulses in the burst'
                    +'\n'
                    +'Please check your Acquire Options!')
        msg.setInformativeText('Exception message:\n'+e)
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return retval
    
    def message_unsafe_exit(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText('cannot close application')
        msg.setInformativeText('stop acquisition and disconnect from hardware')
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()
        return retval
        
    def running(self):
        self.idle = False
        self.ui.hardware_tab.setEnabled(False)
        self.ui.a_run_btn.setDisabled(True)
        self.ui.d_run_btn.setDisabled(True)
        self.ui.a_stop_btn.setDisabled(False)
        self.ui.d_stop_btn.setDisabled(False)
        self.ui.a_file_box.setDisabled(True)
        self.ui.a_times_box.setDisabled(True)
        self.ui.a_acquire_box.setDisabled(True)
        if self.diagnostics_on is False:
            self.ui.d_times_box.setDisabled(True)
            self.ui.d_acquire_box.setDisabled(True)
        return
            
    def idling(self):
        self.idle = True
        self.ui.hardware_tab.setEnabled(True)
        self.ui.a_run_btn.setDisabled(False)
        self.ui.d_run_btn.setDisabled(False)
        self.ui.a_stop_btn.setDisabled(True)
        self.ui.d_stop_btn.setDisabled(True)
        self.ui.a_file_box.setDisabled(False)
        self.ui.a_times_box.setDisabled(False)
        self.ui.a_acquire_box.setDisabled(False)
        self.ui.d_acquire_box.setDisabled(False)
        self.ui.d_times_box.setDisabled(False)
        return
    
    # def update_progress_bars(self):
    #     self.ui.a_sweep_progress_bar.setValue(self.timestep+1)
    #     self.ui.a_measurement_progress_bar.setValue((len(self.times)*self.current_sweep.sweep_index)+self.timestep+1)
    #     return
        

    @pyqtSlot(np.ndarray, np.ndarray, int, int)    

   
    def acquire_bgd(self):
        print("acquire_bgd()")      
        self.append_history('Acquiring '+str(self.num_shots*self.dcshotfactor)+' shots')
        self.acquisition.start_acquire.emit()
        return
    
    @pyqtSlot(np.ndarray, np.ndarray, int, int)    
    def post_acquire_bgd(self, probe, reference, first_pixel, num_pixels):
        print("post_acquire_bgd()")      
        self.message_unblock()
        self.bgd = DataProcessing(probe,
                                  reference,
                                  first_pixel,
                                  num_pixels)
        self.bgd.separate_on_off(self.threshold)
        self.bgd.average_shots() 
        self.run()
        return
    
    def exec_run_btn(self):
        # @todo remove, new version run_acquisition()
        self.append_history('Launching Run!')
        
        self.stop_request = False
        self.diagnostics_on = False
        self.running()
        
        success = self.delay.check_times(self.times)
        if success is False:
            self.message_time_points()
            self.idling()
            return
        
        self.finished_acquisition = False
        self.set_waves_and_times_axes()
        try:
            self.ui.a_kinetic_graph.removeItem(self.time_marker)
        except:
            pass
        self.add_time_marker()
        try:
            self.ui.a_spectra_graph.removeItem(self.wavelength_marker)
        except:
            pass
        self.add_wavelength_marker()
        
        self.acquire_thread = QtCore.QThread()
        self.acquire_thread.start()
        
        # Create acquisition object to be executed in other thread
        self.acquisition = Acquisition(self.camera, number_of_scans=self.num_shots*self.dcshotfactor)
        
        self.acquisition.moveToThread(self.acquire_thread)
        self.acquisition.start_acquire.connect(self.acquisition.acquire)
        self.acquisition.data_ready.connect(self.post_acquire_bgd)
        
        self.run()
        return
            

        

        
    def post_sweep(self):
        print("post_sweep()")
        print("in main code" +str(self.current_sweep.sweep_index))
        self.append_history('Saving Sweep '+str(self.current_sweep.sweep_index))
        try:
            self.current_sweep.save_current_data() # @todo Make this an option in the GUI?
            self.current_sweep.save_avg_data()
        # self.current_sweep.save_metadata_each_sweep(self.current_data.probe_on,
        #                                             self.current_data.reference_on,
        #                                             self.current_data.probe_shot_error)
        except:
            self.message_error_saving()
            
        self.current_sweep.next_sweep()
        
        # if self.current_sweep.sweep_index == self.ui.a_num_sweeps.value():
        #     self.finish()
        # else:
        #     self.append_history('Starting Sweep '+str(self.current_sweep.sweep_index))
        #     self.ui.a_sweep_display.display(self.current_sweep.sweep_index+1)
        #     self.start_sweep()
        return
        
    def exec_stop_btn(self):
        self.append_history('Stopped')
        self.stop_request=True
        return
        
    def move(self, new_time): 
        self.append_history('Moving to: '+str(new_time))
        #self.tau_flip_request = self.delay.move_to(new_time)
        return
    
    def d_jog_earlier(self):
        newtime = self.ui.d_time.value()-self.ui.d_jogstep_sb.value()
        self.move(newtime)
        self.ui.d_time.setValue(newtime)
        return
        
    def d_jog_later(self):
        newtime = self.ui.d_time.value()+self.ui.d_jogstep_sb.value()
        self.move(newtime)
        self.ui.d_time.setValue(newtime)
        return
        
    def exec_d_set_current_btn(self):
        d_time = self.ui.d_time.value()
        self.ui.d_time.setValue(0)
        self.move(d_time)
        self.ui.a_t0.setValue(d_time)
        self.ui.d_t0.setValue(d_time)
        return
        
    def d_acquire(self):
        self.append_history('Acquiring '+str(self.num_shots)+' shots')
        self.acquisition.start_acquire.emit()
        return
        
    @pyqtSlot(np.ndarray, np.ndarray, int, int)
    def d_post_acquire(self, probe, reference, first_pixel, num_pixels):
        try:
            self.current_data.update(probe,
                                     reference,
                                     first_pixel,
                                     num_pixels)
        except:
             self.current_data = DataProcessing(probe,
                                                reference,
                                                first_pixel,
                                                num_pixels)
        self.current_data.separate_on_off(self.threshold,self.tau_flip_request)
        self.current_data.sub_bgd(self.bgd)
        if self.ui.d_use_ref_manip.isChecked() is True:
            self.current_data.manipulate_reference(self.refman)
        self.current_data.average_shots()

        self.current_data.calcuate_dtt(use_reference=False,cutoff=self.cutoff,use_avg_off_shots=self.ui.d_use_avg_off_shots.isChecked())
        self.current_data.calculate_dtt_error(use_reference=False,use_avg_off_shots=self.ui.d_use_avg_off_shots.isChecked())

        self.create_plot_waves_and_times()
        self.d_ls_plot()
        self.d_error_plot()
        self.d_trigger_plot()
        self.d_probe_ref_plot()
        
        if self.stop_request is True:
            self.d_finish()
        else:
            self.d_acquire()
        return
        
    def d_acquire_bgd(self):
        self.append_history('Acquiring '+str(self.num_shots*self.dcshotfactor)+' shots')
        self.acquisition.start_acquire.emit()
        return
        
    @pyqtSlot(np.ndarray, np.ndarray, int, int)
    def d_post_acquire_bgd(self, probe, reference, first_pixel, num_pixels):
        self.message_unblock()
        self.bgd = DataProcessing(probe,
                                  reference,
                                  first_pixel,
                                  num_pixels)
        if self.ui.d_use_linear_corr.isChecked():
            try:
                self.bgd.linear_pixel_correlation(self.linear_corr)
            except:
                self.append_history('Error using linear pixel correction')
        self.bgd.separate_on_off(self.threshold)
        self.bgd.average_shots()
        self.d_run()          
        return
        
    def exec_d_run_btn(self):
        self.append_history('Launching Diagnostics!')
        self.stop_request = False
        self.diagnostics_on = True
        self.tau_flip_request = False
        self.running()
        
        success = self.delay.check_time(self.ui.d_time.value())
        if success is False:
            self.message_time_points()
            self.idling()
            return
        
        self.acquire_thread = QtCore.QThread()
        self.acquire_thread.start()
        
        self.acquisition = Acquisition(self.camera, number_of_scans=self.num_shots*self.dcshotfactor)

        self.acquisition.moveToThread(self.acquire_thread)
        self.acquisition.start_acquire.connect(self.acquisition.acquire)
        self.acquisition.data_ready.connect(self.d_post_acquire_bgd)
        
        self.message_block()
        self.append_history('Taking Background')
        self.d_acquire_bgd()

    def d_run(self):
        self.move(self.ui.d_time.value())
        self.acquisition.update_number_of_scans(self.num_shots)
        self.acquisition.data_ready.disconnect(self.d_post_acquire_bgd)
        self.acquisition.data_ready.connect(self.d_post_acquire)
        self.d_acquire()
        
    def d_finish(self):  
        self.acquire_thread.quit()
        self.idling()
        return
        
    def exec_d_stop_btn(self):
        self.stop_request = True
        return
        
    def exec_d_move_to_time(self):
        self.move(self.ui.d_time.value())
        return

def main():
    
    # create application
    QApplication.setStyle('Fusion')
    app = QApplication(sys.argv)
    
    # load the parameter values from last time and launch GUI
    last_instance_filename = 'metadata_closing_pickle.txt'
    try:
        with open(last_instance_filename, 'rb') as file:
            last_instance_values = pickle.load(file)
    except:
        print("Unable to open `last_instance_values.txt` to load previous GUI values. Defaults will be used.")
        last_instance_values = dict()
    
    ex = Application(last_instance_filename, last_instance_values=last_instance_values, mock=("mock" in sys.argv))
    
    ex.show()
    ex.create_plots()
    
    # kill application
    sys.exit(app.exec_())
   

if __name__ == '__main__':
    main()


""" redundant pyTA code to be deleted


    # def start_sweep(self):
    #     print("start_sweep()")
    #     self.timestep = 0
    #     self.time = self.times[self.timestep]
    #     self.ui.a_time_display.display(self.time)
    #     self.update_progress_bars()
    #     self.move(self.time)
    #     self.acquire()
    #     return
    
    # def (self):
    #     print("acquire()")
    #     self.append_history('Acquiring '+str(self.num_shots)+' shots')
    #     self.acquisition.start_acquire.emit()  # connects to the Acquire signal in the camera class, which results in a signal data_ready being emitted containing the data from probe and reference. This signal connects to post_acquire method, which loops back to acquire
    #     return
    

    # def run(self):
    #     print("run()")
    #     self.update_metadata()
    #     self.current_sweep = SweepProcessing(self.times,self.num_pixels,self.filepath,self.metadata,self.cameratype)    
        
    #     self.acquisition.update_number_of_scans(self.num_shots)
    #     self.acquisition.data_ready.disconnect(self.post_acquire_bgd)
    #     self.acquisition.data_ready.connect(self.post_acquire)
        
    #     self.append_history('Starting Sweep '+str(self.current_sweep.sweep_index))
    #     self.ui.a_sweep_display.display(self.current_sweep.sweep_index+1)
    #     self.ui.a_sweep_progress_bar.setMaximum(len(self.times))
    #     self.ui.a_measurement_progress_bar.setMaximum(len(self.times)*self.ui.a_num_sweeps.value())
    #     self.start_sweep()
        
    # def finish(self):
    #     print("finish()")
    #     self.acquire_thread.quit()
    #     self.idling()
    #     self.finished_acquisition = True
    #     if not self.stop_request:
    #         self.create_plot_waves_and_times()
    #         if self.ui.acquisition_tab.isVisible() is True:
    #             self.ls_plot()
    #             self.top_plot()
    #             self.kin_plot()
    #             self.spec_plot()
    #         if self.ui.diagnostics_tab.isVisible() is True:
    #             self.d_ls_plot()
    #             self.d_error_plot()
    #             self.d_trigger_plot()
    #             self.d_probe_ref_plot()
    #     return
    
    # def post_acquire(self, probe, reference, first_pixel, num_pixels):
    #     print("post_acquire()")
    #     try:
    #         self.current_data.update(probe,
    #                                  reference,
    #                                  first_pixel,
    #                                  num_pixels)
    #     except:
    #          self.current_data = DataProcessing(probe,
    #                                             reference,
    #                                             first_pixel,
    #                                             num_pixels)
    #     self.threshold = (0,15000) # temp
    #     self.high_trig_std = self.current_data.separate_on_off(self.threshold)#, self.tau_flip_request)
    #     #self.current_data.sub_bgd(self.bgd)#self.bgd is set by post_acquire_bgd()
    #     #if self.ui.d_use_ref_manip.isChecked() is True:
    #     #    self.current_data.manipulate_reference(self.refman)
    #     self.current_data.average_shots()

    #     #self.high_dtt = self.current_data.calcuate_dtt(use_reference=False,cutoff=self.cutoff, use_avg_off_shots=self.ui.d_use_avg_off_shots.isChecked(), max_dtt=np.abs(self.ui.d_max_dtt.value()))
    #     self.high_dtt = self.current_data.calcuate_dtt(use_reference=False)
    #     #self.current_data.calculate_dtt_error(use_reference=False, use_avg_off_shots=self.ui.d_use_avg_off_shots.isChecked())
    #     self.current_data.calculate_dtt_error(use_reference=False)
        
    #     if (self.high_trig_std is False) and (self.high_dtt is False):
    #         self.current_sweep.add_current_data(self.current_data.dtt, time_point=self.timestep)
    #         self.create_plot_waves_and_times()
    #         if self.ui.acquisition_tab.isVisible() is True:
    #             self.ls_plot()
    #             self.top_plot()
    #             self.kin_plot()
    #             self.spec_plot()
    #         if self.ui.diagnostics_tab.isVisible() is True:
    #             self.d_ls_plot()
    #             self.d_error_plot()
    #             self.d_trigger_plot()
    #             self.d_probe_ref_plot()
    #         if self.stop_request is True:
    #             self.finish()
    #         if self.timestep == len(self.times)-1:
    #             self.post_sweep()
    #         else:
    #             self.timestep = self.timestep+1
    #             self.time = self.times[self.timestep]
    #             self.ui.a_time_display.display(self.time)
    #             self.update_progress_bars()
    #             self.move(self.time)
    #             self.acquire()
    #     else:
    #         if self.stop_request is True:
    #             self.finish()
    #         self.append_history('retaking point')
    #         self.acquire()
    #     return


"""