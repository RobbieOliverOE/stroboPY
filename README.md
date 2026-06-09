## Sepia2 x Andor Spectroscopy Control Software

This repository contains code for a Python GUI for configuring a PicoQuant Sepia2 laser controller and Andor camera for performing spectroscopy.

Other cameras are included in the GUI, but are unlikely to be fully supported.

### Running

The software can be executed by calling the main source file `pyTA/stroboPY.py` with Python.

If the argument `mock` is passed (e.g. `python stroboPY.py mock`) the GUI will mock the Sepia2 and Andor connections, to allow synthetic images to be collected.

### Interface

On load, the GUI has four tabs:

#### Hardware Tab

Prior to collecting data, it is necessary to connect to both the Andor and Sepia2.
Both connections can take a short amount of time to complete.

It is not possible to close the GUI whilst either device is connected, they should be safely disconnected prior to closing the GUI.

**Camera Connections**

The camera connections group allows the camera to be selected and connected.
This version of the software has been designed with the Andor camera in mind, therefore other camera selections may not work.
Andor does not make use of the IR Gain check.

When first connecting to the Andor, the camera will automatically cool, the connection will be complete once this has been achieved.

**Sepia2 Connection**

The Sepia2 connection group allows connection to a Sepia2 device via the PicoQuant laser driver library.
The fields are preconfigured to match the configuration found within Hicks C14.
These fields can be updated to target other configurations, however validation has not been implemented to ensure that the slot for each specified module corresponds with the expected module class.

#### Acquisition Tab

The acquisition tab completes a full workflow by collecting both pump and probe images for each of the times shown in the list box within "Time Options". This is repeated for the number of specified sweeps.

The three plot widgets, display the captured images:
* Bottom Left: The most recently collected `I_off`
* Bottom right: The most recently collected `(I_on - I_off)/I_off`
* Top right: The average `(I_on - I_off)/I_off` for the time delay selected with the slider to the left.

**Filename and Metadata**

The data entered within this group box has no impact.

**Zoom**

The data entered within this group box has no impact.

**Acquire Options**

The controls within this group box configure the Sepia2.

Non-specified values have defaults in place to ensure they match the Sepia2 GUI screenshot shared by James on Feb 16th (shown below).

`![Workflow configured within Sepia2 GUI](doc/sepia2_gui.png)

**Time Options**

This box works as provided, the list box specifies the time delays that are passed to the Sepia2 during acquisition, and the "Num. Sweeps" combo specifies how many times the full list is repeated (to calculate the average images).

**Launch Acquisition**
* Run, begins the acquisition process (see "Acquisition Workflow" below)
* Stop, cancels the executing acquisition process

#### Diagnostics Tab

Currently no workflow functionality has be implemented for this tab, however it's workflow can likely be implemented as a derivation of that in the Acquisition tab.

GUI elements common with the acquisition tab should remain in sync if updated.

#### Log Tab

Currently no functionality has be implemented for this tab.

### Development

The code has been built upon the source of `stroboPY.py` from [RobbieOliverOE/stroboPY](https://github.com/RobbieOliverOE/stroboPY). Areas of source code tied to removed GUI components have been removed, however much potentially redundant code still exists.

#### Known Issues

Continued development will be required to adjust the acquisition process for two blocking issues.

* The Andor camera is not currently triggered by the Sepia2's external signal. It has been proposed that repeated signals in a short window may resolve this. That would require updating the setters (stroboPY.py:451-677) to accommodate new defaults.
* The Sepia2 signal is continuous, as such it may not be possible to definitely start a pump on/of repeating pattern at specifically on or off. This will require restructuring of the `Acquisition::run()` method from `cameras.py:46`, which controls the Sepia2 and camera

#### Acquisition Workflow

The acquisition workflow forms the most complex component of the program, it is explained below.

* User pressed  "Run" within the acquisition tab (only possible if connected to Sepia2 and camera).
* `Application::run_acquisition()` (`stroboPY.py:681`) is triggered, this resets the GUI and initialises the acquisition process in the background thread (`self.acquire_thread`).
* `Acquisition::run()` (`cameras.py:38`) is where the background thread begins. This performs the acquisition workflow, looping through the provided list of time delays (`self.times_list`) to capture images from. After each pair of frames is collected, a signal (`self.frames_ready`) is emit, which sends the images back to the GUI.
* `Application::process_acquisition_frames()` (`stroboPY.py:735`) receives the images sent from the background frame and updates the GUI. When calculating the difference images, the image is centralised to avoid negative pixels, the code should have thorough comments.
    * `self.acquisition_i_off`, `self.acquisition_i_on` are dictionaries that hold the images collected for each `t_sw` during the acquisition workflow. They are cleared when a new acquisition workflow is started.
* If the user presses "Stop" within the acquisition tab, `Application::stop_acquisition()` (`stroboPY.py:730`) sends a signal to `Acquisition::stop` (`cameras.py:71`). This signal can only be processed during the acquisition workflow if the event loop within `Acquisition::run()` (`cameras.py:38`) calls `QApplication.processEvents()`.
* When the acquisition workflow completes (or is cancelled), a signal is emit which triggers `Application::acquisition_complete()` (`stroboPY.py:796`) which returns the GUI to an idle state.

**Misc.**

* `Application::acquisition_slider_changed()` (`stroboPY.py:806`) is triggered when the time delay slider near the acquisition plot widgets is moved. This recalculates and updates the average image shown in the top-right plot widget for the selected time delay.
* No images or other information is currently written to file during the acquisition workflow.

#### Sepia2

The control of the Sepia2 is managed by the methods found within `stroboPY.py`, which are triggered by changes to the GUI. Each of these methods synchronises the GUI to the other (acquisition/diagnostics) tab and passes changed information to the Sepia2.

* `set_baseosctrigger()`
* `set_divider()`
* `set_pulsesbursts()`
* `set_delay_diagnostics()`
* `set_delay()`
* `set_miscellaneous()`
* `set_outenabled()`
* `set_intensity_pump()`
* `set_intensity_probe()`
* `set_pulsed_pump()`
* `set_pulsed_probe()`

In particular `set_delay()` is triggered by the background thread during the acquisition workflow.
This is assumed to be thread-safe, as the GUI is locked during the acquisition workflow, ensuring nothing else will trigger the Sepia2.

The file `Sepia2.py` provides a wrapper for the PQLaserDrv API methods relevant to the Sepia2 modules in use. This has been tested thoroughly whilst developing the GUI therefore, except for those noted in the source (see `@note`), all methods should work as intended.

#### Andor

The classes `AndorCamera` (`cameras.py:74`) and `MockAndorCamera` (`cameras.py:161`) are intended to share the same interface, with the mock variant producing synthetic images. If the workflow is updated, `MockAndorCamera` may require changes to it's behaviour.

#### Licenses

The implementation of `Sepia2.py` relies on source code provided with the PQLaserDrv samples, which does not have a license attached so should not be published.
This is a minor dependency, corresponding to enumerations for buffer lengths and error codes, it should be possible to replace all enums with integer literals.
