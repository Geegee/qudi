# -*- coding: utf-8 -*-
"""
This module contains a GUI for operating the spectrometer camera logic module.
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

import os
import pyqtgraph as pg

from core.module import Connector
from gui.colordefs import QudiPalettePale as Palette
from gui.guibase import GUIBase

from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from qtpy import uic

from core.module import Connector, ConfigOption, StatusVar
from gui.colordefs import QudiPalettePale as palette
import numpy as np

class CrossROI(pg.ROI):

    """ Create a Region of interest, which is a zoomable rectangular.

    @param float pos: optional parameter to set the position
    @param float size: optional parameter to set the size of the ROI

    Have a look at:
    http://www.pyqtgraph.org/documentation/graphicsItems/roi.html
    """
    sigUserRegionUpdate = QtCore.Signal(object)
    sigMachineRegionUpdate = QtCore.Signal(object)

    def __init__(self, pos, size, **args):
        """Create a ROI with a central handle."""
        self.userDrag = False
        pg.ROI.__init__(self, pos, size, **args)
        # That is a relative position of the small box inside the region of
        # interest, where 0 is the lowest value and 1 is the higherst:
        center = [0.5, 0.5]
        # Translate the center to the intersection point of the crosshair.
        self.addTranslateHandle(center)

        self.sigRegionChangeStarted.connect(self.startUserDrag)
        self.sigRegionChangeFinished.connect(self.stopUserDrag)
        self.sigRegionChanged.connect(self.regionUpdateInfo)

    def setPos(self, pos, update=True, finish=False):
        """Sets the position of the ROI.

        @param bool update: whether to update the display for this call of setPos
        @param bool finish: whether to emit sigRegionChangeFinished

        Changed finish from parent class implementation to not disrupt user dragging detection.
        """
        super().setPos(pos, update=update, finish=finish)

    def setSize(self,size, update=True,finish=True):
        """
        Sets the size of the ROI
        @param bool update: whether to update the display for this call of setPos
        @param bool finish: whether to emit sigRegionChangeFinished
        """
        super().setSize(size,update=update,finish=finish)

    def handleMoveStarted(self):
        """ Handles should always be moved by user."""
        super().handleMoveStarted()
        self.userDrag = True

    def startUserDrag(self, roi):
        """ROI has started being dragged by user."""
        self.userDrag = True

    def stopUserDrag(self, roi):
        """ROI has stopped being dragged by user"""
        self.userDrag = False

    def regionUpdateInfo(self, roi):
        """When the region is being dragged by the user, emit the corresponding signal."""
        if self.userDrag:
            self.sigUserRegionUpdate.emit(roi)
        else:
            self.sigMachineRegionUpdate.emit(roi)




class CrossLine(pg.InfiniteLine):

    """ Construct one line for the Crosshair in the plot.

    @param float pos: optional parameter to set the position
    @param float angle: optional parameter to set the angle of the line
    @param dict pen: Configure the pen.

    For additional options consider the documentation of pyqtgraph.InfiniteLine
    """

    def __init__(self, **args):
        pg.InfiniteLine.__init__(self, **args)
#        self.setPen(QtGui.QPen(QtGui.QColor(255, 0, 255),0.5))

    def adjust(self, extroi):
        """
        Run this function to adjust the position of the Crosshair-Line

        @param object extroi: external roi object from pyqtgraph
        """
        if self.angle == 0:
            self.setValue(extroi.pos()[1] + extroi.size()[1] * 0.5)
        if self.angle == 90:
            self.setValue(extroi.pos()[0] + extroi.size()[0] * 0.5)



class CameraWindow(QtWidgets.QMainWindow):
    """ Class defined for the main window (not the module)
    """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_camera.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class CameraGUI(GUIBase):
    """ Main spectrometer camera class.
    """
    _modclass = 'CameraGui'
    _modtype = 'gui'

    camera_logic = Connector(interface='CameraLogic')

    sigStart = QtCore.Signal()
    sigStop = QtCore.Signal()
    _image = []
    _logic = None
    _mw = None

    _exposure = None
    _gain = None
    _mask = None

    ## Value that need to be connected to the config

    # size of 1 pixel, x and y
    _pixel_size_x = ConfigOption('pixel_size_x',1)
    _pixel_size_y = ConfigOption('pixel_size_y', 1)



    _raw_data_image=np.eye(1000)
    _image_size= (1000,1000) ## care x/ y inversed


    def __init__(self, config, **kwargs):

        # load connection
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Initializes all needed UI files and establishes the connectors.
        """

        self._logic = self.camera_logic()




        # Windows
        self._mw = CameraWindow()
        self._mw.centralwidget.hide()
        self._mw.setDockNestingEnabled(True)

        self._mw.start_control_Action.setEnabled(True)
        self._mw.start_control_Action.setChecked(self._logic.enabled)
        self._mw.start_control_Action.triggered.connect(self.start_clicked)
        self._mw.image_meter_control_dockwidget.hide() #The meter control is initially turned off

        self._logic.sigUpdateDisplay.connect(self.update_data)

        # starting the physical measurement
        self.sigStart.connect(self._logic.startLoop)
        self.sigStop.connect(self._logic.stopLoop)

        self._mw.expos_current_InputWidget.editingFinished.connect(self.update_from_input_exposure)
        self._mw.gain_current_InputWidget.editingFinished.connect(self.update_from_input_gain)







        # Show the image measured
        self._image = pg.ImageItem(image=self._raw_data_image, axisOrder='row-major')
        self._mw.image_PlotWidget.addItem(self._image)


        # Label the axis

        x_axis=self._mw.image_PlotWidget.getAxis('bottom')
        x_axis.setLabel('X position', units="Pixels")
        x_axis.setScale(1)


        y_axis = self._mw.image_PlotWidget.getAxis('left')
        y_axis.setLabel('Y position', units="Pixels")
        y_axis.setScale(1)


        self._mw.image_PlotWidget.setAspectLocked(True)


        #  Initialisation of the exposure/ gain indicators
        self._exposure=self._logic.get_exposure()
        self._mw.expos_current_InputWidget.setValue(self._exposure)

        self._gain = self._logic.get_gain()
        self._mw.gain_current_InputWidget.setValue(self._gain)

        # Creates the crosshair

        self.createCrosshair()



        # Updates the intensity value
        self.update_intensity()

        # Allows meter mode

        self._mw.actionPhysical_position.changed.connect(self.update_units)





    def createCrosshair(self):

        ## Test to be sure that there is an image
        if self._image == None:

            return

        # Create Region of Interest for xy image and add to xy Image Widget:
        self.roi_xy = CrossROI(
            [
                5 ,
                5
            ],
            [1, 1],
            pen={'color': "F0F", 'width': 1},
            removable=True
        )

        self._mw.image_PlotWidget.addItem(self.roi_xy)

        # create horizontal and vertical line as a crosshair in xy image:
        self.hline_xy = CrossLine(pos=self.roi_xy.pos() + self.roi_xy.size() * 0.5,
                                  angle=0, pen={'color': palette.green, 'width': 1})
        self.vline_xy = CrossLine(pos=self.roi_xy.pos() + self.roi_xy.size() * 0.5,
                                  angle=90, pen={'color': palette.green, 'width': 1})

        # connect the change of a region with the adjustment of the crosshair:
        self.roi_xy.sigRegionChanged.connect(self.hline_xy.adjust)
        self.roi_xy.sigRegionChanged.connect(self.vline_xy.adjust)
        self.roi_xy.sigUserRegionUpdate.connect(self.update_from_roi_xy)
        self.roi_xy.sigRegionChangeFinished.connect(self.roi_xy_bounds_check)


        # # Update the inputed/displayed numbers :
        self._mw.x_current_InputWidget_pixels.editingFinished.connect(self.update_from_input_x)
        self._mw.y_current_InputWidget_pixels.editingFinished.connect(self.update_from_input_y)

        self._mw.x_current_InputWidget_meter.editingFinished.connect(self.update_from_input_x_meter)
        self._mw.y_current_InputWidget_meter.editingFinished.connect(self.update_from_input_y_meter)

        self._mw.cursor_x_size_input.editingFinished.connect(self.update_from_input_xy_size)
        self._mw.cursor_y_size_input.editingFinished.connect(self.update_from_input_xy_size)



        self._mw.x_current_InputWidget_pixels.setRange(0,self._image_size[0])
        self._mw.y_current_InputWidget_pixels.setRange(0,self._image_size[1])

        self._mw.x_current_InputWidget_meter.setRange(0,self._image_size[0]*self._pixel_size_x)
        self._mw.y_current_InputWidget_meter.setRange(0,self._image_size[1]*self._pixel_size_y)




        # adds the configured crosshair to the xy Widget
        self._mw.image_PlotWidget.addItem(self.hline_xy)
        self._mw.image_PlotWidget.addItem(self.vline_xy)

        # shows the initial position in the indicators
        self._mw.x_current_InputWidget_pixels.setValue(self.roi_xy.pos()[0])
        self._mw.y_current_InputWidget_pixels.setValue(self.roi_xy.pos()[1])


        self._mw.x_current_InputWidget_meter.setValue(self.roi_xy.pos()[0]*self._pixel_size_x)
        self._mw.y_current_InputWidget_meter.setValue(self.roi_xy.pos()[1]*self._pixel_size_y)

        self._mw.cursor_x_size_input.setValue(self.roi_xy.size()[0])
        self._mw.cursor_y_size_input.setValue(self.roi_xy.size()[1])



    def update_from_roi_xy(self, roi):
        """The user manually moved the XY ROI, adjust all other GUI elements accordingly

        @params object roi: PyQtGraph ROI object
        """
        h_pos = roi.pos()[0] + 0.5 * roi.size()[0]
        v_pos = roi.pos()[1] + 0.5 * roi.size()[1]

        self.update_input_x(h_pos)
        self.update_input_y(v_pos)

        ## Adjust measured intensity
        self.update_intensity()



    def roi_xy_bounds_check(self, roi):
        """ Check if the focus cursor is oputside the allowed range after drag
            and set its position to the limit
        """
        h_pos = roi.pos()[0] + 0.5 * roi.size()[0]
        v_pos = roi.pos()[1] + 0.5 * roi.size()[1]

        new_h_pos=h_pos
        new_v_pos=v_pos

        max_h_pos=self._image_size[0]
        max_v_pos =self._image_size[1]

        if h_pos > max_h_pos:
            new_h_pos=max_h_pos

        if h_pos < 0:
            new_h_pos=0

        if v_pos > max_v_pos:
            new_v_pos = max_v_pos

        if v_pos < 0:
            new_v_pos = 0


        self.update_roi_xy(new_h_pos, new_v_pos)

    def update_from_input_x(self):
        """ The user changed the number in the x pixel position spin box, adjust all
            other GUI elements."""


        x_pos = self._mw.x_current_InputWidget_pixels.value()

        self.update_roi_xy(h=x_pos)
        self._mw.x_current_InputWidget_meter.setValue(x_pos*self._pixel_size_x)

    def update_from_input_x_meter(self):
        """ The user changed the number in the x meter position  spin box, adjust all
            other GUI elements."""


        x_pos = self._mw.x_current_InputWidget_meter.value()/self._pixel_size_x

        self.update_roi_xy(h=x_pos)
        self._mw.x_current_InputWidget_pixels.setValue(x_pos)

    def update_input_x(self, x_pos):
        """ Update the displayed x-value, in pixels and meters.

        @param float x_pos: the current value of the x position in pixels
        """


        self._mw.x_current_InputWidget_pixels.setValue(x_pos)
        self._mw.x_current_InputWidget_meter.setValue(x_pos*self._pixel_size_x)


    def update_from_input_y(self):
        """ The user changed the number in the y pixel position spin box, adjust all
            other GUI elements."""


        y_pos = self._mw.y_current_InputWidget_pixels.value()

        self.update_roi_xy(v=y_pos)
        self._mw.y_current_InputWidget_meter.setValue(y_pos*self._pixel_size_y)

    def update_from_input_y_meter(self):
        """ The user changed the number in the y meter position spin box, adjust all
            other GUI elements."""


        y_pos_meter = self._mw.y_current_InputWidget_meter.value()

        self.update_roi_xy(v=y_pos_meter/self._pixel_size_y)
        self._mw.y_current_InputWidget_pixels.setValue(y_pos_meter/self._pixel_size_y)


    def update_input_y(self, y_pos):
        """ Update the displayed y-value, in pixel and meters.

        @param float y_pos: the current value of the y position in pixels
        """



        self._mw.y_current_InputWidget_pixels.setValue(y_pos)
        self._mw.y_current_InputWidget_meter.setValue(y_pos*self._pixel_size_y)

    def update_from_key(self, x=None, y=None):
        """The user pressed a key to move the crosshair, adjust all GUI elements.

        @param float x: new x position in pixels
        @param float y: new y position in pixels

        """
        if x is not None:
            self.update_roi_xy(h=x)

            self.update_input_x(x)

        if y is not None:
            self.update_roi_xy(v=y)

            self.update_input_y(y)

        self.update_intensity()
    def update_roi_xy(self, h=None, v=None):
        """ Adjust the xy ROI position if the value has changed.

        @param float x: real value of the current x position
        @param float y: real value of the current y position

        Since the origin of the region of interest (ROI) is not the crosshair
        point but the lowest left point of the square, you have to shift the
        origin according to that. Therefore the position of the ROI is not
        the actual position!
        """
        roi_h_view = self.roi_xy.pos()[0]
        roi_v_view = self.roi_xy.pos()[1]

        if h is not None:
            roi_h_view = h - self.roi_xy.size()[0] * 0.5
        if v is not None:
            roi_v_view = v - self.roi_xy.size()[1] * 0.5

        self.roi_xy.setPos([roi_h_view, roi_v_view])
        self.update_intensity()

    def update_input_exposure(self, _exposure):
        """ Updates the displayed exposure.

        @param float _exposure: the current value of the exposure
        """
        # Change the exposure in the associated widget:
        self._mw.expos_current_InputWidget.setValue(_exposure)

    def update_from_input_exposure(self):
        """ If the user changes the exposition time in the box, adjusts the corresponding hardware parameter"""

        exposure = self._mw.expos_current_InputWidget.value()
        self._exposure=exposure
        self._logic.set_exposure(exposure)
        self.update_intensity()

    def update_input_gain(self, _gain):
        """ Updates the displayed gain.

         @param float _gain: the current value of the gain
         """
        # Change the gain in the associated widget:
        self._mw.gain_current_InputWidget.setValue(_gain)

    def update_from_input_gain(self):
        """ If the user changes the gain in the box, adjusts the corresponding hardware parameter"""

        gain = self._mw.gain_current_InputWidget.value()
        self._gain = gain
        self._logic.set_gain(gain)
        self.update_intensity()

    def create_mask_ROI(self,image):
        """ Creates a mask corresponding to the ROI"""


        # Creates the base of the mask, with the same size as the image, with zeros.
        mask=image*0

        h_bounds=[int(self.roi_xy.pos()[0] - self.roi_xy.size()[0]/2), int(self.roi_xy.pos()[0] + self.roi_xy.size()[0]/2)+1]
        v_bounds=[int(self.roi_xy.pos()[1] - self.roi_xy.size()[1]/2), int(self.roi_xy.pos()[1] + self.roi_xy.size()[1]/2)+1]

        # Correction if the ROI comes out of the image, but can give wrong results if the ROI comes out (this part mostly means to avoid errors)

        if self.roi_xy.pos()[0]+self.roi_xy.size()[0]>=self._image_size[0] :
            h_bounds[1]=self._image_size[0]


        if self.roi_xy.pos()[1]+self.roi_xy.size()[1]>=self._image_size[1] :
            v_bounds[1]=self._image_size[1]


        if self.roi_xy.pos()[0] - self.roi_xy.size()[0] <= 0:
            h_bounds[0] = 0


        if self.roi_xy.pos()[1] - self.roi_xy.size()[1] <= 0:
            v_bounds[0] = 0

        for h in range(h_bounds[0],h_bounds[1]):
            for v in range(v_bounds[0],v_bounds[1]):

             mask[v][h]=1

        return(mask)

    def update_intensity(self):
        """ Returns the intensity mean in the ROI"""

        ## Here we assume that we have a logic module, that take two np array in entry, the image and the mask,
        ## applies the mask on the image, and returns the mean of the pixels of the masked image
        ## This module has to be implemented, and we set the intensity value as the sum of the pixels direct value.

        # Test to be sure that there is an image
        # if self._image == None :
        #
        #     self._mw.intensity_current.setValue(0)
        #     return


        mask=self.create_mask_ROI(self._raw_data_image)

        intensity_test=np.sum(mask*self._raw_data_image)/(self.roi_xy.size()[0]*self.roi_xy.size()[1]) ## Needs to be replaced by the logic module

        self._mw.intensity_current.setValue(intensity_test)


    def update_from_input_xy_size(self):
        """ The user changes the input size of the cursor """

        x_size = self._mw.cursor_x_size_input.value()
        y_size = self._mw.cursor_y_size_input.value()

        self.roi_xy.setSize(size=[x_size,y_size])
        self.update_intensity()

    def update_input_x_size(self, x_size):
        """ Updates the displayed cursor x size.

        @param float x_size: the current value of the x size in pixels
        """
        self._mw.cursor_x_size_input.setValue(x_size)
        self.update_intensity()

    def update_input_y_size(self, y_size):
        """ Updates the displayed cursor y size.

        @param float y_size: the current value of the y size in pixels
        """
        self._mw.cursor_y_size_input.setValue(y_size)
        self.update_intensity()


    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self._mw.close()

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()


    def start_clicked(self):
        """ Handling the Start button to stop and restart the counter.
        """




        if self._logic.enabled:
            self._raw_data_image = self._logic.get_last_image()


            self._mw.start_control_Action.setText('Start')
            self.sigStop.emit()



        else:



            self._mw.start_control_Action.setText('Stop')
            self.sigStart.emit()

    def update_data(self):
        """
        Get the image data from the logic and print it on the window
        """

        self._raw_data_image = self._logic.get_last_image()
        self._image_size = (np.shape(self._raw_data_image)[1],np.shape(self._raw_data_image)[0])
        self.update_intensity()

        levels = (0., 1.)
        # The maximum intensity measurable is the number of pixels in the ROI time the maximum intensity value, set by the levels

        #self._mw.intensity_current.setRange(0, self.roi_xy.size()[0] * self.roi_xy.size()[1]*levels[1])
        self._mw.intensity_current.setRange(0, self.roi_xy.size()[0] * self.roi_xy.size()[1] * np.amax(self._raw_data_image))
        self._image.setImage(image=self._raw_data_image)
        #self._image.setImage(image=self._raw_data_image, levels=levels)

    def updateView(self):
        """
        Update the view when the model change
        """
        pass


    def update_units(self):
        """
        Update the units on the graph, and the view of the meter control windows, depending of the activation of the meter mode.
        """

        # Checks the activation of the mode

        meter_state = self._mw.actionPhysical_position.isChecked()

        if meter_state:

            # Changes axis label and scale
            x_axis = self._mw.image_PlotWidget.getAxis('bottom')
            x_axis.setLabel('X position', units="Meter")
            x_axis.setScale(self._pixel_size_x)

            y_axis = self._mw.image_PlotWidget.getAxis('left')
            y_axis.setLabel('Y position', units="Meter")
            y_axis.setScale(self._pixel_size_y)

            # Shows the meter control window
            self._mw.image_meter_control_dockwidget.show()



        else:

            # Changes axis label and scale

            x_axis = self._mw.image_PlotWidget.getAxis('bottom')
            x_axis.setLabel('X position', units="Pixel")
            x_axis.setScale(1)

            y_axis = self._mw.image_PlotWidget.getAxis('left')
            y_axis.setLabel('Y position', units="Pixel")
            y_axis.setScale(1)

            # Hides the meter control window
            self._mw.image_meter_control_dockwidget.hide()


