# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
External Kernel connection widget
"""

# Standard library imports
import os.path as osp

# Third party imports
from jupyter_core.paths import jupyter_runtime_dir
from qtpy.compat import getopenfilename
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QGridLayout,
                            QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                            QPushButton, QRadioButton, QSpacerItem,
                            QVBoxLayout, QComboBox, QMessageBox, QListWidget)

# Local imports
from spyder.config.base import _, get_home_dir
from spyder.config.main import CONF
from typing import Optional


def _falsy_to_none(arg):
    return arg if arg else None


def show_info_dialog(title, text):
    """
    Shows a modal dialog with provided title and text.

    :param title: Title of the dialog.
    :param text: Message to show.
    :return: None
    """
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setText(text)
    # msg.setInformativeText("This is additional information")
    msg.setWindowTitle(title)
    # msg.setDetailedText("The details are as follows:")
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()


class RemoteKernelSetupDialog(QDialog):
    """Dialog to connect to existing kernels (either local or remote)."""

    def __init__(self, parent=None):
        super(RemoteKernelSetupDialog, self).__init__(parent)
        self.setWindowTitle(_('Setup remote kernel'))

        self.TEXT_FETCH_REMOTE_CONN_FILES_BTN = 'Fetch remote connection files'
        self.DEFAULT_CMD_FOR_JUPYTER_RUNTIME = 'jupyter --runtime-dir'

        # Name of the connection
        name_label = QLabel(_('Configuration name:'))
        self.name_line_edit = QLineEdit()

        # SSH connection
        hn_label = QLabel(_('Hostname:'))
        self.hn = QLineEdit()
        pn_label = QLabel(_('Port:'))
        self.pn = QLineEdit()
        self.pn.setMaximumWidth(75)

        un_label = QLabel(_('Username:'))
        self.un = QLineEdit()

        # SSH authentication
        auth_group = QGroupBox(_("Authentication method:"))
        self.pw_radio = QRadioButton()
        pw_label = QLabel(_('Password:'))
        self.kf_radio = QRadioButton()
        kf_label = QLabel(_('SSH keyfile:'))

        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw_radio.toggled.connect(self.pw.setEnabled)
        self.kf_radio.toggled.connect(self.pw.setDisabled)

        self.kf = QLineEdit()
        kf_open_btn = QPushButton(_('Browse'))
        kf_open_btn.clicked.connect(self.select_ssh_key)
        kf_layout = QHBoxLayout()
        kf_layout.addWidget(self.kf)
        kf_layout.addWidget(kf_open_btn)

        kfp_label = QLabel(_('Passphase:'))
        self.kfp = QLineEdit()
        self.kfp.setPlaceholderText(_('Optional'))
        self.kfp.setEchoMode(QLineEdit.Password)

        self.kf_radio.toggled.connect(self.kf.setEnabled)
        self.kf_radio.toggled.connect(self.kfp.setEnabled)
        self.kf_radio.toggled.connect(kf_open_btn.setEnabled)
        self.kf_radio.toggled.connect(kfp_label.setEnabled)
        self.pw_radio.toggled.connect(self.kf.setDisabled)
        self.pw_radio.toggled.connect(self.kfp.setDisabled)
        self.pw_radio.toggled.connect(kf_open_btn.setDisabled)
        self.pw_radio.toggled.connect(kfp_label.setDisabled)

        # Button to fetch JSON files listing
        # self.kf_fetch_conn_files_btn = QPushButton(_(self.TEXT_FETCH_REMOTE_CONN_FILES_BTN))
        # self.kf_fetch_conn_files_btn.clicked.connect(self.fill_combobox_with_fetched_remote_connection_files)
        # self.cb_remote_conn_files = QComboBox()
        # self.cb_remote_conn_files.currentIndexChanged.connect(self._take_over_selected_remote_configuration_file)

        # Remote kernel groupbox
        self.start_remote_kernel_group = QGroupBox(_("Start remote kernel"))

        # Advanced settings to get remote connection files
        jupyter_runtime_location_cmd_label = QLabel(_('Command to get Jupyter runtime:'))
        self.jupyter_runtime_location_cmd_lineedit = QLineEdit()
        self.jupyter_runtime_location_cmd_lineedit.setPlaceholderText(_(self.DEFAULT_CMD_FOR_JUPYTER_RUNTIME))

        # SSH layout
        ssh_layout = QGridLayout()
        ssh_layout.addWidget(name_label, 0, 0)
        ssh_layout.addWidget(self.name_line_edit, 0, 2)

        ssh_layout.addWidget(hn_label, 1, 0, 1, 2)
        ssh_layout.addWidget(self.hn, 1, 2)
        ssh_layout.addWidget(pn_label, 1, 3)
        ssh_layout.addWidget(self.pn, 1, 4)
        ssh_layout.addWidget(un_label, 2, 0, 1, 2)
        ssh_layout.addWidget(self.un, 2, 2, 1, 3)

        # SSH authentication layout
        auth_layout = QGridLayout()
        auth_layout.addWidget(self.pw_radio, 1, 0)
        auth_layout.addWidget(pw_label, 1, 1)
        auth_layout.addWidget(self.pw, 1, 2)
        auth_layout.addWidget(self.kf_radio, 2, 0)
        auth_layout.addWidget(kf_label, 2, 1)
        auth_layout.addLayout(kf_layout, 2, 2)
        auth_layout.addWidget(kfp_label, 3, 1)
        auth_layout.addWidget(self.kfp, 3, 2)

        auth_layout.addWidget(jupyter_runtime_location_cmd_label, 4, 1)
        auth_layout.addWidget(self.jupyter_runtime_location_cmd_lineedit, 4, 2)
        # auth_layout.addWidget(self.kf_fetch_conn_files_btn, 5, 1)
        # auth_layout.addWidget(self.cb_remote_conn_files, 5, 2)

        auth_group.setLayout(auth_layout)

        # Remote kernel layout
        self.rm_group = QGroupBox(_("Setup up of a remote connection"))
        rm_layout = QVBoxLayout()
        rm_layout.addLayout(ssh_layout)
        rm_layout.addSpacerItem(QSpacerItem(QSpacerItem(0, 8)))
        rm_layout.addWidget(auth_group)
        self.rm_group.setLayout(rm_layout)
        self.rm_group.setCheckable(False)

        # Ok and Cancel buttons
        self.accept_btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)

        self.accept_btns.accepted.connect(self.accept)
        self.accept_btns.rejected.connect(self.reject)

        btns_layout = QHBoxLayout()
        btns_layout.addWidget(self.accept_btns)

        # Dialog layout
        layout = QVBoxLayout()
        layout.addSpacerItem(QSpacerItem(QSpacerItem(0, 8)))
        # layout.addSpacerItem(QSpacerItem(QSpacerItem(0, 12)))
        layout.addWidget(self.rm_group)
        layout.addLayout(btns_layout)

        # Main layout
        hbox_layout = QHBoxLayout(self)

        # Left side with the list of all remote connection configurations
        items_label = QLabel(text="Configured remote locations")
        self.items_list = QListWidget()

        items_layout = QVBoxLayout()
        items_layout.addWidget(items_label)
        items_layout.addWidget(self.items_list)
        edit_delete_new_buttons_layout = QHBoxLayout()
        edit_btn = QPushButton(text="Edit")
        add_btn = QPushButton(text="Add")
        delete_btn = QPushButton(text="Delete")
        edit_delete_new_buttons_layout.addWidget(add_btn)
        edit_delete_new_buttons_layout.addWidget(edit_btn)
        edit_delete_new_buttons_layout.addWidget(delete_btn)

        items_layout.addLayout(edit_delete_new_buttons_layout)

        hbox_layout.addSpacerItem(QSpacerItem(10, 0))
        hbox_layout.addLayout(items_layout)
        hbox_layout.addLayout(layout)

    def select_ssh_key(self):
        kf = getopenfilename(self, _('Select SSH keyfile'),
                             get_home_dir(), '*.pem;;*')[0]
        self.kf.setText(kf)

    def _take_over_selected_remote_configuration_file(self, chosen_idx_of_combobox_with_remote_conn_files):
        remote_path_filename = self.remote_conn_file_paths[chosen_idx_of_combobox_with_remote_conn_files]
        self.cf.setText(remote_path_filename)
