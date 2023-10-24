#!/usr/bin/env python3
#
# Electron Cash - lightweight Bitcoin Cash client
# Copyright (C) 2023 The Electron Cash Developers
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
import os
from typing import List, Optional

from PyQt5.Qt import Qt, QMargins
from PyQt5.QtWidgets import QDialog, QGridLayout, QVBoxLayout, QLabel, QPushButton, QToolButton, QGroupBox

from electroncash import keystore
from electroncash.i18n import _
from electroncash.util import InvalidPassword
from electroncash.wallet import Multisig_Wallet, MultiXPubWallet
from electroncash_gui.qt.qrtextedit import ShowQRTextEdit
from electroncash_gui.qt.seed_dialog import KeysLayout
from electroncash_gui.qt.util import Buttons, CloseButton, WindowModalDialog, ColorScheme, ChoicesLayout, CancelButton


def show_wallet_information(main_window):
    """Shows the 'Wallet Information' popup dialog. This was refactored out of main_window.py to
    reduce line count in that file."""
    from .main_window import ElectrumWindow
    assert isinstance(main_window, ElectrumWindow)
    wallet = main_window.wallet
    dialog = WindowModalDialog(main_window.top_level_window(), _("Wallet Information"))
    dialog.setMinimumSize(500, 100)
    mpk_list: List[str] = wallet.get_master_public_keys()
    orig_mpk_list = mpk_list[:]
    vbox = QVBoxLayout()
    wallet_type = wallet.storage.get('wallet_type', '')
    grid = QGridLayout()
    basename = os.path.basename(wallet.storage.path)
    grid.addWidget(QLabel(_("Wallet name") + ':'), 0, 0)
    grid.addWidget(QLabel(basename), 0, 1)
    grid.addWidget(QLabel(_("Wallet type") + ':'), 1, 0)
    grid.addWidget(QLabel(wallet_type), 1, 1)
    grid.addWidget(QLabel(_("Script type") + ':'), 2, 0)
    grid.addWidget(QLabel(wallet.txin_type), 2, 1)
    vbox.addLayout(grid)
    bottom_buttons = Buttons(CloseButton(dialog))
    if wallet.is_deterministic():
        has_prvkey_ct = sum(ks.has_master_private_key() for ks in wallet.get_keystores()
                            if isinstance(ks, keystore.Xprv))
        mpk_text = ShowQRTextEdit()
        mpk_text.setMaximumHeight(150)
        mpk_text.addCopyButton()
        mpk_del_button: Optional[QPushButton] = None
        show_privkey_button: Optional[QToolButton] = None
        selected_index: Optional[int] = None
        title_lbl: Optional[QLabel] = None
        title_gb: Optional[QGroupBox] = None
        password: Optional[str] = None

        def mpk_selected(clayout, index):
            nonlocal selected_index
            selected_index = index
            mpk_text.setText(mpk_list[index])
            name = (clayout and clayout.group.checkedButton() and clayout.group.checkedButton().text()) or _("Key")
            if mpk_del_button:
                mpk_del_button.setText(_("Delete") + " " + name)
            if show_privkey_button:
                ks = wallet.get_keystores()[index]
                if not show_privkey_button.isChecked():
                    show_privkey_button.setEnabled(isinstance(ks, keystore.Xprv) and ks.has_master_private_key())
        # only show the combobox in case multiple accounts are available
        labels_clayout = None
        if len(mpk_list) > 1:
            def label(key):
                if isinstance(wallet, Multisig_Wallet):
                    return _("cosigner") + ' ' + str(key +1)
                elif isinstance(wallet, MultiXPubWallet):
                    return _("Key") + f" {key + 1}"
                return ''
            labels = [label(i) for i in range(len(mpk_list))]
            labels_clayout = ChoicesLayout(_("Master Public Keys"), labels, on_id_clicked=mpk_selected)
            title_gb = labels_clayout.group_box()
            vbox.addLayout(labels_clayout.layout())
        else:
            title_lbl = QLabel(_("Master Public Key"))
            vbox.addWidget(title_lbl)
        vbox.addWidget(mpk_text)

        # Support for deleting keys
        if wallet.can_delete_keystore() and labels_clayout:
            def on_click(checked):
                if selected_index is not None:
                    if main_window.wallet_delete_xpub(selected_index):
                        dialog.close()
            mpk_del_button = mpk_text.addButton(icon_name=None, on_click=on_click, index=0,
                                                tooltip=_("Delete this key from the wallet"),
                                                # This is tmp text for layout, gets set to real text by mpk_selected
                                                # above ...
                                                text="Delete Key 1")
            red = ColorScheme.RED.get_html(True)
            red_alt = ColorScheme.RED.get_html(False)
            mpk_del_button.setStyleSheet("QPushButton { border: 2px solid "
                                         + red + "; padding: 2px; border-radius: 2px; font-size: 11px; } " +
                                         "QPushButton:hover { border: 2px solid "
                                         + red_alt + "; padding: 2px; border-radius: 2px; font-size: 11px; } ")

        # Support for the "Add Key" button
        if wallet.can_add_keystore():
            add_but = QPushButton(_("Add Key..."))
            marg: QMargins = add_but.contentsMargins()
            marg.setLeft(marg.left() // 2)
            marg.setRight(marg.right() // 2)
            add_but.setContentsMargins(marg)
            bottom_buttons.insertWidget(0, add_but, Qt.AlignLeft)

            def on_click(checked):
                d = QDialog(parent=dialog)
                d.setWindowModality(Qt.WindowModal)
                d.setMinimumSize(400, 200)
                title = _("Add Master Key")
                d.setWindowTitle(title)
                message = '  '.join([
                    _("Enter an xpub or xprv key to add to this wallet."),
                    _("Addresses derived from this key will be a part of the wallet and will appear in this"
                      " wallet's transaction history."),
                    _("If adding an xprv key, this wallet will also be able to spend from these addresses."),
                ])
                cancel_but = CancelButton(d)
                cancel_but.setDefault(True)
                d.next_button = ok_but = QPushButton(_("Add Key"))  # KeysLayout widget expects this attribute
                ok_but.clicked.connect(d.accept)
                ok_but.setEnabled(False)
                l = KeysLayout(parent=d, title=message, allow_multi=False, is_valid=keystore.is_master_key)
                l.addLayout(Buttons(ok_but, cancel_but))
                d.setLayout(l)
                if d.exec_() == QDialog.Accepted:
                    if main_window.wallet_add_xpub(l.get_text().strip()):
                        dialog.close()
            add_but.clicked.connect(on_click)

        # Support for "Show XPrv"
        if has_prvkey_ct > 0:
            show_privkey_button = QToolButton()
            show_privkey_button.setText(_("Show XPrv"))
            show_privkey_button.setToolTip(_("Toggle display of public versus private master keys"))
            show_privkey_button.setCheckable(True)
            show_privkey_button.setContentsMargins(1, 1, 1, 1)
            mpk_text.addWidget(show_privkey_button)

            def on_toggle(checked):
                nonlocal mpk_list, password
                if not checked:
                    mpk_list = orig_mpk_list[:]
                    mpk_selected(labels_clayout, selected_index)  # Force redraw of text area with new text
                else:
                    for i, ks in enumerate(wallet.get_keystores()):
                        if isinstance(ks, keystore.Xprv) and ks.has_master_private_key():
                            if ks.is_master_private_key_encrypted() and password is None:
                                password = main_window.password_dialog(parent=dialog)
                                if password is None:
                                    show_privkey_button.setChecked(False)
                                    return
                            try:
                                mpk_list[i] = ks.get_master_private_key(password)
                            except InvalidPassword as e:
                                password = None  # Clear nonlocal
                                main_window.show_error(e)
                                show_privkey_button.setChecked(False)
                                return
                        else:
                            mpk_list[i] = _('No XPrv')
                    mpk_selected(labels_clayout, selected_index)  # Forces redraw of text area
                if title_lbl is not None:
                    title_lbl.setText(_("Master Public Key") if not checked else _("Master Private Key"))
                if title_gb is not None:
                    title_gb.setTitle(_("Master Public Keys") if not checked else _("Master Private Keys"))

            show_privkey_button.toggled.connect(on_toggle)
        bottom_buttons.insertStretch(bottom_buttons.count( ) -1, 2)
        mpk_selected(labels_clayout, 0)
    vbox.addStretch(1)
    vbox.addLayout(bottom_buttons)
    dialog.setLayout(vbox)
    dialog.exec_()
