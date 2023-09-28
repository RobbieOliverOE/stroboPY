import pyvisa as visa
from pipython import GCSDevice, pitools


class PILongStageDelay:
    
    def __init__(self, t0):
        self.t0 = t0
        self.stage = GCSDevice('HYDRA')  # alternatively self.stage = GCSDevice(gcsdll='PI_HydraPollux_GCS2_DLL_x64.dll') for a fail safe option
        self.stage.ConnectTCPIP(ipaddress='192.168.0.2', ipport=400)
        self.axis = '1'
        self.timeout = 5000
        self.pos_max = 610.0
        self.pos_min = 0.0
        self.set_max_min_times()
        self.stage.VEL(self.axis, 30.0)  # set the velocity to some low value to avoid crashes!
        pitools.startup(self.stage)
        
    def initialise(self):
        self.stage.FRF(self.axis)  # reference the axis
        self.wait(self.timeout)
        self.initialized = True
    
    def wait(self, timeout):
        pitools.waitontarget(self.stage, self.axis, timeout=timeout)
        return

    def home(self):
        self.stage.GOH(self.axis)
        self.wait(self.timeout)
        return    
        
    def move_to(self, time_point_ps):
        new_pos_mm = self.convert_ps_to_mm(float(self.t0-time_point_ps))
        self.stage.MOV(self.axis, new_pos_mm)
        self.wait(self.timeout)
        return False
    
    def convert_ps_to_mm(self, time_ps):
        pos_mm = 0.299792458*time_ps/2
        return pos_mm
    
    def convert_mm_to_ps(self, pos_mm):
        time_ps = 2*pos_mm/0.299792458
        return time_ps
    
    def set_max_min_times(self):
        self.tmax = self.convert_mm_to_ps(self.pos_min)+self.t0
        self.tmin = -self.convert_mm_to_ps(self.pos_max)+self.t0
    
    def close(self):
        self.stage.CloseConnection()
        
    def check_times(self, times):
        all_on_stage = True
        for time in times:
            pos = self.convert_ps_to_mm(float(self.t0-time))
            if (pos>self.pos_max) or (pos<self.pos_min):
                all_on_stage = False
        return all_on_stage
        
    def check_time(self, time):
        on_stage = True
        pos = self.convert_ps_to_mm(float(self.t0-time))
        if (pos>self.pos_max) or (pos<self.pos_min):
            on_stage = False
        return on_stage
    
    
class PIShortStageDelay:
    
    def __init__(self, t0):
        self.t0 = t0
        self.stage = GCSDevice('E-873')
        self.stage.ConnectUSB(serialnum=119040925)
        self.axis = '1'
        self.timeout = 5000
        self.pos_max = 13.0
        self.pos_min = -13.0
        self.set_max_min_times()
        self.stage.VEL(self.axis, 3.0)  # set the velocity to some low value to avoid crashes!
        pitools.startup(self.stage)
        
    def initialise(self):
        self.stage.FRF(self.axis)  # reference the axis
        self.wait(self.timeout)
        self.initialized = True
    
    def wait(self, timeout):
        pitools.waitontarget(self.stage, self.axis, timeout=timeout)
        return

    def home(self):
        self.stage.GOH(self.axis)
        self.wait(self.timeout)
        return    
        
    def move_to(self, time_point_ps):
        new_pos_mm = self.convert_ps_to_mm(float(self.t0-time_point_ps))
        self.stage.MOV(self.axis, new_pos_mm)
        self.wait(self.timeout)
        return False
    
    def convert_ps_to_mm(self, time_ps):
        pos_mm = (0.299792458*time_ps/2)-13.0
        return pos_mm
    
    def convert_mm_to_ps(self, pos_mm):
        time_ps = 2*(pos_mm+13.0)/0.299792458
        return time_ps
    
    def set_max_min_times(self):
        self.tmax = self.convert_mm_to_ps(self.pos_min)+self.t0
        self.tmin = -self.convert_mm_to_ps(self.pos_max)+self.t0
    
    def close(self):
        self.stage.CloseConnection()
        
    def check_times(self, times):
        all_on_stage = True
        for time in times:
            pos = self.convert_ps_to_mm(float(self.t0-time))
            if (pos>self.pos_max) or (pos<self.pos_min):
                all_on_stage = False
        return all_on_stage
        
    def check_time(self, time):
        on_stage = True
        pos = self.convert_ps_to_mm(float(self.t0-time))
        if (pos>self.pos_max) or (pos<self.pos_min):
            on_stage = False
        return on_stage
    
    
class InnolasPinkLaserDelay:
    
    def __init__(self, t0):
        self.dg_tcpip_address = 'TCPIP::192.168.0.4::INSTR'
        self.rm = visa.ResourceManager()
        self.dg = self.rm.open_resource(self.dg_tcpip_address)
        self.t0 = t0
        self.set_max_min_times()
        
    def initialise(self):
        self.dg.write('TSRC 1\r')  # set to external trigger
        self.dg.write('TLVL 1.0\r')  # set external trigger level
        self.dg.write('LOFF 1,0.0\r')  # set the level offset of AB channel to 0
        self.dg.write('LAMP 1,4.0\r')  # set level amplitude to +4V
        self.dg.write('LPOL 1,1\r')  # set level polarity positive
        self.dg.write('DLAY 3,2,1e-7\r')  # set output pulse width to 100 ns
        self.dg.write('DLAY 2,0,0\r')  # set output pulse delay to (arbitrary value of) 0
        self.dg.write('ADVT 1\r')  # enable advanced triggering
        self.dg.write('PRES 1,2\r')  # halve the frequency of AB channel output
        self.dg.write('LOFF 2,0.0\r')  # set the level offset of CD channel to 0, to use as 500 HZ for PCI
        self.dg.write('LAMP 2,4.0\r')  # set CD level amplitude to +4V
        self.dg.write('LPOL 2,1\r')  # set CD level polarity positive
        self.dg.write('DLAY 5,4,5e-4\r')  # set CD output pulse width to 500 us
        self.dg.write('DLAY 4,0,0\r')  # set CD output pulse delay to (arbitrary value of) 0
        self.dg.write('PRES 2,2\r')  # halve the frequency of CD channel output
        self.initialized = True
 
    def move_to(self, time_point_ns):
        tau_flip_request = False
        new_time = (self.t0-time_point_ns)*1E-9  # is this correct since we are delaying the pump here not the probe?
        if new_time < 0:
            tau_flip_request = True
            new_time = new_time + 0.001  # add 1ms (rep rate is 1kHz) (AJM changed to 0ms 11-03-2019)
        self.dg.write('DLAY 2,0,{0:.5e}\r'.format(new_time))  # delay channel AB by new_time seconds from channel T0
        return tau_flip_request
    
    def set_max_min_times(self):
        self.tmax = 1E6+self.t0
        self.tmin = -1E6+self.t0
    
    def close(self):
        self.dg.close()
        self.rm.close()
        
    def check_times(self,times):
        all_between_two_shots = True
        for time in times:
            new_time = (self.t0-time)*1E-9  # is this correct since we are delaying the pump here not the probe?
            if (new_time<-0.001) or (new_time>0.001):
                all_between_two_shots = False
        return all_between_two_shots
        
    def check_time(self,time):
        between_two_shots = True
        new_time = (self.t0-time)*1E-9  # is this correct since we are delaying the pump here not the probe?
        if (new_time<-0.001) or (new_time>0.001):
            between_two_shots = False
        return between_two_shots
