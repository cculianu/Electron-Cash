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

from PyQt5.QtWidgets import QLayout, QWidget, QLayoutItem
from PyQt5.QtCore import Qt, QSize, QRect, QPoint

class FixedAspectRatioLayout(QLayout):
    def __init__(self, parent: QWidget = None, aspect_ratio: float = 1.0):
        super().__init__(parent)
        self.aspect_ratio = aspect_ratio
        self.items = []

    def setAspectRatio(self, aspect_ratio: float = 1.0):
        self.aspect_ratio = aspect_ratio
        self.update()

    def addItem(self, item: QLayoutItem):
        self.items.append(item)

    def count(self) -> int:
        return len(self.items)

    def itemAt(self, index: int) -> QLayoutItem:
        if index >= len(self.items):
            return None
        return self.items[index]

    def takeAt(self, index: int) -> QLayoutItem:
        if index >= len(self.items):
            return None
        return self.items.pop(index)

    def _getContentsMarginsSize(self) -> QSize:
        margins = self.getContentsMargins()
        return QSize(margins[0] + margins[2], margins[1] + margins[3])

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        if len(self.items) == 0:
            return

        content_size = rect.size() - self._getContentsMarginsSize()
        content_aspect_ratio = content_size.width() / content_size.height()
        item_rect = QRect(QPoint(0, 0), QSize(
            content_size.width() if content_aspect_ratio < self.aspect_ratio else content_size.height() * self.aspect_ratio,
            content_size.height() if content_aspect_ratio > self.aspect_ratio else content_size.width() / self.aspect_ratio
        ))

        content_margins = self.getContentsMargins()
        free_space = content_size - item_rect.size()

        if free_space.width() > 0:
            if self.items[0].alignment() & Qt.AlignLeft:
                item_rect.moveLeft(content_margins[1])
            elif self.items[0].alignment() & Qt.AlignRight:
                item_rect.moveRight(content_size.width() + content_margins[3])
            else:
                item_rect.moveLeft(content_margins[1] + (free_space.width() / 2))

        if free_space.height() > 0:
            if self.items[0].alignment() & Qt.AlignTop:
                item_rect.moveTop(content_margins[0])
            elif self.items[0].alignment() & Qt.AlignBottom:
                item_rect.moveBottom(content_size.height() + content_margins[2])
            else:
                item_rect.moveTop(content_margins[0] + (free_space.height() / 2))

        for item in self.items:
            item.widget().setGeometry(item_rect)

    def sizeHint(self) -> QSize:
        if len(self.items) == 0:
            return self._getContentsMarginsSize()
        # FIXME: Calculate proper sizeHint
        return self._getContentsMarginsSize() + self.items[0].sizeHint()

    def minimumSize(self) -> QSize:
        if len(self.items) == 0:
            return self._getContentsMarginsSize()
        # FIXME: Calculate proper minimumSize
        return self._getContentsMarginsSize() + self.items[0].minimumSize()

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Horizontal | Qt.Vertical
