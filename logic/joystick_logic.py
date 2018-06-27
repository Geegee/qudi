# -*- coding: utf-8 -*-

"""
A module for reading a joystick controller via joystick itnerface.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

from core.module import Connector, ConfigOption
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from qtpy import QtCore


class JoystickLogic(GenericLogic):
    """
    Control a camera.
    """
    _modclass = 'cameralogic'
    _modtype = 'logic'

    # declare connectors
    hardware = Connector(interface='JoystickInterface')
    _hardware = None

    _max_fps = ConfigOption('default_exposure', 100)
    _fps = _max_fps

    # signals
    sig_controller_changed = QtCore.Signal()
    sig_new_frame = QtCore.Signal()

    timer = None
    enabled = False

    _last_state = None

    _button_list = ['left_up', 'left_down', 'left_left', 'left_right', 'left_joystick',
               'right_up', 'right_down', 'right_left', 'right_right', 'right_joystick',
               'middle_left', 'middle_right', 'left_shoulder', 'right_shoulder']

    _axis_list = ['left_vertical', 'left_horizontal', 'right_vertical', 'right_horizontal',
                  'left_trigger', 'right_trigger']

    events = None

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.threadlock = Mutex()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._hardware = self.hardware()

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.loop)

        for button in self._button_list:
            self.events[button] = {
                'pressed': QtCore.Signal(),
                'value_change': QtCore.Signal()
            }

        for axis in self._axis_list:
            self.events[axis] = {
                'value_change': QtCore.Signal()
            }

        self._last_state = self._hardware.get_state()

        self.start_loop()

    def on_deactivate(self):
        """ Perform required deactivation. """
        self.stop_loop()
        pass

    def fps(self, value=None):
        """ Set  ou get the frequency at which the hardware is read """
        if value is not None:
            self._fps = value
        return self._fps

    def start_loop(self):
        """ Start the running loop.
        """
        self.enabled = True
        self.timer.start(1000*1/self._fps)

    def stop_loop(self):
        """ Stop the data recording loop.
        """
        self.timer.stop()
        self.enabled = False

    def loop(self):
        """ Loop function of the module. Get state and emit event
        """
        old_state = self._last_state
        state = self._hardware.get_state()
        changed = False

        if not self.enabled:
            return

        for button in self._button_list:
            if state[button] != old_state[button]:
                changed = True
                self._events[button]['value_change'].emit()
                if state[button]:
                    self._events[button]['pressed'].emit()

        for axis in self._axis_list:
            if state[axis] != old_state[axis]:
                changed = True
                self._events[axis]['value_change'].emit()

        if changed:
            self.sig_controller_changed.emit()

        self.timer.start(1000 * 1 / self._fps)

    def get_last_state(self):
        """ Return last acquired state """
        return self._last_state
