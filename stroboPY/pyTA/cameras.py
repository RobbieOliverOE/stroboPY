import os
import ctypes as ct
import numpy as np
import pylablib as pll
pll.par["devices/dlls/andor_sdk3"] = "C:/Program Files/Andor SDK3/" #Pass the path the AndorSDKdlls
from pylablib.devices import Andor
import imageio
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class Acquisition(QObject):
    
    def __init__(self, camera, number_of_scans=100, exposure_time_us=1):
        super(QObject, self).__init__()
        self.camera = camera
        self.camera.number_of_scans = number_of_scans
        self.camera.exposure_time_us = exposure_time_us
        self.camera.array = np.zeros((self.camera.number_of_scans+10, self.camera.pixels*2), dtype=np.dtype(np.int32))
        #self.camera.data = self.camera.array[10:]
        
    def update_number_of_scans(self, number_of_scans):
        self.camera.number_of_scans = number_of_scans
        self.camera.array = np.zeros((self.camera.number_of_scans+10, self.camera.pixels*2), dtype=np.dtype(np.int32))
        #self.camera.data = self.camera.array[10:]
        
    start_acquire = pyqtSignal()
    data_ready = pyqtSignal(np.ndarray, np.ndarray, int, int)
    @pyqtSlot()
    def acquire(self):
        self.camera._acquire()
        try: #for Stessing
            self.data_ready.emit(self.camera.probe, self.camera.reference, self.camera.first_pixel, self.camera.num_pixels)
        except:
            self.data_ready.emit(self.camera.image)
            print("In Except in cameras")
        self.camera.overflow = self.camera.FFOvl()
        return


class AndorCamera(QObject):
    def __init__(self, bit_depth_mode, shutter_mode):
        super(QObject,self).__init__()
        try:
            self.cam = Andor.AndorSDK3Camera() #connect to the camera
            self.cam.set_attribute_value("SpuriousNoiseFilter", False) #ensure weird noise filtering always off
            self.cam.set_attribute_value("ElectronicShutteringMode", shutter_mode) #pass the chosen shutter mode
            self.cam.set_attribute_value("SimplePreAmpGainControl", bit_depth_mode) #pass bitdepth mode (12-bit [faster but less detail] or 16-bit)
            print("Camera is cooling, please wait")
            self.cam.set_cooler(True) #start cooling
            while True:
                if float(self.cam.get_temperature()) <=1: # To 0 deg
                    print("Camera has cooled - thanks for waiting!")
                    break
        except:
            raise IOError("Couldn't initilise ANDOR Zyla!")
        
    def SetParams(self, exposure=None, shutter_mode=None, bit_depth_mode=None):
        if exposure:
            self.cam.set_attribute_value("ExposureTime",exposure) # in s
        if shutter_mode:
            self.cam.set_attribute_value("ElectronicShutteringMode", shutter_mode) 
            # 0 = rolling, 1 = global
        if bit_depth_mode:
            self.cam.set_attribute_value("SimplePreAmpGainControl",bit_depth_mode) 
            # 0 = 12-bit (high well capacity), 1 = 12-bit (low noise), 16-bit (low noise & high well capacity)
    
    def _acquire(self, filename):
        image = self.cam.snap() # Saves image to memory
        # Write to disk:
        imageio.imwrite(f"{filename}.tif", image) # tif is the only thing that works!
    
    def dump_settings(self, path):
        with open(f"{path}/camera_setting_dump.txt",'w') as file:
            print(self.cam.get_all_attribute_values(), file=file) # Saves all parameters to file
    
    def close(self):
        self.cam.close()







class StresingCameras(QObject):
    
    def __init__(self, cameratype, use_ir_gain=False):
        super(QObject, self).__init__()
        self.cameratype = cameratype
        self.use_ir_gain = use_ir_gain
        if self.cameratype == 'VIS':
            self.dll = self.dll = ct.WinDLL(os.path.join(os.path.expanduser('~'), 'Documents', 'StresingCameras', '64bit', '64FFT1200CAM2', 'ESLSCDLL_64', 'x64', 'Release', '2cam', 'ESLSCDLL_64.dll'))
            self.board_number = 1  # PCI board index: 1 is VIS, 2 is NIR
            self.fft_lines = 64  # number of lines for binning if FFT sensor, 0 for NIR, 64 for VIS
            self.vfreq = 7  # vertical frequency for FFT sensor, given as 7 in examples from Stresing
            self.pixels = 1200  # number of pixels, including dummy pixels
            self.num_pixels = 1024  # actual number of active pixels
            self.first_pixel = 16 # first non-dummy pixel
            self.threadp = 15  # priority of thread, 31 is highest
            self.dat_10ns = 100  # delay after trigger
        elif self.cameratype == 'NIR':
            self.dll = ct.WinDLL(os.path.join(os.path.expanduser('~'), 'Documents', 'StresingCameras', '64bit', '64IR600CAM2', 'ESLSCDLL_64', 'x64', 'Release', '2cam', 'ESLSCDLL_64.dll'))
            self.board_number = 2 # PCI board index: 1 is VIS, 2 is NIR
            self.fft_lines = 0  # number of lines for binning if FFT sensor, 0 for NIR, 64 for VIS
            self.pixels = 600  # number of pixels, including dummy pixels
            self.num_pixels = 512  # actual number of active pixels
            self.first_pixel = 16  # first non-dummy pixel
            self.threadp = 10  # priority of thread, 31 is highest
        else:
            raise ValueError('cameratype must be either \'VIS\' or \'NIR\'')
        self.zadr = 1  # not needed, only if in addressed mode
        self.fkt = 1  # 1 for standard read, others are possible, could try 0 but unlikely
        self.sym = 0  # for FIFO, depends on sensor
        self.burst = 1  # for FIFO, depends on sensor
        self.waits = 3  # depends on sensor, sets the pixel read frequency
        self.flag816 = 1  # 1 if AD resolution 12 is 16bit, 2 if 8bit
        self.pportadr = 378  # address if parallel port is used
        self.pclk = 2  # pixelclock, not used here
        self.xckdelay = 3  # sets the delay after xck goes high
        self.freq = 0  # read frequency in Hz, should be 0 if exposure time is given
        self.clear_cnt = 8  # number of reads to clear the sensor, depends on sensor
        self.release_ms = -1  # less than zero: don't release
        self.exttrig = 1  # 1 is use external trigger
        self.block_trigger = 0  # true (not 0) if one external trigger starts block of nos scans which run with internal timer
        self.adrdelay = 3  # not sure what this is...
        self.exposure_time_us = 10  # set an arbitrary default - overridden by Acquisition instance
        self.number_of_scans = 100  # set an arbitrary default - overridden by Acquisition instance
        self._set_argtypes()
    
    def _set_argtypes(self):
        """
        required on 64-bit to ensure that pointers to the data array have the correct type
        """
        self.dll.DLLReadFFLoop.argtypes = [ct.c_uint32,
                                           np.ctypeslib.ndpointer(dtype=np.int32, ndim=2, flags=['C', 'W']),
                                           ct.c_uint32,
                                           ct.c_int32,
                                           ct.c_uint32,
                                           ct.c_uint32,
                                           ct.c_uint32,
                                           ct.c_uint32,
                                           ct.c_uint32,
                                           ct.c_uint32,
                                           ct.c_uint16,
                                           ct.c_uint8,
                                           ct.c_uint8]
        self.dll.DLLGETCCD.argtypes = [ct.c_uint32,
                                       np.ctypeslib.ndpointer(dtype=np.int32, ndim=2, flags=['C', 'W']),
                                       ct.c_uint32,
                                       ct.c_int32,
                                       ct.c_uint32]
        self.dll.DLLReadFifo.argtypes = [ct.c_uint32,
                                         np.ctypeslib.ndpointer(dtype=np.int32, ndim=2, flags=['C', 'W']),
                                         ct.c_int32]
        
    def initialise(self):
        self.CCDDrvInit()
        self._wait(1000000)
        self.InitBoard()
        self._wait(1000000)
        self.WriteLongS0(100,52)        
        self._wait(1000000)
        self.RsTOREG()
        self._wait(1000000)
        if self.cameratype == 'VIS':
            self.SetISFFT(1)
            self._wait(1000000)
            self.SetupVCLK()
        elif self.cameratype == 'NIR':
            self.SetISPDA(1)
            self._wait(1000000)
            if self.use_ir_gain:
                self.Von()
            else:
                self.Voff()
        else:
            raise ValueError('cameratype must be either \'VIS\' or \'NIR\'')
        self._wait(1000000)
        self.Cal16bit()
        self._wait(1000000)
        self.RSFifo()
        self._wait(1000000)
            
    def _wait(self, time_us):
        self.InitSysTimer()
        tick_start = self.TicksTimestamp()
        time_start = self.Tickstous(tick_start)
        tick_end = self.TicksTimestamp()
        time_end = self.Tickstous(tick_end)
        while (time_end - time_start) < time_us:
            tick_end = self.TicksTimestamp()
            time_end = self.Tickstous(tick_end)
        return
    
    def _acquire(self):
        self.ReadFFLoop(self.number_of_scans, self.exposure_time_us)
        self._construct_data_vectors()
        return
        
    # def _construct_data_vectors(self):
    #     hiloArray = self.data.view(np.uint16)[:, 0:self.pixels*2]  # temp = shots x (2*pixels)
    #     hiloArray = hiloArray.reshape(hiloArray.shape[0], 2, self.pixels)
    #     self.probe = hiloArray[:, 0, :]  # pointers onto self.data
    #     self.reference = hiloArray[:, 1, :]
    
    def _construct_data_vectors(self):
        if self.cameratype == 'VIS':
            hiloArray = self.array.view(np.uint16)[10:, 0:self.pixels*2]
            hiloArray = hiloArray.reshape(hiloArray.shape[0], 2, self.pixels)
        elif self.cameratype == 'NIR':
            hiloArray = self.array.view(np.uint16)[5:int((self.number_of_scans+10)/2), 0:self.pixels*4]
            hiloArray = hiloArray.reshape(hiloArray.shape[0]*2, 2, self.pixels)
        else:
            raise ValueError('cameratype must be either \'VIS\' or \'NIR\'')
        self.probe = hiloArray[:, 0, :]
        self.reference = hiloArray[:, 1, :]
    
    def close(self):
        self.CCDDrvExit()
        
    ###########################################################################
    ###########################################################################
    ###########################################################################
    # Library methods from DLL (DO NOT EDIT)
        
    def AboutDrv(self):
        self.dll.DLLAboutDrv(ct.c_uint32(self.board_number))
        
    def ActCooling(self):
        self.dll.DLLActCooling(ct.c_uint32(self.board_number),
                               ct.c_uint8(1))
                               
    def ActMouse(self):
        self.dll.DLLActMouse(ct.c_uint32(self.board_number))
    
    def Cal16bit(self):
        self.dll.DLLCal16Bit(ct.c_uint32(self.board_number),
                             ct.c_uint32(self.zadr))

    def CCDDrvExit(self):
        self.dll.DLLCCDDrvExit(ct.c_uint32(self.board_number))
        
    def CCDDrvInit(self):
        found = self.dll.DLLCCDDrvInit(ct.c_uint32(self.board_number))
        return bool(found)
        
    def CloseShutter(self):
        self.dll.DLLCloseShutter(ct.c_uint32(self.board_number))
        
    def ClrRead(self, clr_count):
        self.dll.DLLClrRead(ct.c_uint32(self.board_number),
                            ct.c_uint32(self.fft_lines),
                            ct.c_uint32(self.zadr),
                            ct.c_uint32(clr_count))
                            
    def ClrShCam(self):
        self.dll.DLLClrShCam(ct.c_uint32(self.board_number),
                             ct.c_uint32(self.zadr))
    
    def DeactMouse(self):
        self.dll.DLLDeactMouse(ct.c_uint32(self.board_number))
    
    def DisableFifo(self):
        self.dll.DLLDisableFifo(ct.c_uint32(self.board_number))
        
    def EnableFifo(self):
        self.dll.DLLEnableFifo(ct.c_uint32(self.board_number))
    
    def FFOvl(self):
        overflow = self.dll.DLLFFOvl(ct.c_uint32(self.board_number))
        return bool(overflow)
        
    def FFValid(self):
        valid = self.dll.DLLFFValid(ct.c_uint32(self.board_number))
        return bool(valid)
        
    def FlagXCKI(self):
        active = self.dll.DLLFlagXCKI(ct.c_uint32(self.board_number))
        return bool(active)
       
    def GetCCD(self):
        self.dll.DLLGETCCD(ct.c_uint32(self.board_number),
                           self.array,
                           ct.c_uint32(self.fft_lines),
                           ct.c_int32(self.fkt),
                           ct.c_uint32(self.zadr))
        return self.array
        
    def HighSlope(self):
        self.dll.DLLHighSlope(ct.c_uint32(self.board_number))
     
    def InitBoard(self):
        self.dll.DLLInitBoard(ct.c_uint32(self.board_number),
                              ct.c_int8(self.sym),
                              ct.c_uint8(self.burst),
                              ct.c_uint32(self.pixels),
                              ct.c_uint32(self.waits),
                              ct.c_uint32(self.flag816),
                              ct.c_uint32(self.pportadr),
                              ct.c_uint32(self.pclk),
                              ct.c_uint32(self.adrdelay))
    
    def InitSysTimer(self):
        return self.dll.DLLInitSysTimer()
        
    def LowSlope(self):
        self.dll.DLLLowSlope(ct.c_uint32(self.board_number))
    
    def OpenShutter(self):
        self.dll.DLLOpenShutter(ct.c_uint32(self.board_number))
    
    def OutTrigHigh(self):
        self.dll.DLLOutTrigHigh(ct.c_uint32(self.board_number))
        
    def OutTrigLow(self):
        self.dll.DLLOutTrigLow(ct.c_uint32(self.board_number))
    
    def OutTrigPulse(self, pulse_width):
        self.dll.DLLOutTrigPulse(ct.c_uint32(self.board_number),
                                 ct.c_uint32(pulse_width))
    
    def ReadFifo(self):
        self.dll.DLLReadFifo(ct.c_uint32(self.board_number),
                             self.array,
                             ct.c_int32(self.fkt))
        return self.array
    
    def ReadFFCounter(self):
        counter = self.dll.DLLReadFFCounter(ct.c_uint32(self.board_number))
        return counter        
    
    def ReadFFLoop(self, number_of_scans, exposure_time_us):
        self.dll.DLLReadFFLoop(ct.c_uint32(self.board_number),
                               self.array,
                               ct.c_uint32(self.fft_lines),
                               ct.c_int32(self.fkt),
                               ct.c_uint32(self.zadr),
                               ct.c_uint32(number_of_scans+10),
                               ct.c_uint32(exposure_time_us),
                               ct.c_uint32(self.freq),
                               ct.c_uint32(self.threadp),
                               ct.c_uint32(self.clear_cnt),
                               ct.c_uint16(self.release_ms),
                               ct.c_uint8(self.exttrig),
                               ct.c_uint8(self.block_trigger))
                               
    def RSFifo(self):
        self.dll.DLLRSFifo(ct.c_uint32(self.board_number))
        
    def RsTOREG(self):
        self.dll.DLLRsTOREG(ct.c_uint32(self.board_number))
        
    def SetADAmpRed(self, gain):
        self.dll.DLLSetADAmpRed(ct.c_uint32(self.board_number),
                                ct.c_uint32(gain))
    
    def SetAD16Default(self):
        self.dll.DLLSetAD16Default(ct.c_uint32(self.board_number),
                                   ct.c_uint32(1))
                                   
    def SetExtTrig(self):
        self.dll.DLLSetExtTrig(ct.c_uint32(self.board_number))
        
    def StopFFTimer(self):
        self.dll.DLLStopFFTimer(ct.c_uint32(self.board_number))
        
    def SetIntTrig(self):
        self.dll.DLLSetIntTrig(ct.c_uint32(self.board_number))
        
    def SetISFFT(self, _set):
        self.dll.DLLSetISFFT(ct.c_uint32(self.board_number),
                             ct.c_uint8(_set))
    
    def SetISPDA(self, _set):
        self.dll.DLLSetISPDA(ct.c_uint32(self.board_number),
                             ct.c_uint8(_set))
                             
    def SetOvsmpl(self):
        self.dll.DLLSetOvsmpl(ct.c_uint32(self.board_number),
                              ct.c_uint32(self.zadr))
    
    def SetTemp(self, level):
        self.dll.DLLSetTemp(ct.c_uint32(self.board_number),
                            ct.c_uint32(level))
    
    def SetupDelay(self, delay):
        self.dll.DLLSetupDELAY(ct.c_uint32(self.board_number),
                               ct.c_uint32(delay))
    
    def SetupHAModule(self, fft_lines):
        self.dll.DLLSetupHAModule(ct.c_uint32(self.board_number),
                                  ct.c_uint32(fft_lines))
        
    def SetupVCLK(self):
        self.dll.DLLSetupVCLK(ct.c_uint32(self.board_number),
                              ct.c_uint32(self.fft_lines),
                              ct.c_uint8(self.vfreq))
    
    def StartTimer(self, exposure_time):
        self.dll.DLLStartTimer(ct.c_uint32(self.board_number),
                               ct.c_uint32(exposure_time))
    
    def TempGood(self, channel):
        self.dll.DLLTempGood(ct.c_uint32(self.board_number),
                             ct.c_uint32(channel))
                             
    def TicksTimestamp(self):
        ticks = self.dll.DLLTicksTimestamp()
        return ticks
        
    def Tickstous(self, ticks):
        us = self.dll.DLLTickstous(ct.c_uint64(ticks))
        return us
    
    def Von(self):
        self.dll.DLLVOn(ct.c_uint32(self.board_number))
        
    def Voff(self):
        self.dll.DLLVOff(ct.c_uint32(self.board_number))
        
    def WaitforTelapsed(self, t_us):
        success = self.dll.DLLWaitforTelapsed(ct.c_uint32(t_us))
        return bool(success)
        
    def WriteLongS0(self, val, offset):
        success = self.dll.DLLWriteLongS0(ct.c_uint32(self.board_number),
                                          ct.c_uint32(val),
                                          ct.c_uint32(offset))
        return print('set dat '+str(bool(success)))
          