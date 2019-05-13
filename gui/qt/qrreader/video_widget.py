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

from typing import List

from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPixmap, QPainter, QPaintEvent, QPen, QPainterPath, QColor
from PyQt5.QtCore import QRectF, Qt

from electroncash.qrreaders import QrCodeResult
from electroncash.util import PrintError

class QrReaderVideoWidget(PrintError, QWidget):
    """
    Simple widget for drawing a pixmap
    """

    USE_BILINEAR_FILTER = True

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.pixmap = None

        self.qr_outline_pen = QPen()
        self.qr_outline_pen.setColor(Qt.red)
        self.qr_outline_pen.setWidth(3)
        self.qr_outline_pen.setStyle(Qt.DotLine)
        #self.qr_outline_pen.setDashOffset(4)

        self.text_pen = QPen()
        self.text_pen.setColor(Qt.black)

        self.bg_box_pen = QPen()
        self.bg_box_pen.setColor(Qt.black)
        self.bg_box_pen.setStyle(Qt.DotLine)
        self.bg_box_fill = QColor(255, 255, 255, 192)

    def paintEvent(self, event: QPaintEvent):
        if not self.pixmap:
            return
        painter = QPainter(self)
        if self.USE_BILINEAR_FILTER:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self.pixmap, self.pixmap.rect())
        #self.print_error("PixMap {}x{}, pixelRatio={}, self.pixelRatio={}, self.size={}x{}".format(self.pixmap.width(), self.pixmap.height(), self.pixmap.devicePixelRatio(), self.devicePixelRatioF(), self.width(), self.height()))

    def setPixmap(self, pixmap: QPixmap):
        self.pixmap = pixmap
        self.update()

    def setResults(self, results: List[QrCodeResult]):
        self.results = results

    def drawOverlay(self):
        # Small helper for tuple to QPoint
        def toqp(point):
            return QPoint(point[0], point[1])

        # Starting from here we care about AA
        painter.setRenderHint(QPainter.Antialiasing)

        for res in self.results:
            painter.setPen(self.qr_outline_pen)

            num_points = len(res.points)
            for i in range(0, num_points):
                i_n = i + 1

                line_from = toqp(res.points[i])
                line_from += self.crop.topLeft()

                line_to = toqp(res.points[i_n] if i_n < num_points else res.points[0])
                line_to += self.crop.topLeft()

                # Put the offset into the world transform
                # transform = painter.worldTransform()
                # offset = self.crop.topLeft()
                # transform = transform.translate(offset.x(), offset.y())
                # painter.setWorldTransform(transform)

                painter.drawLine(line_from, line_to)

            # Draw the data
            font_metrics = painter.fontMetrics()
            data_metrics_x = font_metrics.horizontalAdvance(res.data)
            data_metrics_y = font_metrics.capHeight()

            center_pos = toqp(res.center)
            center_pos += self.crop.topLeft()

            text_offset = QPoint(-data_metrics_x / 2, data_metrics_y / 2)
            center_pos += text_offset

            bg_rect_padding = 5
            bg_rect_pos = center_pos - QPoint(bg_rect_padding, data_metrics_y + bg_rect_padding)
            bg_rect = QRect(bg_rect_pos, QSize(data_metrics_x + (bg_rect_padding * 2), data_metrics_y + (bg_rect_padding * 2)))
            bg_rect_path = QPainterPath()
            bg_rect_path.addRoundedRect(QRectF(bg_rect), 5.0, 5.0, Qt.RelativeSize)
            painter.setPen(self.bg_box_pen)
            painter.fillPath(bg_rect_path, self.bg_box_fill)
            painter.drawPath(bg_rect_path)

            painter.setPen(self.text_pen)
            painter.drawText(center_pos, res.data)
