from ctypes import byref
import ctypes as ct
import os

import PQLaserDrv.Sepia2_Def as Sepia2_Def
import PQLaserDrv.Sepia2_ErrorCodes as Sepia2_ErrorCodes


# Setting locale might be better set elsewhere?
# Not documented why it's used in the demo
import locale
locale.setlocale(locale.LC_ALL, 'en-US')

class Sepia2:
    """
    Object orientated Python interface to PQLaserDrv API
    https://www.picoquant.com/dl_manuals/PQLaserDrv_API_Manual.pdf
    All functions core functions and those relevant to the Sepia2 and it's modules found in Hicks C14 (LIB, USB, FWR, COM, SCD, SOMD, SLM) should be available.
    
    This simple interface translates Pythonic arguments to C types, to call the API, and then translates the return values back to Pythonic types.
    Where a function has multiple outputs, they are returned in order as a tuple.
    """
    # Represents the Sepia dll that functions are called via
    lib = None
    last_error_code = Sepia2_ErrorCodes.SEPIA2_ERR_NO_ERROR
    def __init__(self):
        """
        Find and load the laser driver dll else throw exception
        """
        # Detect whether operating system is x64, to connect correct driver
        # Most likely always x64 at this point
        # Alt method looks at python version struct.calcsize("P") == 8 (x64)
        # Could alternatively test both with try-catch
        lib_32 = "C:/ProgramData/PQLaserDrv/API/Win32/Sepia2_Lib.dll"
        lib_64 = "C:/ProgramData/PQLaserDrv/API/x64/Sepia2_Lib.dll"
        lib_path = lib_64 if 'PROCESSOR_ARCHITEW6432' in os.environ or os.environ['PROCESSOR_ARCHITECTURE'].endswith('64') else lib_32
        # Load DLL
        try:
            self.lib = ct.WinDLL(lib_path)
        except FileNotFoundException as ex:            
            print("Sepia2_Lib.dll was not at the expected location")
            raise
        except OSError as ex:            
            print("Sepia2_Lib.dll is not the correct architecture\nWin32 driver installed on x64?")
            raise
        # Check Library Version
        strLibVersion = self.LIB_GetVersion()
        strUSBVersion = self.LIB_GetLibUSBVersion()
        print("Using Sepia Lib v%s/%s"%(strLibVersion, strUSBVersion))
        if strLibVersion != "1.2.64.793" or strUSBVersion != "354":
            print("Warning: Code was developed for v1.2.64.793/354")
            
    def __del__(self):
        # Close down all connections as object is destroyed
        # This may already occur implicitly when self.lib is destroyed
        for i in range(8):
            if self.USB_IsOpenDevice(i):
                self.USB_CloseDevice(i)
    
    # Library Functions (LIB)        
    def __errchk(self, iRet):
        """
        Utility for handling error codes returned by Sepia2
        Raises an exception with the error message else returns True
        @param iRet Return code from an API function
        """
        self.last_error_code = iRet
        if (iRet == Sepia2_ErrorCodes.SEPIA2_ERR_NO_ERROR):
            return True
        if (iRet == Sepia2_ErrorCodes.SEPIA2_ERR_LIB_USB_DEVICE_OPEN_ERROR):
            print("Is the Sepia2 turned on?")
        # Convert error code to error message
        cErr = ct.create_string_buffer(Sepia2_Def.SEPIA2_ERRSTRING_LEN + 1)
        self.__errchk(self.lib.SEPIA2_LIB_DecodeError(ct.c_int(iRet), cErr))
        raise Exception("Error(%d): %s"%(iRet, cErr.value.decode("utf-8")))
        return False
        
    def LIB_GetVersion(self):
        """
        int SEPIA2_LIB_GetVersion (char* cLibVersion )
        (Referred to as in API manual as SEPIA2_LIB_GetLibVersion on one occasion)
        @return The library version string
        """
        cLibVersion = ct.create_string_buffer(Sepia2_Def.SEPIA2_VERSIONINFO_LEN + 2)
        self.__errchk(self.lib.SEPIA2_LIB_GetVersion(cLibVersion))
        return cLibVersion.value.decode("utf-8")

    def LIB_GetLibUSBVersion(self):
        """
        int SEPIA2_LIB_GetLibUSBVersion (char* cLibVersion )
        (Incorrectly included in API manual as SEPIA2_LIB_GetUSBVersion)
        @return The usb version string
        """
        cUSBVersion = ct.create_string_buffer(Sepia2_Def.SEPIA2_VERSIONINFO_LEN + 2)
        self.__errchk(self.lib.SEPIA2_LIB_GetLibUSBVersion(cUSBVersion))
        return cUSBVersion.value.decode("utf-8")

    def LIB_IsRunningOnWine(self):
        """
        int SEPIA2_LIB_IsRunningOnWine (unsigned char* pbRunsOnWine );
        @return True if operating system is Linux
        """        
        bIsLinux = ct.c_uint8(0)
        self.__errchk(self.lib.SEPIA2_LIB_IsRunningOnWine(byref(bIsLinux)))
        return bIsLinux.value != 0

    # Device Communication Functions (USB)
    def USB_OpenDevice(self, iDevIdx, strProductModel="", strSerialNumber=""):
        """
        int SEPIA2_USB_OpenDevice (int iDevIdx, char* cProductModel, char* cSerialNumber )
        Connect over USB to the PQ Laser Device
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param strProductModel Optional filter to ensure connected device has correct model
        @param strSerialNumber Optional filter to ensure connected device has correct serial number
        @return A tuple containing the product model and serial number of the connected device
        """
        cProductModel = ct.create_string_buffer(strProductModel.encode(), max(len(strProductModel)+1, Sepia2_Def.SEPIA2_PRODUCTMODEL_LEN))
        cSerialNumber = ct.create_string_buffer(strSerialNumber.encode(), max(len(strSerialNumber)+1, Sepia2_Def.SEPIA2_SERIALNUMBER_LEN))
        self.__errchk(self.lib.SEPIA2_USB_OpenDevice(ct.c_int(iDevIdx), cProductModel, cSerialNumber))
        return (cProductModel.value.decode("utf-8"), cSerialNumber.value.decode("utf-8"))
    
    def USB_IsOpenDevice(self, iDevIdx, strProductModel="", strSerialNumber=""):
        """
        int SEPIA2_USB_IsOpenDevice (int iDevIdx, unsigned char* pbIsOpen )
        Query whether the USB device iDevIdx has been opened or not
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param strProductModel Optional filter to ensure connected device has correct model
        @param strSerialNumber Optional filter to ensure connected device has correct serial number
        @return A tuple containing the product model and serial number of the connected device
        """
        bIsOpen = ct.c_uint8(0)
        self.__errchk(self.lib.SEPIA2_USB_IsOpenDevice(ct.c_int(iDevIdx), byref(bIsOpen)))
        return bIsOpen.value != 0
        
    def USB_OpenGetSerNumAndClose(self, iDevIdx, strProductModel="", strSerialNumber=""):
        """
        int SEPIA2_USB_OpenGetSerNumAndClose (int iDevIdx, char* cProductModel, char* cSerialNumber )
        Fetch the product model and serial number of the USB device iDevIdx
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param strProductModel Optional filter to ensure device has correct model
        @param strSerialNumber Optional filter to ensure device has correct serial number
        @return A tuple containing the product model and serial number of the device
        """
        cProductModel = ct.create_string_buffer(strProductModel.encode(), max(len(strProductModel)+1, Sepia2_Def.SEPIA2_PRODUCTMODEL_LEN))
        cSerialNumber = ct.create_string_buffer(strSerialNumber.encode(), max(len(strSerialNumber)+1, Sepia2_Def.SEPIA2_SERIALNUMBER_LEN))
        self.last_error_code = self.lib.SEPIA2_USB_OpenDevice(ct.c_int(iDevIdx), cProductModel, cSerialNumber)
        # Don't care if busy/blocked error is returned here, return values should be correct
        if (self.last_error_code != Sepia2_ErrorCodes.SEPIA2_ERR_LIB_USB_DEVICE_BUSY_OR_BLOCKED 
        and self.last_error_code != Sepia2_ErrorCodes.SEPIA2_ERR_LIB_USB_DEVICE_ALREADY_OPENED):
            self.__errchk(self.last_error_code)
        return (cProductModel.value.decode("utf-8"), cSerialNumber.value.decode("utf-8"))

    def USB_GetStrDescriptor(self, iDevIdx):
        """
        int SEPIA2_USB_GetStrDescriptor (int iDevIdx, char* cDescriptor )
        Returns the concatenated string descriptors of the USB device. e.g. model, firmware, serial.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @return The string description
        """
        cStrDecr = ct.create_string_buffer(Sepia2_Def.SEPIA2_USB_STRDECR_LEN)
        self.__errchk(self.lib.SEPIA2_USB_GetStrDescriptor(ct.c_int(iDevIdx), cStrDecr))
        return cStrDecr.value.decode("utf-8") 

    # Despite appearing in API manual, this function does not appear implemented
    #def USB_GetStrDescByIdx(self, iDevIdx, iDescrIdx):
    #    """
    #    int SEPIA2_USB_GetStrDescByIdx (int iDevIdx, int iDescrIdx, char* cDescriptor );
    #    Returns a specific component of the device descriptor.
    #    @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
    #    @param iDescrIdx Description component index (1...4)
    #    @return The string description component
    #    """
    #    cStrDecr = ct.create_string_buffer(Sepia2_Def.SEPIA2_USB_STRDECR_LEN)
    #    self.__errchk(self.lib.SEPIA2_USB_GetStrDescByIdx(ct.c_int(iDevIdx), ct.c_int(iDescrIdx), cStrDecr))
    #    return cStrDecr.value.decode("utf-8")

    def USB_CloseDevice(self, iDevIdx):
        """
        int SEPIA2_USB_CloseDevice (int iDevIdx )
        Closes the exclusive connection to the specified PQ Laser Device
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        """
        self.__errchk(self.lib.SEPIA2_USB_CloseDevice(ct.c_int(iDevIdx)))
        
    #  Firmware Functions (FWR)
    def FWR_DecodeErrPhaseName(self, iErrPhase):
        """
        int SEPIA2_FWR_DecodeErrPhaseName (int iErrPhase, char* cErrorPhase )
        @param iErrPhase error phase, integer returned by firmware function GetLastError
        @return Decoded error phase
        """
        cErrorPhase = ct.create_string_buffer(Sepia2_Def.SEPIA2_FW_ERRPHASE_LEN + 1)
        self.__errchk(self.lib.SEPIA2_FWR_DecodeErrPhaseName(ct.c_int(iErrPhase), cErrorPhase))
        return cErrorPhase.value.decode("utf-8")
    
    def FWR_GetVersion(self, iDevIdx):
        """
        int SEPIA2_FWR_GetVersion (int iDevIdx, char* cFWVersion )
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @return The "actual" firmware version string
        """
        cFWVersion = ct.create_string_buffer(Sepia2_Def.SEPIA2_PRI_DEVICE_FW_LEN + 1)
        self.__errchk(self.lib.SEPIA2_FWR_DecodeErrPhaseName(ct.c_int(iDevIdx), cFWVersion))
        return cFWVersion.value.decode("utf-8")
        
    def FWR_GetLastError(self, iDevIdx):
        """
        int SEPIA2_FWR_GetLastError (int iDevIdx, int* piErrCode, int* piPhase, int* piLocation, int* piSlot, char* cCondition )
        Returns the error description data from the last startup of the PQ laser device
        Errorcode can be passed to __errchk() to decode
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)        
        @return Tuple(error code, error phase, error location, error slot, error condition string)
        """
        cCondition = ct.create_string_buffer(Sepia2_Def.SEPIA2_FW_ERRCOND_LEN + 1)
        iErrCode = ct.c_int()
        iPhase = ct.c_int()
        iLocation = ct.c_int()
        iSlot = ct.c_int()
        self.__errchk(self.lib.SEPIA2_FWR_GetLastError(int(iDevIdx), byref(iErrCode), byref(iPhase), byref(iLocation), byref(iSlot), cCondition))
        return (iErrCode.value, iPhase.value, iLocation.value, iSlot.value, cCondition.value.decode("utf-8"))
        
    def FWR_GetModuleMap(self, iDevIdx, iPerformRestart):
        """
        int SEPIA2_FWR_GetModuleMap (int iDevIdx, int iPerformRestart, int* pwModuleCount )
        The map is a firmware and library internal data structure, which is essential to the work with PQ Laser Devices.
        It will be created by the firmware during start up.
        The library needs to have a copy of an actual map before you may access any module.
        You don't need to prepare memory, the function autonomously manages the memory acquirements for this task.        
        Since the firmware doesn't actualise the map once it is running, you might wish to restart the firmware to assure up to date mapping.
        You could switch the power off and on again to reach the same goal, but you also could more simply call this function with iPerformRestart set to 1.
        The PQ Laser Device will perform the whole booting cycle with the tiny difference of not needing to load the firmware again…
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iPerformRestart Tell the device to perform a soft restart before responding, this ensures the map is upto date
        @return The number of PQ laser device configurable elements
        """
        iModuleCount = ct.c_int()
        self.__errchk(self.lib.SEPIA2_FWR_GetModuleMap(ct.c_int(iDevIdx), ct.c_int(iPerformRestart), byref(iModuleCount)))
        return iModuleCount.value
        
    def FWR_GetModuleInfoByMapIdx(self, iDevIdx, iMapIdx):
        """
        int SEPIA2_FWR_GetModuleInfoByMapIdx (int iDevIdx, int iMapIdx, int* piSlotId, unsigned char* pbIsPrimary, unsigned char* pbIsBackPlane, unsigned char* pbHasUTC )
        Once the map is created and populated by the function GetModuleMap, you can scan it module by module, using this function.
        It returns the slot number, which is needed for all module-related functions later on, and three additional boolean information,
        namely if the module in question is a primary (e. g. laser driver) or a secondary module (e. g. laser head),
        if it identifies a backplane and furthermore, if the module supports uptime counters.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iMapIdx Index inside module map to access
        @return Tuple(slot number, isPrimaryModule : Bool, isBlackPlane : Bool, hasUptimeCounter : Bool)
        """
        iSlotID = ct.c_int()
        bIsPrimaryModule = ct.c_uint8()
        bIsBlackPlane = ct.c_uint8()
        bHasUptimeCounter = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_FWR_GetModuleInfoByMapIdx(ct.c_int(iDevIdx), ct.c_int(iMapIdx), byref(iSlotID), byref(bIsPrimaryModule), byref(bIsBlackPlane), byref(bHasUptimeCounter)))
        return (iSlotID.value, bIsPrimaryModule.value != 0, bIsBlackPlane.value != 0, bHasUptimeCounter.value != 0)
        
    def FWR_GetUptimeInfoByMapIdx(self, iDevIdx, iMapIdx):
        """
        int SEPIA2_FWR_GetUptimeInfoByMapIdx (int iDevIdx, int iMapIdx, unsigned long* pulMainPwrUp, unsigned long* pulActivePwrUp, unsigned long* ulScaledPwrUp )
        if SEPIA2_FWR_GetModuleInfoByMapIdx() returned HasUTC=True, then this can be called to get three counter values related to power up time
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iMapIdx Index inside module map to access
        @return Tuple(Approx power up time in mins*51, Approx active power up time (laser unlocked) in mins*51, Approximation of the power factor if divided by active power up time when >255).
        @note None of the modules in the hardware used for testing contain uptime counters
        """
        ulPulMainPwrUp = ct.c_uint32()
        ulPulActivePwrUp = ct.c_uint32()
        ulPulScaledPwrUp = ct.c_uint32()
        self.__errchk(self.lib.SEPIA2_FWR_GetUptimeInfoByMapIdx(ct.c_int(iDevIdx), ct.c_int(iMapIdx), byref(ulPulMainPwrUp), byref(ulPulActivePwrUp), byref(ulPulScaledPwrUp)))
        return (ulPulMainPwrUp.value, ulPulActivePwrUp.value, ulPulScaledPwrUp.value)
        
    def FWR_CreateSupportRequestText(self, iDevIdx, strPreamble, strCallingSW, NO_PREAMBLE = False, NO_TITLE = False, NO_CALLING_SW_INDENT = False, NO_SYSTEM_INFO = False, bufferLen = 10240):
        """
        int SEPIA2_FWR_CreateSupportRequestText (int iDevIdx, char* cPreamble, char* cCallingSW, unsigned long ulOptions, int iBufferLen, char* cBuffer )
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param strPreamble Preamble string to include in response
        @param strCallingSW Description of calling software to include in response
        @param NO_PREAMBLE No preamble text processing (if given, it is ignored)
        @param NO_TITLE No title created
        @param NO_CALLING_SW_INDENT Lines on calling software are not indented
        @param NO_SYSTEM_INFO No system info is processed
        @param bufferLen If buffer len is set too short, the function causes an early exit
        @return A comprehensive description of the laser device in it's running environment, e.g. for support requests
        """
        cPreamble = ct.create_string_buffer(strPreamble.encode())
        cCallingSW = ct.create_string_buffer(strCallingSW.encode())
        ulOptions = 0
        if NO_PREAMBLE:
            ulOptions |= 1
        if NO_TITLE:
            ulOptions |= 2
        if NO_CALLING_SW_INDENT:
            ulOptions |= 4
        if NO_SYSTEM_INFO:
            ulOptions |= 8
        cBufferLen = bufferLen + len(cPreamble) + len(cCallingSW)
        cBuffer = ct.create_string_buffer(cBufferLen)
        self.__errchk(self.lib.SEPIA2_FWR_CreateSupportRequestText(ct.c_int(iDevIdx), cPreamble, cCallingSW, ct.c_uint32(ulOptions), ct.sizeof(cBuffer), cBuffer))
        #return cBuffer.value.decode("utf-8")
        # Python claims an error when it comes to the degree-character '°'
        cBufferStr = ""
        for i in range(0, len(cBuffer.value)):
            cBufferStr += "%c" % cBuffer.value[i]
        return cBufferStr
        
    def FWR_FreeModuleMap(self, iDevIdx):
        """
        int SEPIA2_FWR_FreeModuleMap (int iDevIdx );
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        Releases the memory on device allocated when FWR_GetModuleMap() was called
        """
        self.__errchk(self.lib.SEPIA2_FWR_FreeModuleMap(ct.c_int(iDevIdx)))
    
    #  Firmware Working Mode Functions (FWR, only for FW V1.05.420 and above)
    def FWR_GetWorkingMode(self, iDevIdx):
        """
        int SEPIA2_FWR_GetWorkingMode (int iDevIdx, int* piCurFWMode );
        Returns the current working mode
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @return 0 (default mode, commands & protective data written immediately), 1 Volatile (Commands sent immediately, data retarded)
        """
        iCurFWMode = ct.c_int()
        self.__errchk(self.lib.SEPIA2_FWR_GetWorkingMode(ct.c_int(iDevIdx), byref(iCurFWMode)))
        return iCurFWMode.value
        
    def FWR_SetWorkingMode(self, iDevIdx, iCurFWMode):
        """
        int SEPIA2_FWR_SetWorkingMode (int iDevIdx, int iCurFWMode );
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iCurFWMode New FW mode: 0 (default mode, commands & protective data written immediately), 1 Volatile (Commands sent immediately, data retarded)
        """
        iCurFWMode = ct.c_int(iCurFWMode)
        self.__errchk(self.lib.SEPIA2_FWR_SetWorkingMode(ct.c_int(iDevIdx), iCurFWMode))
        
    def FWR_StoreAsPermanentValues(self, iDevIdx):
        """
        int SEPIA2_FWR_StoreAsPermanentValues (int iDevIdx );
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        This function calculates the protective data for all modules changed and sends them to the device.
        The working mode stays “volatile”.
        """
        self.__errchk(self.lib.SEPIA2_FWR_StoreAsPermanentValues(ct.c_int(iDevIdx)))
        
    def FWR_RollBackToPermanentValues(self, iDevIdx):
        """
        int SEPIA2_FWR_RollBackToPermanentValues (int iDevIdx );
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        This function re–sends commands to discard all changes made since the working mode was switched. 
        The working mode changes to “stay permanent”.
        """
        self.__errchk(self.lib.SEPIA2_FWR_RollBackToPermanentValues(ct.c_int(iDevIdx)))

    #  Common Module Functions (COM)
    def COM_DecodeModuleType(self, iModuleType):
        """
        int SEPIA2_COM_DecodeModuleType (int iModuleType, char* cModuleType );
        @param iModuleType Module type, as returned by COM_GetModuleType()
        This function works “off line”, without a PQ Laser Device running.
        It decodes the module type and returns the appropriate module type string
        @return module type string
        """
        cModuleType = ct.create_string_buffer(Sepia2_Def.SEPIA2_MODULETYPESTRING_LEN + 1)
        self.__errchk(self.lib.SEPIA2_COM_DecodeModuleType(ct.c_int(iModuleType), cModuleType))
        return cModuleType.value.decode("utf-8")

    def COM_DecodeModuleTypeAbbr(self, iModuleType):
        """
        int SEPIA2_COM_DecodeModuleTypeAbbr (int iModuleType, char* cModTypeAbbr );
        @param iModuleType Module type, as returned by COM_GetModuleType()
        This function works “off line”, without a PQ Laser Device running.
        It decodes the module type and returns the appropriate module type abbreviation string
        @return module type abbreviation string
        """
        cModTypeAbbr = ct.create_string_buffer(5)
        self.__errchk(self.lib.SEPIA2_COM_DecodeModuleTypeAbbr(ct.c_int(iModuleType), cModTypeAbbr))
        return cModTypeAbbr.value.decode("utf-8")

    def COM_GetModuleType(self, iDevIdx, iSlotId, iGetPrimary):
        """
        int SEPIA2_COM_GetModuleType (int iDevIdx, int iSlotId, int iGetPrimary, int* piModuleType );
        Returns the module type code for a primary or secondary module respectively, located in a given slot.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iGetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        @return Module type integer
        @see COM_DecodeModuleType()
        """
        iModuleType = ct.c_int()
        self.__errchk(self.lib.SEPIA2_COM_GetModuleType(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iGetPrimary), byref(iModuleType)))
        return iModuleType.value

    def COM_GetSerialNumber(self, iDevIdx, iSlotId, iGetPrimary):
        """
        int SEPIA2_COM_GetSerialNumber (int iDevIdx, int iSlotId, int iGetPrimary, char* cSerialNumber );
        Returns the serial number for a module
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iGetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        """
        cSerialNumber = ct.create_string_buffer(Sepia2_Def.SEPIA2_SERIALNUMBER_LEN)
        self.__errchk(self.lib.SEPIA2_COM_GetSerialNumber(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iGetPrimary), cSerialNumber))
        return cSerialNumber.value.decode("utf-8")

    def COM_GetPresetInfo(self, iDevIdx, iSlotId, iGetPrimary, iPresetNr):
        """
        int SEPIA2_COM_GetPresetInfo (int iDevIdx, int iSlotId, int iGetPrimary, int iPresetNr, unsigned char* pbIsSet, char* cPresetMemo );
        Returns the preset info identified by iPresetNr for a given module.
        Initially, the content of preset 1 and preset 2 is not assigned; In this case, the content of pbIsSet will be false (i. e. 0).
        Additionally, the text stored with the presets when the function SaveAsPreset was last invoked for the preset block, is returned in cPresetMemo
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iGetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        @param iPresetNr The preset index (-1: factory default, 0: current, 1: preset 1, 2: preset 2)
        @return Tuple(True if preset is set, preset memo string for the given module)
        @note Testing showed that only Preset nr 0 returns set True, but all return memo "-"
        """
        bIsSet = ct.c_uint8()
        cPresetMemo = ct.create_string_buffer(65)
        self.__errchk(self.lib.SEPIA2_COM_GetPresetInfo(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iGetPrimary), ct.c_int(iPresetNr), byref(bIsSet), cPresetMemo))
        return (bIsSet.value != 0, cPresetMemo.value.decode("utf-8"))

    def COM_RecallPreset(self, iDevIdx, iSlotId, iGetPrimary, iPresetNr):
        """
        int SEPIA2_COM_RecallPreset (int iDevIdx, int iSlotId, int iGetPrimary, int iPresetNr );
        Recalls the preset data as stored in the preset block identified by iPresetNr.
        Recalling a preset means to overwrite all current settings by the desired ones.
        The settings previously active are lost!
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iGetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        @param iPresetNr The preset index (-1: factory default, 0: current, 1: preset 1, 2: preset 2)
        """
        self.__errchk(self.lib.SEPIA2_COM_RecallPreset(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iGetPrimary), ct.c_int(iPresetNr)))

    def COM_SaveAsPreset(self, iDevIdx, iSlotId, iGetPrimary, iPresetNr, strPresetMemo):
        """
        int SEPIA2_COM_SaveAsPreset (int iDevIdx, int iSlotId, int iGetPrimary, int iPresetNr, char* cPresetMemo );
        Stores the currently active settings into the preset block identified by iPresetNr for a given module.
        Consider, if presets were already stored in the desired presets block, they will be overwritten without any further request.
        Don't forget to pass a meaningful text over with the cPresetMemo; It might be working as a remainder to prevent you from an unintentional loss of preset data. 
        Use the COM_GetPresetInfo() function to get informed on potential presets already stored in the destination block.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iGetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        @param iPresetNr The preset index (-1: factory default, 0: current, 1: preset 1, 2: preset 2)
        @param strPresetMemo Preset memo, this is essentially a name for the preset
        """
        cPresetMemo = ct.create_string_buffer(strPresetMemo.encode(), 65)
        self.__errchk(self.lib.SEPIA2_COM_SaveAsPreset(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iGetPrimary), ct.c_int(iPresetNr), cPresetMemo))

    def COM_GetSupplementaryInfos(self, iDevIdx, iSlotId, iGetPrimary):
        """
        int SEPIA2_COM_GetSupplementaryInfos (int iDevIdx, int iSlotId, int iGetPrimary, char* cLabel, char* cReleaseDate, char* cRevision, char* cMemo );
        Returns supplementary string information for a given module. Mainly needed for support
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iGetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        @return Tuple(internal label string, release date string, revision string, serial number string)
        """
        cLabel = ct.create_string_buffer(9)
        cReleaseDate = ct.create_string_buffer(9)
        cRevision = ct.create_string_buffer(9)
        cMemo = ct.create_string_buffer(129)
        self.__errchk(self.lib.SEPIA2_COM_GetSupplementaryInfos(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iGetPrimary), cLabel, cReleaseDate, cRevision, cMemo))
        return (cLabel.value.decode("utf-8"), cReleaseDate.value.decode("utf-8"), cRevision.value.decode("utf-8"), cMemo.value.decode("utf-8"))

    def COM_HasSecondaryModule(self, iDevIdx, iSlotId):
        """
        int SEPIA2_COM_HasSecondaryModule (int iDevIdx, int iSlotId, int* piHasSecondary);
        Returns if the module in the named slot has attached a secondary one (laser head).
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return True if module has a secondary module (e.g. laser head)
        """
        iHasSecondary = ct.c_int()
        self.__errchk(self.lib.SEPIA2_COM_HasSecondaryModule(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(iHasSecondary)))
        return iHasSecondary.value != 0

    def COM_IsWritableModule(self, iDevIdx, iSlotId, iGetPrimary):
        """
        int SEPIA2_COM_IsWritableModule (int iDevIdx, int iSlotId, int iGetPrimary, unsigned char* pbIsWritable );
        Returns the write protection state of the module's definition, calibration and set-up memory.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iGetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        @return False, if the memory block is write protected
        """
        bIsWritable = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_COM_IsWritableModule(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iGetPrimary), byref(bIsWritable)))
        return bIsWritable.value != 0

    def COM_UpdateModuleData(self, iDevIdx, iSlotId, iSetPrimary, strDCLFileName):
        """
        int SEPIA2_COM_UpdateModuleData (int iDevIdx, int iSlotId, int iSetPrimary, char* cDCLFileName );
        ??? (documentation for this has copy paste of previous fns description)
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iSetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        @param strDCLFileName File path of the binary image of the update data
        @note This has not been tested as I don't wish to unnecessarily update firmware, only slot 100 responded as writable
        """
        cDCLFileName = ct.create_string_buffer(strDCLFileName.encode())
        self.__errchk(self.lib.SEPIA2_COM_UpdateModuleData(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iSetPrimary), cDCLFileName))

    def COM_GetFormatVersion(self, iDevIdx, iSlotId, iGetPrimary):
        """
        int SEPIA2_COM_GetFormatVersion (int iDevIdx, int iSlotId, int iGetPrimary,  word* pwFormatVersion );
        This function returns the value of the “format version” field from the header of the specified module. 
        This format version identifies the descriptive structures (e.g., 0x0105 stands for version 1.05). 
        Besides for support tools written by PicoQuant, this data is purely informative.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iGetPrimary True if this call concerns a primary (e. g. laser driver) else False if a secondary module (e. g. laser head) in the given slot
        @return Integer, that when read as hex denotes the format version
        @note FWR_GetModuleMap() must be called first
        """
        wFormatVersion = ct.c_uint16() # assuming windows WORD
        self.__errchk(self.lib.SEPIA2_COM_GetFormatVersion(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iGetPrimary), byref(wFormatVersion)))
        return wFormatVersion.value
    
    # Device Operational Safety Controller Functions (SCM)
    def SCM_GetPowerAndLaserLEDS(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SCM_GetPowerAndLaserLEDS (int iDevIdx, int iSlotId, unsigned char* pbPowerLED, unsigned char* pbLaserActLED);
        Returns the state of the power LED and the laser active LED.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(True if Power LED is on else False, True if Laser Active LED is on else False)
        @note iSlotId==0 for Hicks C14 configuration
        """
        bPowerLED = ct.c_uint8()
        bLaserActLED = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SCM_GetPowerAndLaserLEDS(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(bPowerLED), byref(bLaserActLED)))
        return (bPowerLED.value != 0, bLaserActLED.value != 0)
        
    def SCM_GetLaserLocked(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SCM_GetLaserLocked (int iDevIdx, int iSlotId, unsigned char* pbLocked );
        Returns the state of the laser power line. 
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return True if the laser is down either by hardlock (key), power failure or softlock (firmware, GUI, custom software), else False
        @note iSlotId==0 for Hicks C14 configuration
        """
        bLocked = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SCM_GetLaserLocked(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(bLocked)))
        return bLocked.value != 0
        
    def SCM_GetLaserSoftLock(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SCM_GetLaserSoftLock (int iDevIdx, int iSlotId, unsigned char* pbSoftLocked );
        Returns the contents of the soft lock register.
        Note, that this information will not stand for the real state of the laser power line.
        A hard lock overrides a soft unlock
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Contents of the soft lock register
        @note iSlotId==0 for Hicks C14 configuration
        """
        bSoftLocked = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SCM_GetLaserSoftLock(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(bSoftLocked)))
        return bSoftLocked.value != 0
        
    def SCM_SetLaserSoftLock(self, iDevIdx, iSlotId, softLocked):
        """
        int SEPIA2_SCM_SetLaserSoftLock (int iDevIdx, int iSlotId, unsigned char bSoftLocked );
        Sets the content of the soft lock register
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param softLocked Desired value of the soft lock register
        @note iSlotId==0 for Hicks C14 configuration
        """
        bSoftLocked = ct.c_uint8(softLocked != 0)
        self.__errchk(self.lib.SEPIA2_SCM_SetLaserSoftLock(ct.c_int(iDevIdx), ct.c_int(iSlotId), bSoftLocked))
        
        
    # Enhanced Oscillator Functions (SOMD)
    def SOMD_DecodeFreqTrigMode(self, iDevIdx, iSlotId, iFreqTrigMode):
        """
        int SEPIA2_SOMD_DecodeFreqTrigMode (int iDevIdx, int iSlotId, int iFreqTrigMode, char* cFreqTrigMode );
        Returns the frequency resp. trigger mode string at list position <iFreqTrigMode> for a given SOMD module.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iFreqTrigMode index into the list of reference sources, integer (0…4)
        @return Frequency resp. trigger mode string
        """
        cFreqTrigMode = ct.create_string_buffer(Sepia2_Def.SEPIA2_SOM_FREQ_TRIGMODE_LEN + 1)
        self.__errchk(self.lib.SEPIA2_SOMD_DecodeFreqTrigMode(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iFreqTrigMode), cFreqTrigMode))
        return cFreqTrigMode.value.decode("utf-8")
        
    def SOMD_GetTriggerRange(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetTriggerRange (int iDevIdx, int iSlotId, int* piMilliVoltLow, int* piMilliVoltHigh);
        This function gets the adjustable range of the trigger level.
        The limits are specified in mV.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(MilliVoltLow, MilliVoltHigh)
        """
        iMilliVoltLow = ct.c_int()
        iMilliVoltHigh = ct.c_int()
        self.__errchk(self.lib.SEPIA2_SOMD_GetTriggerRange(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(iMilliVoltLow), byref(iMilliVoltHigh)))
        return (iMilliVoltLow.value, iMilliVoltHigh.value)
        
    def SOMD_GetTriggerLevel(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetTriggerLevel (int iDevIdx, int iSlotId, int* piMilliVolt );
        This function gets the current value of the trigger level specified in mV
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        """
        iMilliVolt = ct.c_int()
        self.__errchk(self.lib.SEPIA2_SOMD_GetTriggerLevel(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(iMilliVolt)))
        return iMilliVolt.value
        
    def SOMD_SetTriggerLevel(self, iDevIdx, iSlotId, iMilliVolt):
        """
        int SEPIA2_SOMD_SetTriggerLevel (int iDevIdx, int iSlotId, int iMilliVolt );
        This function sets the new value of the trigger level specified in mV.
        To learn about the individual valid range for the trigger level, call GetTriggerRange.
        Notice: Since the scale of the trigger level has its individual step width, the value you specified will be rounded off to the nearest valid value. It is recommended to call the GetTriggerLevel function to check the “level in fact”.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iMilliVolt the desired value of the trigger level
        """
        self.__errchk(self.lib.SEPIA2_SOMD_SetTriggerLevel(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iMilliVolt)))
        
    def SOMD_GetBurstLengthArray(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetBurstLengthArray (int iDevIdx, int iSlotId, long* plBurstLen1, long* plBurstLen2, long* plBurstLen3, long* plBurstLen4, long* plBurstLen5, long* plBurstLen6, long* plBurstLen7, long* plBurstLen8 );
        This function gets the current values for the respective burst length of the eight output channels.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple of channel 1...8 burst lengths
        """
        lBurstLen1 = ct.c_int32()
        lBurstLen2 = ct.c_int32()
        lBurstLen3 = ct.c_int32()
        lBurstLen4 = ct.c_int32()
        lBurstLen5 = ct.c_int32()
        lBurstLen6 = ct.c_int32()
        lBurstLen7 = ct.c_int32()
        lBurstLen8 = ct.c_int32()
        self.__errchk(self.lib.SEPIA2_SOMD_GetBurstLengthArray(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(lBurstLen1), byref(lBurstLen2), byref(lBurstLen3), byref(lBurstLen4), byref(lBurstLen5), byref(lBurstLen6), byref(lBurstLen7), byref(lBurstLen8)))
        return (lBurstLen1.value, lBurstLen2.value, lBurstLen3.value, lBurstLen4.value, lBurstLen5.value, lBurstLen6.value, lBurstLen7.value, lBurstLen8.value)
        
    def SOMD_SetBurstLengthArray(self, iDevIdx, iSlotId, lBurstLen):
        """
        int SEPIA2_SOMD_SetBurstLengthArray (int iDevIdx, int iSlotId, long lBurstLen1, long lBurstLen2, long lBurstLen3, long lBurstLen4, long lBurstLen5, long lBurstLen6, long lBurstLen7, long lBurstLen8 );
        This function sets the new values for the respective burst length of the eight output channels.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param lBurstLen A list or tuple with length 8, desired burst lengths for corresponding channels
        """
        if len(lBurstLen) != 8:
            raise Exception("len(lBurstLen)!=8, len(lBurstLen)==%d"%(len(lBurstLen)))
        lBurstLen1 = ct.c_int32(lBurstLen[0])
        lBurstLen2 = ct.c_int32(lBurstLen[1])
        lBurstLen3 = ct.c_int32(lBurstLen[2])
        lBurstLen4 = ct.c_int32(lBurstLen[3])
        lBurstLen5 = ct.c_int32(lBurstLen[4])
        lBurstLen6 = ct.c_int32(lBurstLen[5])
        lBurstLen7 = ct.c_int32(lBurstLen[6])
        lBurstLen8 = ct.c_int32(lBurstLen[7])
        self.__errchk(self.lib.SEPIA2_SOMD_SetBurstLengthArray(ct.c_int(iDevIdx), ct.c_int(iSlotId), lBurstLen1, lBurstLen2, lBurstLen3, lBurstLen4, lBurstLen5, lBurstLen6, lBurstLen7, lBurstLen8))
        
    def SOMD_GetOutNSyncEnable(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetOutNSyncEnable (int iDevIdx, int iSlotId, unsigned char* pbOutEnable, unsigned char* pbSyncEnable, unsigned char* pbSyncInverse );
        This function gets the current values of the output control and sync signal composing.
        (For the following illustrations refer to the screen shot of the main dialogue in the main manual and to the chapter on sync signal composition with SOM 828 modules.)
        Each bit in the byte pointed at by <pbOutEnable> stands for an output enable boolean. Thus if all bits are set except of the second and fifth, this byte reads 0xED, which means all but the second and fifth output channel are enabled.
        Each bit in the byte pointed at by <pbSyncEnable> stands for an sync enable boolean. Thus if all bits are clear except of the first and third, this byte reads 0x05, which means only the first and third output channel is mirrored to the sync signal composition.
        The byte pointed at by <pbSyncInverse> stands for a boolean. It defines whether the sync mask length stands for the count of pulses first let through (bSyncInverse = true, 1) or for the count of pulses first blocked (bSyncInverse = false, 0)
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(pbOutEnable, pbSyncEnable, pbSyncInverse)
        """
        bOutEnable = ct.c_uint8()
        bSyncEnable = ct.c_uint8()
        bSyncInverse = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SOMD_GetOutNSyncEnable(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(bOutEnable), byref(bSyncEnable), byref(bSyncInverse)))
        return (bOutEnable.value, bSyncEnable.value, bSyncInverse.value != 0)
        
    def SOMD_SetOutNSyncEnable(self, iDevIdx, iSlotId, OutEnable, SyncEnable, SyncInverse):
        """
        int SEPIA2_SOMD_SetOutNSyncEnable (int iDevIdx, int iSlotId, unsigned char bOutEnable, unsigned char bSyncEnable, unsigned char bSyncInverse );
        This function sets the new values for the output control and sync signal composing
        (For the following illustrations refer to the screen shot of the main dialogue in the main manual and to the chapter on sync signal composition with SOM 828 modules.)
        Each bit in the byte <bOutEnable> stands for an output enable boolean. Thus if all bits are set except of the second and fifth, this byte reads 0xED (0b11101101), which means all but the second and fifth output channel are enabled.
        Each bit in the byte <bSyncEnable> stands for a sync enable boolean. Thus if all bits are clear except of the first and third, this byte reads 0x05 (0b00000101), which means only the first and third output channel is mirrored to the sync signal composition.
        The byte <bSyncInverse> stands for a boolean. It defines whether the sync mask length stands for the count of first pulses let through (bSyncInverse = true, 1) or for the count of first pulses blocked (bSyncInverse = false, 0) of each individual burst when composing the sync signal.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param OutEnable output channel enable mask, bitcoded (byte, 0…255)
        @param SyncEnable sync channel enable mask, bitcoded (byte, 0…255)
        @param SyncInverse sync mask inverse, boolean (byte, 0…1)
        """
        self.__errchk(self.lib.SEPIA2_SOMD_SetOutNSyncEnable(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_uint8(OutEnable), ct.c_uint8(SyncEnable), ct.c_uint8(SyncInverse != 0)))
        
    def SOMD_DecodeAUXINSequencerCtrl(self, iAUXInCtrl):
        """
        int SEPIA2_SOMD_DecodeAUXINSequencerCtrl (int iAUXInCtrl,  char* cSequencerCtrl);
        It decodes the sequencer control code returned by the SOM function GetAUXIOSequencerCtrl and returns the appropriate sequencer control string
        @param iAUXInCtrl sequencer control, integer, taking the byte value as returned by the SOM function GetAUXIOSequencerCtrl
        @return sequencer control string
        """
        cSequencerCtrl = ct.create_string_buffer(25)
        self.__errchk(self.lib.SEPIA2_SOMD_DecodeAUXINSequencerCtrl(ct.c_int(iAUXInCtrl), cSequencerCtrl))
        return cSequencerCtrl.value.decode("utf-8")
        
    def SOMD_GetAUXIOSequencerCtrl(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetAUXIOSequencerCtrl (int iDevIdx, int iSlotId, unsigned char* pbAUXOutCtrl, unsigned char* pbAUXInCtrl );
        This function gets the current control values for AUX OUT and AUX IN.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(pbAUXOutCtrl, pbAUXInCtrl)
        pbAUXOutCtrl: a boolean “sequence index pulse enabled on AUX Out”.
        pbAUXInCtrl: The current running/restart mode of the sequencer (0…3). The user can decode this value to a human readable string using the DecodeAUXINSequencerCtrl function.
          0: free running
          1: running / restarting, if AUX IN is on logical High level,
          2: running / restarting, if AUX IN is on logical Low level.
          3: disabled / restarting on neither level at AUX IN.
        """
        bAUXOutCtrl = ct.c_uint8()
        bAUXInCtrl = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SOMD_GetAUXIOSequencerCtrl(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(bAUXOutCtrl), byref(bAUXInCtrl)))
        return (bAUXOutCtrl.value != 0, bAUXInCtrl.value)
        
    def SOMD_SetAUXIOSequencerCtrl(self, iDevIdx, iSlotId, bAUXOutCtrl, bAUXInCtrl):
        """
        int SEPIA2_SOMD_SetAUXIOSequencerCtrl (int iDevIdx, int iSlotId, unsigned char bAUXOutCtrl, unsigned char bAUXInCtrl );
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param bAUXOutCtrl boolean, true if sequence index pulse is enabled on AUX OUT
        @param bAUXInCtrl controls restarting condition of the sequencer (0…3)
          0: free running
          1: running / restarting, if AUX IN is on logical High level,
          2: running / restarting, if AUX IN is on logical Low level.
          3: disabled / restarting on neither level at AUX IN.
        """
        self.__errchk(self.lib.SEPIA2_SOMD_SetAUXIOSequencerCtrl(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_uint8(bAUXOutCtrl), ct.c_uint8(bAUXInCtrl)))

    def SOMD_GetFreqTrigMode(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetFreqTrigMode (int iDevIdx, int iSlotId, int* piFreqTrigMode, unsigned char* pbSynchronize );
        This function inquires the current setting for the reference source in a given SOMD. In the integer variable, pointed to by <piFreqTrigMode> it returns an index into the list of possible sources. If the trigger source is external, <pbSynchronize> tells, if the module should run synchronized to the signal using SynchronizeNow. (The delay feature for the burst outputs is only allowed for internal triggers, or if the module is synchronized to an external trigger signal.)
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(index into the list of reference sources, boolean: if true synchronization is mandatory)
        """
        iFreqTrigMode = ct.c_int()
        bSynchronize = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SOMD_GetFreqTrigMode(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(iFreqTrigMode), byref(bSynchronize)))
        return (iFreqTrigMode.value, bSynchronize.value != 0)
        
    def SOMD_SetFreqTrigMode(self, iDevIdx, iSlotId, iFreqTrigMode, Synchronize):
        """
        int SEPIA2_SOMD_SetFreqTrigMode (int iDevIdx, int iSlotId, int iFreqTrigMode, unsigned char bSynchronize );
        This function sets the new reference source for a given SOMD. It is passed over as a new value for the index into the list of possible sources. Additionally, if externally triggered, the module could be synchronized to the external signal using the function SynchronizeNow. 
        (The delay feature for the burst outputs is only allowed for internal triggers, or if the module is synchronized to an external trigger signal.)
        Call GetStatusError to check the state afterwards!
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iFreqTrigMode index into the list of reference sources
          (Based on testing in Hicks C14, may vary with other devices/configurations)
          0: rising  edge (ext.)
          1: falling edge (ext.)
          2: 80.00 MHz (int. A)
          3: 64.00 MHz (int. B)
          4: 50.00 MHz (int. C)
        @param Synchronize boolean, if true synchronization is mandatory (only on ext. trigger modes)
        """
        self.__errchk(self.lib.SEPIA2_SOMD_SetFreqTrigMode(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iFreqTrigMode), ct.c_uint8(Synchronize != 0)))
        
    def SOMD_GetBurstValues(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetBurstValues (int iDevIdx, int iSlotId, unsigned short* psDivider, unsigned char* pbPreSync, unsigned char* pbSyncMask );
        This function returns the current settings of the determining values for the timing of the pre scaler. Refer to the main manual chapter on SOM 828-D modules to learn about these values. (This function differs from the SOM type in the wider range of the divider.)
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(current divider for the pre scalar, current pre sync value, current sync mask)
        """
        sDivider = ct.c_uint16()
        bPreSync = ct.c_uint8()
        bSyncMask = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SOMD_GetFreqTrigMode(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(sDivider), byref(bPreSync), byref(bSyncMask)))
        return (sDivider.value, bPreSync.value, bSyncMask.value)
        
    def SOMD_SetBurstValues(self, iDevIdx, iSlotId, sDivider, bPreSync, bSyncMask):
        """
        int SEPIA2_SOMD_SetBurstValues (int iDevIdx, int iSlotId, unsigned short sDivider, unsigned char bPreSync, unsigned char bSyncMask );
        This function sets the new determining values for the timing of the pre scaler. Refer to the main manual chapter on SOM 828-D modules to learn about these values. (This function differs from the SOM type in the wider range of the divider.)
        Call GetStatusError to check the state afterwards!
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param sDivider the desired divider for the pre scaler  (1…65535)
        @param bPreSync the desired pre sync value (0…<sDivider>-1)
        @param bSyncMask the desired sync mask value (0…255)
        @note This failed silently whilst testing, SOMD_GetStatusError() == 64, SOMD_DecodeModuleState(64) == "FRAM write-protected"
        """
        self.__errchk(self.lib.SEPIA2_SOMD_SetBurstValues(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_uint16(sDivider), ct.c_uint8(bPreSync), ct.c_uint8(bSyncMask)))
        
    def SOMD_DecodeModuleState(self, wState):
        """
        int SEPIA2_SOMD_DecodeModuleState (unsigned short wState, char* cStatusText );
        @param wState PQ module state (0...65535)
        @return Module status string
        """
        cStatusText = ct.create_string_buffer(96)
        self.__errchk(self.lib.SEPIA2_SOMD_DecodeModuleState(ct.c_uint16(wState), cStatusText))
        return cStatusText.value.decode("utf-8")
        
    def SOMD_GetStatusError(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetStatusError (int iDevIdx, int iSlotId, unsigned short* pwState, short* piErrorCode );
        The state is bit coded and can be decoded by the SOMD function DecodeModuleState. If the error state bit (0x0010) is set, the error code <piErrorCode> is transmitted as well, else this variable is zero. As a side effect, error state bit and error code are cleared, if there are no further errors pending. Decode the error codes received with the LIB function DecodeError.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(state of the SOMD module, error code)
        """
        wState = ct.c_uint16()
        iErrorCode = ct.c_int16()
        self.__errchk(self.lib.SEPIA2_SOMD_GetStatusError(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(wState), byref(iErrorCode)))
        return (wState.value, iErrorCode.value)
        
    def SOMD_GetHWParams(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetHWParams (int iDevIdx, int iSlotId, unsigned short* pwHWParTemp1, unsigned short* pwHWParTemp2, unsigned short* pwHWParTemp3, unsigned short* pwHWParVolt1, unsigned short* pwHWParVolt2, unsigned short* pwHWParVolt3, unsigned short* pwHWParVolt4, unsigned short* pwHWParAUX );
        This function returns the current results of some temperature and voltage measurements inside the SOMD module. These values are used to rate the working conditions and judge the stability of the module. The function is needed for documentation of the module's current working conditions in case of a support request, beside this, it is solely informative.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(temperatures[3], voltages[4], aux measure)
        """
        pwHWParTemp1 = ct.c_uint16()
        pwHWParTemp2 = ct.c_uint16()
        pwHWParTemp3 = ct.c_uint16()
        pwHWParVolt1 = ct.c_uint16()
        pwHWParVolt2 = ct.c_uint16()
        pwHWParVolt3 = ct.c_uint16()
        pwHWParVolt4 = ct.c_uint16()
        pwHWParAUX = ct.c_uint16()
        self.__errchk(self.lib.SEPIA2_SOMD_GetHWParams(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(pwHWParTemp1), byref(pwHWParTemp2), byref(pwHWParTemp3), byref(pwHWParVolt1), byref(pwHWParVolt2), byref(pwHWParVolt3), byref(pwHWParVolt4), byref(pwHWParAUX)))
        return ((pwHWParTemp1.value, pwHWParTemp2.value, pwHWParTemp3.value), (pwHWParVolt1.value, pwHWParVolt2.value, pwHWParVolt3.value, pwHWParVolt4.value), pwHWParAUX.value)
        
    def SOMD_GetFWVersion(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetFWVersion (int iDevIdx, int iSlotId, unsigned long* pulFWVersion );
        Firmware Version is coded (byte[3] = major-nr., byte[2] = minor-nr., byte[1] + byte[0] as word = build-nr.)
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Firmware version encoded into a 4-byte unsigned integer
        @todo Could instead decode and return this as tuple with 3 elements
        """
        ulFWVersion = ct.c_uint32()
        self.__errchk(self.lib.SEPIA2_SOMD_GetStatusError(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(ulFWVersion)))
        return ulFWVersion.value
        
    def SOMD_SynchronizeNow(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_SynchronizeNow (int iDevIdx, int iSlotId );
        If the triggering is set to one of the external modes using the function SetFreqTrigMode, this function is used to synchronize to the external triggering signal. Once this function succeeded, it is allowed to apply delay info to the bursts at the sequencer outputs.
        Call GetStatusError to check the state afterwards!
        Get information on the synchronized-to signal calling GetTrigSyncFreq.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @note untested, won't be using external triggers
        """
        self.__errchk(self.lib.SEPIA2_SOMD_SynchronizeNow(ct.c_int(iDevIdx), ct.c_int(iSlotId)))
        
    def SOMD_GetTrigSyncFreq(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetTrigSyncFreq (int iDevIdx, int iSlotId, unsigned char* pbFreqStable, unsigned long* pulTrigSyncFrq );
        If synchronized, call this function to get information on the triggering signal. <pbFreqStable> stays true, as long as the signal stays within the tolerance window of ±100 ppm.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(bFreqStable, ulTrigSyncFrq)
          bFreqStable: boolean denoting if the synchronized-to frequency is still stable (within a tolerance window of ±100 ppm
          ulTrigSyncFrq: triggering frequency in Hz
        """
        bFreqStable = ct.c_uint8()
        ulTrigSyncFrq = ct.c_uint32()
        self.__errchk(self.lib.SEPIA2_SOMD_GetTrigSyncFreq(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(bFreqStable), byref(ulTrigSyncFrq)))
        return (bFreqStable.value != 0, ulTrigSyncFrq.value)
        
    def SOMD_GetDelayUnits(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SOMD_GetDelayUnits (int iDevIdx, int iSlotId, double* pfCoarseDlyStep, byte* pbFineDlySteps );
        This function should always be called, after the base oscillator values (source, divider, synchronized frequency, etc.) had changed. It returns the coarse delay stepwidth in seconds and the currently possible amount of fine steps to apply. The coarse delay stepwidth is mainly varying with the main clock, depending on the trigger source (base oscillator or external signal) and the pre-division factor. Usually the stepwidth will be about 650 to 950 psec; the value is given in seconds. Since this value is varying on all changes to the main clock, the amount of steps to meet a desired delay length has to be recalculated then. The same goes for the amount of fine steps. A fine step has a module depending, individually varying steplength of typically 15 to 35 psec
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(width of a coarse delay step in secs, fine delay maximum step count)
        """
        fCoarseDlyStep = ct.c_double()
        bFineDlySteps = ct.c_int8()
        self.__errchk(self.lib.SEPIA2_SOMD_GetDelayUnits(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(fCoarseDlyStep), byref(bFineDlySteps)))
        return (fCoarseDlyStep.value, bFineDlySteps.value)
        
    def SOMD_GetSeqOutputInfos(self, iDevIdx, iSlotId, bSeqOutputIdx):
        """
        int SEPIA2_SOMD_GetSeqOutputInfos (int iDevIdx, int iSlotId, byte bSeqOutputIdx, byte* pbDelayed, byte* pbForcdUndlyd, byte* pbOutCombi, byte* pbMaskedCombi, double* pfCoarseDly, byte* pbFineDly );
        This function returns all information necessary to describe the state of the sequencer output identified by <bSeqOutputIdx>. Note, that it returns apparently redundant information: If e.g. <pbDelayed> is true, the information on output combinations seems sort of useless, since burst combinations aren't allowed on delayed signals. On the other hand, there is no virtue in reading delay data, if <pbDelayed> is false or <pbForcdUndlyd> is true. But then again, consider, this function was designed for complex GUI purposes. It offers all the alternately hidden, but still effective information, to enable a GUI to seamlessly switch back and forth between the different states.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param bSeqOutputIdx sequencer output index (byte, 1…8)
        @return Tuple(bDelayed, bForcdUndlyd, bOutCombi, bMaskedCombi, fCoarseDly, bFineDly)
          bDelayed: boolean
          bForcdUndlyd: forced being undelayed, boolean
          bOutCombi: output channel combination mask, bitcoded 
          bMaskedCombi: boolean
          fCoarseDly: coarse delay in ns.
          bFineDly: fine delay steps in a.u. 
        """
        # Docs says byte, one goes to 255 so assume unsigned
        bDelayed = ct.c_uint8()
        bForcdUndlyd = ct.c_uint8()
        bOutCombi = ct.c_uint8()
        bMaskedCombi = ct.c_uint8()
        fCoarseDly = ct.c_double()
        bFineDly = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SOMD_GetSeqOutputInfos(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_uint8(bSeqOutputIdx), byref(bDelayed), byref(bForcdUndlyd), byref(bOutCombi), byref(bMaskedCombi), byref(fCoarseDly), byref(bFineDly)))
        return (bDelayed.value != 0, bForcdUndlyd.value != 0, bOutCombi.value, bMaskedCombi.value != 0, fCoarseDly.value, bFineDly.value)
        
    def SOMD_SetSeqOutputInfos(self, iDevIdx, iSlotId, bSeqOutputIdx, bDelayed, bOutCombi, bMaskedCombi, fCoarseDly, bFineDly):
        """
        int SEPIA2_SOMD_SetSeqOutputInfos (int iDevIdx, int iSlotId, byte bSeqOutputIdx, byte bDelayed, byte bOutCombi, byte bMaskedCombi, double fCoarseDly, byte bFineDly );
        This function sets all information necessary to describe the state of the sequencer output identified by <bSeqOutputIdx>. Note, that it transmits apparently redundant information: If e.g. <bDelayed> is true, the information on output combinations seems sort of useless, since burst combinations aren't allowed on delayed signals. On the other hand, there is no virtue in setting delay data, if <bDelayed> is false. But then again, consider, this function was designed for complex GUI purposes. It sends all the alternately hidden, but still effective information, to enable a GUI to seamlessly switch back and forth between the different states.
        Note: <bOutCombi> must not equal 0. (At least one channel has to be assigned to the output.)
        Note that the currently legal values for <bFineDly> are module state dependent and have to be queried using the SOMD function GetDelayUnits.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param bSeqOutputIdx sequencer output index (byte, 1…8)
        @param bDelayed boolean
        @param bForcdUndlyd forced being undelayed, boolean
        @param bOutCombi output channel combination mask, bitcoded 
        @param bMaskedCombi boolean
        @param fCoarseDly coarse delay in ns.
        @param bFineDly fine delay steps in a.u.
        """
        # Docs says byte, one goes to 255 so assume unsigned
        self.__errchk(self.lib.SEPIA2_SOMD_SetSeqOutputInfos(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_uint8(bSeqOutputIdx), ct.c_uint8(bDelayed != 0), ct.c_uint8(bOutCombi), ct.c_uint8(bMaskedCombi != 0), ct.c_double(fCoarseDly), ct.c_uint8(bFineDly)))
        
    def SLM_DecodeFreqTrigMode(self, iFreq):
        """
        int SEPIA2_SLM_DecodeFreqTrigMode (int iFreq, char* cFreqTrigMode );
        Returns the frequency resp. trigger mode string at list position <iFreq> for any SLM module.
        @param iFreq index into the list of int. frequencies/ext. trigger modi (0…7)
          (Based on testing in Hicks C14, may vary with other devices/configurations)
          0: 80 MHz (int.)
          1: 40 MHz (int.)
          2: 20 MHz (int.)
          3: 10 MHz (int.)
          4:  5 MHz (int.)
          5:  2.5 MHz (int.)
          6: rising  edge (ext.)
          7: falling edge (ext.)
        @return frequency resp. trigger mode string
        """
        cFreqTrigMode = ct.create_string_buffer(29)
        self.__errchk(self.lib.SEPIA2_SLM_DecodeFreqTrigMode(ct.c_int(iFreq), cFreqTrigMode))
        return cFreqTrigMode.value.decode("utf-8")

    def SLM_DecodeHeadType(self, iHeadType):
        """
        int SEPIA2_SLM_DecodeHeadType (int iHeadType, char* cHeadType );
        Returns the head type string at list position <iHeadType> for any SLM module
        @param iHeadType index into the list of pulsed LED / laser head types (0…3)
        @return head type string
        """
        cHeadType = ct.create_string_buffer(19)
        self.__errchk(self.lib.SEPIA2_SLM_DecodeHeadType(ct.c_int(iHeadType), cHeadType))
        return cHeadType.value.decode("utf-8")
        
    def SLM_GetIntensityFineStep(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SLM_GetIntensityFineStep (int iDevIdx, int iSlotId, unsigned short* pwIntensity );
        This function gets the current intensity value of a given SLM driver module.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return intensity (as per mille of the laser head ctrl. voltage; 0…1000)
        """
        wIntensity = ct.c_uint16()
        self.__errchk(self.lib.SEPIA2_SLM_GetIntensityFineStep(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(wIntensity)))
        return wIntensity.value

    def SLM_SetIntensityFineStep(self, iDevIdx, iSlotId, wIntensity):
        """
        int SEPIA2_SLM_SetIntensityFineStep (int iDevIdx, int iSlotId, unsigned short wIntensity );
        This function sets the intensity value of a given SLM driver module
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param wIntensity the desired per mille value of the laser head controlling voltage (0...1000).
        """
        self.__errchk(self.lib.SEPIA2_SLM_SetIntensityFineStep(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_uint16(wIntensity)))
        
    def SLM_GetPulseParameters(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SLM_GetPulseParameters (int iDevIdx, int iSlotId, int* piFreq, unsigned char* pbPulseMode, int* piHeadType );
        This function gets the current pulse parameter values of a given SLM driver module.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(iFreq, bPulseMode, iHeadType)
          iFreq: index into list of frequencies/trigger modi (0…7)
          bPulseMode: pulse enabled (boolean), false can mean laser off or continuous wave depending on head capabilities
          iHeadType: index into list of pulsed LED/laser head types (0…3) ??? docs say pointer to byte but it's pointer to int
        """
        iFreq = ct.c_int()
        bPulseMode = ct.c_uint8()
        iHeadType = ct.c_int()
        self.__errchk(self.lib.SEPIA2_SLM_GetPulseParameters(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(iFreq), byref(bPulseMode), byref(iHeadType)))
        return (iFreq.value, bPulseMode.value != 0, iHeadType.value)

    def SLM_SetPulseParameters(self, iDevIdx, iSlotId, iFreq, bPulseMode):
        """
        int SEPIA2_SLM_SetPulseParameters (int iDevIdx, int iSlotId, int iFreq, unsigned char bPulseMode );
        This function sets the current pulse parameter values of a given SLM driver module.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iFreq index into list of frequencies/trigger modi (0…7)
        @param bPulseMode pulse enabled (boolean), false can mean laser off or continuous wave depending on head capabilities
        """
        self.__errchk(self.lib.SEPIA2_SLM_SetPulseParameters(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iFreq), ct.c_uint8(bPulseMode != 0)))

    def __SLM_GetParameters(self, iDevIdx, iSlotId):
        """
        int SEPIA2_SLM_GetParameters (int iDevIdx, int iSlotId, int* piFreq, unsigned char* pbPulseMode, int* piHeadType, unsigned char* pbIntensity );
        deprecated, instead use
            SEPIA2_SLM_GetIntensityFineStep(),
            SEPIA2_SLM_GetPulseParameters()
        This function gets the current values of a given SLM driver module.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @return Tuple(iFreq, bPulseMode, iHeadType)
          iFreq: index into list of frequencies/trigger modi (0…7)
          bPulseMode: pulse enabled (boolean), false can mean laser off or continuous wave depending on head capabilities
          iHeadType: index into list of pulsed LED/laser head types (0…3) ??? docs say pointer to byte but it's pointer to int
          bIntensity: intensity (as percentage of ctrl. voltage; 0…100)
        """
        iFreq = ct.c_int()
        bPulseMode = ct.c_uint8()
        iHeadType = ct.c_int()
        bIntensity = ct.c_uint8()
        self.__errchk(self.lib.SEPIA2_SLM_GetParameters(ct.c_int(iDevIdx), ct.c_int(iSlotId), byref(iFreq), byref(bPulseMode), byref(iHeadType), byref(bIntensity)))
        return (iFreq.value, bPulseMode.value != 0, iHeadType.value, bIntensity.value)

    def __SLM_SetParameters(self, iDevIdx, iSlotId, iFreq, PulseMode, bIntensity):
        """
        int SEPIA2_SLM_SetParameters (int iDevIdx, int iSlotId, int iFreq, unsigned char bPulseMode, unsigned char bIntensity );
        deprecated, instead use
            SEPIA2_SLM_SetIntensityFineStep(),
            SEPIA2_SLM_SetPulseParameters()
        This function sets the current values of a given SLM driver module.
        @param iDevIdx PQ Laser Device index (USB channel number, 0...7)
        @param iSlotId slot number, integer (000…989; refer to manual on slot numbers)
        @param iFreq index into list of frequencies/trigger modi (0…7)
        @param PulseMode pulse enabled (boolean), false can mean laser off or continuous wave depending on head capabilities
        @param bIntensity intensity (as percentage of ctrl. voltage; 0…100)
        """
        self.__errchk(self.lib.SEPIA2_SLM_SetParameters(ct.c_int(iDevIdx), ct.c_int(iSlotId), ct.c_int(iFreq), ct.c_uint8(PulseMode != 0), ct.c_uint8(bIntensity)))

#t = Sepia2()

