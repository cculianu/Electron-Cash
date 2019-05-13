#!/usr/bin/env python3
#
# Electron Cash - lightweight Bitcoin client
# Copyright (C) 2019 Axel Gembe <derago@gmail.com>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
from typing import List

from PyQt5.QtMultimedia import QCameraInfo, QCamera, QCameraViewfinderSettings
from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QSize, QRect, Qt

from electroncash.i18n import _
from electroncash.util import print_error, PrintError
from electroncash.qrreaders import get_qr_reader

from electroncash_gui.qt.utils import FixedAspectRatioLayout

from .video_widget import QrReaderVideoWidget
from .video_surface import QrReaderVideoSurface
from .crop_blur_effect import QrReaderCropBlurEffect

class QrReaderCameraDialog(PrintError, QDialog):
    # Try to crop so we have minimum 512 dimensions
    SCAN_SIZE = 512

    # Try to QR scan every QR_SCAN_MODULO frames
    QR_SCAN_MODULO = 2

    def __init__(self, parent):
        QDialog.__init__(self, parent=parent)

        # Try to get the QR reader for this system
        self.qrreader = get_qr_reader()
        if self.qrreader is None:
            raise RuntimeError(_("Cannot start QR scanner, not available."))

        # Set up the window
        flags = self.windowFlags()
        flags = flags | Qt.WindowMaximizeButtonHint
        self.setWindowFlags(flags)
        self.setWindowTitle(_("Scan QR Code"))

        # Create video widget and fixed aspect ratio layout to contain it
        self.video_widget = QrReaderVideoWidget()
        self.video_widget_layout = FixedAspectRatioLayout()
        self.video_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.video_widget_layout.addWidget(self.video_widget)

        # Create root layout and add the video widget layout to it
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vbox)
        vbox.addLayout(self.video_widget_layout)

        # Create the video surface and receive events when new frames arrive
        self.video_surface = QrReaderVideoSurface()
        self.video_surface.frame_available.connect(self.on_frame_available)

    @staticmethod
    def _get_resolution(resolutions: List[QSize], min_size: int) -> QSize:
        """
        Given a list of resolutions that the camera supports this function picks the
        lowest resolution that is at least min_size in both width and height.
        If no resolution is found, a RuntimeError is raised.
        """
        def res_list_to_str(res_list: List[QSize]) -> str:
            return ', '.join(['{}x{}'.format(r.width(), r.height()) for r in res_list])

        def check_res(res: QSize):
            return res.width() >= min_size and res.height() >= min_size

        print_error(_('QR code scanner searching for at least {0}x{0}').format(min_size))

        # Query and display all resolutions the camera supports
        format_str = _('QR code scanner camera resolutions: {}')
        print_error(format_str.format(res_list_to_str(resolutions)))

        # Filter to those that are at least min_size in both width and height
        usable_resolutions = [r for r in resolutions if check_res(r)]
        format_str = _('QR code scanner usable resolutions: {}')
        print_error(format_str.format(res_list_to_str(usable_resolutions)))

        # Raise an error if we have no usable resolutions
        if len(usable_resolutions) < 1:
            raise RuntimeError(_("Cannot start QR scanner, no usable camera resolution found."))

        # Sort the usable resolutions, least number of pixels first, get the first element
        resolution = sorted(usable_resolutions, key=lambda r: r.width() * r.height())[0]
        format_str = _('QR code scanner chosen resolution is {}x{}')
        print_error(format_str.format(resolution.width(), resolution.height()))

        return resolution

    @staticmethod
    def _get_crop(resolution: QSize, scan_size: int) -> QRect:
        """
        Returns a QRect that is scan_size x scan_size in the middle of the resolution
        """
        x = (resolution.width() - scan_size) / 2
        y = (resolution.height() - scan_size) / 2
        return QRect(x, y, scan_size, scan_size)

    def scan(self, device='') -> str:
        """
        Scans a QR code from the given camera device.
        If no QR code is found the returned string will be empty.
        If the camera is not found or can't be opened a RuntimeError will be raised.
        """
        device_info = None

        for camera in QCameraInfo.availableCameras():
            if camera.deviceName() == device:
                device_info = camera
                break

        if not device_info:
            print_error(_('Failed to open selected camera, trying to use default camera'))
            device_info = QCameraInfo.defaultCamera()

        if not device_info or device_info.isNull():
            raise RuntimeError(_("Cannot start QR scanner, no usable camera found."))

        self.init_stats()

        camera = QCamera(device_info)
        camera.setViewfinder(self.video_surface)
        camera.setCaptureMode(QCamera.CaptureViewfinder)

        # Camera needs to be loaded to query resolutions, this tries to open the camera
        camera.load()
        if camera.status() != QCamera.LoadedStatus:
            raise RuntimeError(_("Cannot start QR scanner, camera is unavailable."))

        # Determine the optimal resolution and compute the crop rect
        camera_resolutions = camera.supportedViewfinderResolutions()
        resolution = self.__class__._get_resolution(camera_resolutions, self.SCAN_SIZE)
        self.qr_crop = self.__class__._get_crop(resolution, self.SCAN_SIZE)

        # Initialize the video widget
        self.video_widget.setMinimumSize(resolution)
        self.video_widget.setGraphicsEffect(QrReaderCropBlurEffect(self, resolution, self.qr_crop))
        self.video_widget_layout.setAspectRatio(resolution.width() / resolution.height())

        # Set the camera resolution
        viewfinder_settings = QCameraViewfinderSettings()
        viewfinder_settings.setResolution(resolution)
        camera.setViewfinderSettings(viewfinder_settings)

        # Counter for the QR scanner frame number
        self.frame_id = 0

        camera.start()

        self.exec()

        camera.stop()

        self.video_widget.setGraphicsEffect(None)
        self.effect = None

        print_error(_('QR code scanner closed'))

        return ''

    def on_frame_available(self, frame: QImage):
        #self.print_error("Image {}x{}, pixelRatio={}".format(frame.width(), frame.height(), frame.devicePixelRatio()))

        self.frame_id += 1

        # Only QR scan every QR_SCAN_MODULO frames
        qr_scanned = self.frame_id % self.QR_SCAN_MODULO == 0
        if qr_scanned:
            # Crop the frame so we only scan a SCAN_SIZE rect
            frame_cropped = frame.copy(self.qr_crop)

            # Convert to Y800 / GREY FourCC (single 8-bit channel)
            # This creates a copy, so we don't need to keep the frame around anymore
            frame_y800 = frame_cropped.convertToFormat(QImage.Format_Grayscale8)

            qrreader_res = self.qrreader.read_qr_code(frame_y800.constBits().__int__(), frame_y800.byteCount(),
                frame_y800.width(), frame_y800.height(), self.frame_id)

            #format_str = _('QR code scanner found {} symbol(s): {}')
            #print_error(format_str.format(len(qrreader_res), ', '.join([str(r) for r in qrreader_res])))

            self.video_widget.setResults(qrreader_res)

        # Display the frame in the widget
        self.video_widget.setPixmap(QPixmap.fromImage(frame))

        self.update_stats(qr_scanned)

    def init_stats(self):
        self.last_stats_time = time.perf_counter()
        self.frame_counter = 0
        self.qr_frame_counter = 0

    def update_stats(self, qr_scanned):
        self.frame_counter += 1
        if qr_scanned:
            self.qr_frame_counter += 1
        now = time.perf_counter()
        last_stats_delta = now - self.last_stats_time
        if last_stats_delta > 5.0:
            fps = self.frame_counter / last_stats_delta
            qr_fps = self.qr_frame_counter / last_stats_delta
            print_error(_('QR code display running at {} FPS, scanner at {} FPS').format(fps, qr_fps))
            self.frame_counter = 0
            self.qr_frame_counter = 0
            self.last_stats_time = now
