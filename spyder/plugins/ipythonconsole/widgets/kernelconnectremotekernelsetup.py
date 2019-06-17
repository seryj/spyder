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
        cfg_name_label = QLabel(_('Configuration name:'))
        self.cfg_name_line_edit = QLineEdit()

        # SSH connection
        hostname_label = QLabel(_('Hostname:'))
        self.hostname_lineedit = QLineEdit()
        port_label = QLabel(_('Port:'))
        self.port_lineeidt = QLineEdit()
        self.port_lineeidt.setMaximumWidth(75)

        username_label = QLabel(_('Username:'))
        self.username_lineedit = QLineEdit()

        # SSH authentication
        auth_group = QGroupBox(_("Authentication method:"))
        self.pw_radio = QRadioButton()
        pw_label = QLabel(_('Password:'))
        self.keyfile_radio = QRadioButton()
        keyfile_label = QLabel(_('SSH keyfile:'))

        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw_radio.toggled.connect(self.pw.setEnabled)
        self.keyfile_radio.toggled.connect(self.pw.setDisabled)

        self.keyfile_path_lineedit = QLineEdit()
        keyfile_browse_btn = QPushButton(_('Browse'))
        keyfile_browse_btn.clicked.connect(self.select_ssh_key)
        keyfile_layout = QHBoxLayout()
        keyfile_layout.addWidget(self.keyfile_path_lineedit)
        keyfile_layout.addWidget(keyfile_browse_btn)

        passphrase_label = QLabel(_('Passphrase:'))
        self.passphrase_lineedit = QLineEdit()
        self.passphrase_lineedit.setPlaceholderText(_('Optional'))
        self.passphrase_lineedit.setEchoMode(QLineEdit.Password)

        self.keyfile_radio.toggled.connect(self.keyfile_path_lineedit.setEnabled)
        self.keyfile_radio.toggled.connect(self.passphrase_lineedit.setEnabled)
        self.keyfile_radio.toggled.connect(keyfile_browse_btn.setEnabled)
        self.keyfile_radio.toggled.connect(passphrase_label.setEnabled)
        self.pw_radio.toggled.connect(self.keyfile_path_lineedit.setDisabled)
        self.pw_radio.toggled.connect(self.passphrase_lineedit.setDisabled)
        self.pw_radio.toggled.connect(keyfile_browse_btn.setDisabled)
        self.pw_radio.toggled.connect(passphrase_label.setDisabled)

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
        ssh_layout.addWidget(cfg_name_label, 0, 0)
        ssh_layout.addWidget(self.cfg_name_line_edit, 0, 2)

        ssh_layout.addWidget(hostname_label, 1, 0, 1, 2)
        ssh_layout.addWidget(self.hostname_lineedit, 1, 2)
        ssh_layout.addWidget(port_label, 1, 3)
        ssh_layout.addWidget(self.port_lineeidt, 1, 4)
        ssh_layout.addWidget(username_label, 2, 0, 1, 2)
        ssh_layout.addWidget(self.username_lineedit, 2, 2, 1, 3)

        # SSH authentication layout
        auth_layout = QGridLayout()
        auth_layout.addWidget(self.pw_radio, 1, 0)
        auth_layout.addWidget(pw_label, 1, 1)
        auth_layout.addWidget(self.pw, 1, 2)
        auth_layout.addWidget(self.keyfile_radio, 2, 0)
        auth_layout.addWidget(keyfile_label, 2, 1)
        auth_layout.addLayout(keyfile_layout, 2, 2)
        auth_layout.addWidget(passphrase_label, 3, 1)
        auth_layout.addWidget(self.passphrase_lineedit, 3, 2)

        auth_layout.addWidget(jupyter_runtime_location_cmd_label, 4, 1)
        auth_layout.addWidget(self.jupyter_runtime_location_cmd_lineedit, 4, 2)
        # auth_layout.addWidget(self.kf_fetch_conn_files_btn, 5, 1)
        # auth_layout.addWidget(self.cb_remote_conn_files, 5, 2)

        auth_group.setLayout(auth_layout)

        # Remote kernel layout
        self.rm_group = QGroupBox(_("Setup up of a remote connection"))
        self.rm_group.setEnabled(False)
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
        self.items_list.clicked.connect(self._on_items_list_click)

        items_layout = QVBoxLayout()
        items_layout.addWidget(items_label)
        items_layout.addWidget(self.items_list)
        edit_delete_new_buttons_layout = QHBoxLayout()
        edit_btn = QPushButton(text="Edit")
        add_btn = QPushButton(text="Add")
        delete_btn = QPushButton(text="Delete")

        add_btn.clicked.connect(self._on_add_btn_click)
        edit_btn.clicked.connect(self._on_edit_btn_click)
        delete_btn.clicked.connect(self._on_delete_btn_click)

        edit_delete_new_buttons_layout.addWidget(add_btn)
        edit_delete_new_buttons_layout.addWidget(edit_btn)
        edit_delete_new_buttons_layout.addWidget(delete_btn)

        items_layout.addLayout(edit_delete_new_buttons_layout)

        hbox_layout.addSpacerItem(QSpacerItem(10, 0))
        hbox_layout.addLayout(items_layout)
        hbox_layout.addLayout(layout)

        self.lst_with_connecion_configs = []

    def _on_items_list_click(self):
        from .kernelconnectmaindialog import LocalConnectionSettings, RemoteConnectionSettings
        idx_of_config = self.items_list.selectedIndexes()[0].row()
        cfg = self.lst_with_connecion_configs[idx_of_config]
        if isinstance(cfg, RemoteConnectionSettings):
            self._update_remote_connection_input_fields(cfg)
        else:
            show_info_dialog("Information", "This functionality is still not available")

    def _clear_remote_connection_input_fields(self):
        self.keyfile_path_lineedit.setText("")
        self.passphrase_lineedit.setText("")
        self.hostname_lineedit.setText("")
        self.username_lineedit.setText("")
        self.port_lineeidt.setText("")
        self.cfg_name_line_edit.setText("")
        self.jupyter_runtime_location_cmd_lineedit.setText("")

        self.keyfile_radio.setChecked(False)
        self.pw_radio.setChecked(False)

    def _update_remote_connection_input_fields(self, remote_conn_settings):
        self.keyfile_path_lineedit.setText(remote_conn_settings.keyfile_path)
        self.passphrase_lineedit.setText(remote_conn_settings.password)
        self.hostname_lineedit.setText(remote_conn_settings.hostname)
        self.username_lineedit.setText(remote_conn_settings.username)
        self.port_lineeidt.setText(str(remote_conn_settings.port))
        self.cfg_name_line_edit.setText(remote_conn_settings.connection_name)
        self.jupyter_runtime_location_cmd_lineedit.setText(remote_conn_settings.cmd_for_jupyter_runtime_location)

        self.keyfile_radio.setChecked(remote_conn_settings.keyfile_path is not None)
        self.pw_radio.setChecked(remote_conn_settings.password is not None)

    def _on_add_btn_click(self):
        from .kernelconnectmaindialog import LocalConnectionSettings, RemoteConnectionSettings

        username = self.username_lineedit.text()
        passphrase = self.passphrase_lineedit.text()
        hostname = self.hostname_lineedit.text()
        keyfile_path = self.keyfile_path_lineedit.text()
        port = int(self.port_lineeidt.text()) if self.port_lineeidt.text() != "" else 22
        jup_runtime_cmd = self.jupyter_runtime_location_cmd_lineedit.text()
        cfg_name = self.cfg_name_line_edit.text()

        cfg = RemoteConnectionSettings(
            username=username,
            hostname=hostname,
            keyfile_path=keyfile_path,
            port=port,
            connection_name=cfg_name,
            cmd_for_jupyter_runtime_location=jup_runtime_cmd,
            password=passphrase
        )

        self.lst_with_connecion_configs.append(cfg)
        self._update_list_with_configs()
        self.rm_group.setEnabled(False)

    def _on_edit_btn_click(self):
        from .kernelconnectmaindialog import LocalConnectionSettings, RemoteConnectionSettings
        self.rm_group.setEnabled(True)
        idx_of_config = self.items_list.selectedIndexes()[0].row()
        cfg = self.lst_with_connecion_configs[idx_of_config]
        if isinstance(cfg, RemoteConnectionSettings):
            self._update_remote_connection_input_fields(cfg)
        else:
            show_info_dialog("Information", "This functionality is still not available")

    def _on_delete_btn_click(self):
        idx_of_config = self.items_list.selectedIndexes()[0].row()
        self.lst_with_connecion_configs.pop(idx_of_config)
        self._update_list_with_configs()

    def select_ssh_key(self):
        kf = getopenfilename(self, _('Select SSH keyfile'),
                             get_home_dir(), '*.pem;;*')[0]
        self.keyfile_path_lineedit.setText(kf)

    def _take_over_selected_remote_configuration_file(self, chosen_idx_of_combobox_with_remote_conn_files):
        remote_path_filename = self.remote_conn_file_paths[chosen_idx_of_combobox_with_remote_conn_files]
        self.cf.setText(remote_path_filename)

    def set_connection_configs(self, lst_with_connecion_configs):
        self.lst_with_connecion_configs = lst_with_connecion_configs
        self._update_list_with_configs()

    def _update_list_with_configs(self):
        from .kernelconnectmaindialog import LocalConnectionSettings, RemoteConnectionSettings
        # now, fill the list
        self.items_list.clear()
        for cfg in self.lst_with_connecion_configs:
            if isinstance(cfg, LocalConnectionSettings):
                self.items_list.addItem(f"Local: {cfg.connection_name}")
            elif isinstance(cfg, RemoteConnectionSettings):
                self.items_list.addItem(f"Remote: {cfg.connection_name}")

    def get_connection_settings(self):
        return self.lst_with_connecion_configs