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

from typing import List, Dict
from abc import ABC, abstractmethod

from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

from electroncash.i18n import _
from electroncash.qrreaders import QrCodeResult

from electroncash_gui.qt.utils import QColorLerp
from electroncash_gui.qt.util import ColorScheme

class QrReaderValidatorResult():
    accepted: bool = False
    message: str = None
    message_color: QColor = None
    result_colors: Dict[QrCodeResult, QColor] = {}

class AbstractQrReaderValidator(ABC):
    """
    Abstract base class for QR code result validators.
    """

    @abstractmethod
    def validate_results(self, results: List[QrCodeResult]) -> QrReaderValidatorResult:
        """
        Checks a list of QR code results for usable codes.
        """

class QrReaderValidatorSingle(AbstractQrReaderValidator):
    WEAK_COLOR: QColor = QColor(Qt.red)
    STRONG_COLOR: QColor = QColor(Qt.green)
    STRONG_COUNT: int = 10

    _result_counts: Dict[QrCodeResult, int] = {}

    def validate_results(self, results: List[QrCodeResult]) -> QrReaderValidatorResult:
        res = QrReaderValidatorResult()

        for result in results:
            if not result in self._result_counts:
                self._result_counts[result] = 0
            self._result_counts[result] += 1
            lerp_factor = (self._result_counts[result] - 1) / self.STRONG_COUNT
            res.result_colors[result] = QColorLerp(
                self.WEAK_COLOR, self.STRONG_COLOR, lerp_factor)

        # Search for missing results, iterate over a copy because the loop might modify the dict
        for result in self._result_counts.copy():
            # Count down missing results
            if result in results:
                continue
            self._result_counts[result] -= 2
            # When the count goes to zero, remove
            if self._result_counts[result] < 1:
                del self._result_counts[result]

        if len(results) == 1:
            pass
            #res.accepted = True
        elif len(results) > 1:
            res.message = _('More than one QR code detected.')
            res.message_color = ColorScheme.RED.as_color()

        return res
