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
from paramiko.ssh_exception import NoValidConnectionsError
from qtpy.compat import getopenfilename
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QGridLayout,
                            QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                            QPushButton, QRadioButton, QSpacerItem,
                            QVBoxLayout, QComboBox, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal

# Local imports
from spyder.config.base import _, get_home_dir
from spyder.config.main import CONF
from typing import Optional

import paramiko
import os
import glob
import json
import tempfile

#from spyder.plugins.ipythonconsole.widgets.kernelconnectremotekernelsetup import RemoteKernelSetupDialog
from .kernelconnectremotekernelsetup import RemoteKernelSetupDialog

TEXT_FETCH_REMOTE_CONN_FILES_BTN = 'Fetch remote connection files'
DEFAULT_CMD_FOR_JUPYTER_RUNTIME = 'jupyter --runtime-dir'


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


class LocalConnectionSettings:
    def __init__(self, directory: str = None, filename: str = None, connection_name: str = None):
        self.directory = directory
        self.filename = filename
        self.connection_name = connection_name

        if connection_name is None:
            self.connection_name = directory
            if filename is not None:
                self.connection_name = os.path.join(directory, filename)

    def to_json(self):
        return {
            'directory': self.directory,
            'filename': self.filename,
            'connection_name': self.connection_name
        }

    def from_json(self, js_settings: dict):
        self.directory = js_settings['directory']
        self.filename = js_settings['filename']
        self.connection_name = js_settings['connection_name'] if 'connection_name' in js_settings.keys() else js_settings['name']
        return self


class RemoteConnectionSettings:
    def __init__(self, username: str = None, hostname: str = None,
                 port: int = 22, password: str = None, keyfile_path: str = None,
                 connection_name: str = None,
                 cmd_for_jupyter_runtime_location: str = None):
        self.username = username
        self.hostname = hostname
        self.port = port
        self.keyfile_path = keyfile_path
        self.password = password
        self.connection_name = self.hostname if connection_name is None else connection_name
        self.cmd_for_jupyter_runtime_location = \
            DEFAULT_CMD_FOR_JUPYTER_RUNTIME if cmd_for_jupyter_runtime_location is None \
                else cmd_for_jupyter_runtime_location

    def to_json(self):
        return {
            'username': self.username,
            'hostname': self.hostname,
            'port': self.port,
            'keyfile_path': self.keyfile_path,
            'password': self.password,
            'connection_name': self.connection_name,
            'cmd_for_jupyter_runtime_location': self.cmd_for_jupyter_runtime_location,
        }

    def from_json(self, js_settings: dict):
        self.username = js_settings['username']
        self.hostname = js_settings['hostname']
        self.port = js_settings['port']
        self.keyfile_path = js_settings['keyfile_path']
        self.password = js_settings['password']
        self.connection_name = self.connection_name = js_settings['connection_name'] if 'connection_name' in js_settings.keys() else js_settings['name']
        self.cmd_for_jupyter_runtime_location = js_settings['cmd_for_jupyter_runtime_location']
        return self


def connection_settings_factory(js):
    if js['type'] == 'local':
        s = LocalConnectionSettings()
        s.from_json(js)
        return s

    elif js['type'] == 'remote':
        r = RemoteConnectionSettings()
        r.from_json(js)
        return r


def _process_exists(shell_port: str, client: paramiko.SSHClient):
    """
    Checks if the shell port found in the connection configuration json file belongs to a running python process.

    :param shell_port: Port from JSON configuration file for a Jupyter notebook.
    :param client: Paramiko SSH client
    :return: True if the port belongs to a python process, False otherwise.
    """
    stdin, stdout, stderr = client.exec_command(f"fuser {shell_port}/tcp")
    running_id_output = stdout.readlines()
    if len(running_id_output) == 0:
        return False

    id_of_process = running_id_output[0].strip()
    stdin, stdout, stderr = client.exec_command(f"ls -l /proc/{id_of_process}/exe")
    path_to_executable_of_process = stdout.readlines()
    if len(path_to_executable_of_process) == 0:
        return False

    path_to_executable_of_process = path_to_executable_of_process[0].split(' -> ')[1]
    if 'python' not in path_to_executable_of_process:
        return False

    return True


class FetchConnectionFilesThread(QThread):
    signal = pyqtSignal(str)

    def __init__(self):
        QThread.__init__(self)
        self.connection_settings_list: list = []

    # run method gets called when we start the thread
    def run(self):
        file_locations = []
        for conn_setting in self.connection_settings_list:
            if isinstance(conn_setting, LocalConnectionSettings):
                if conn_setting.filename is not None and conn_setting.directory is not None:
                    file_locations.append({'type': 'local', 'path': os.path.join(conn_setting.directory, conn_setting.filename)})
                elif conn_setting.directory is not None and conn_setting.filename is None:
                    jsons_from_runtime_dir = glob.glob(f'{conn_setting.directory}/*.json')
                    for js_file in jsons_from_runtime_dir:
                        file_locations.append({'type': 'local', 'path': js_file, 'connection_settings_obj': conn_setting.to_json()})
            elif isinstance(conn_setting, RemoteConnectionSettings):
                fetched_files = self._fetch_connection_files_list(conn_setting.hostname,
                                                                  conn_setting.keyfile_path,
                                                                  conn_setting.password,
                                                                  conn_setting.username,
                                                                  str(conn_setting.port),
                                                                  conn_setting.cmd_for_jupyter_runtime_location)

                for js_file in fetched_files:
                    file_locations.append({'type': 'remote', 'conn_setting_name': conn_setting.connection_name, 'path': js_file, 'connection_settings_obj': conn_setting.to_json()})

        self.signal.emit(json.dumps(file_locations))

    def _fetch_connection_files_list(self,
                                     host: str,
                                     keyfile: Optional[str],
                                     password: Optional[str],
                                     username: Optional[str],
                                     port: str,
                                     cmd_to_get_location_of_jupyter_runtime_files: Optional[str]):
        """

        :param host: URL or IP of the host.
        :param keyfile: SSH key path or None if no key was provided.
        :param password: Password for SSH connection or None if no password is used.
        :rtype: List[str]
        :return:
        """
        client = paramiko.SSHClient()
        list_of_copied_connection_files = []
        try:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host,
                           port=int(port),
                           key_filename=keyfile,
                           passphrase=password,
                           username=username,
                           timeout=5,
                           auth_timeout=5)
            if cmd_to_get_location_of_jupyter_runtime_files is None:
                cmd_to_get_location_of_jupyter_runtime_files = self.DEFAULT_CMD_FOR_JUPYTER_RUNTIME

            stdin, stdout, stderr = client.exec_command(cmd_to_get_location_of_jupyter_runtime_files)
            location_of_jupyter_runtime = stdout.readlines()
            if len(location_of_jupyter_runtime) > 0:
                location_of_jupyter_runtime = location_of_jupyter_runtime[0].strip()

                # get absolute paths
                stdin, stdout, stderr = client.exec_command(f'ls -d {location_of_jupyter_runtime}/*')
                list_of_connection_files = stdout.readlines()

                if len(list_of_connection_files) > 0:
                    list_of_connection_files = [l.strip() for l in list_of_connection_files]
                    temp_dir = tempfile.gettempdir()
                    only_filenames = [f.rsplit('/', 1)[1] for f in list_of_connection_files]
                    list_of_copied_connection_files = [os.path.join(temp_dir, f) for f in only_filenames]
                    for remote_path, filename_only in zip(list_of_connection_files, only_filenames):
                        sftp = client.open_sftp()
                        local_path_of_connection_file = os.path.join(temp_dir, filename_only)
                        sftp.get(remote_path, local_path_of_connection_file)

                        with open(local_path_of_connection_file, 'r') as js_file:
                            conn_file_js = json.load(js_file)
                        shell_port = conn_file_js['shell_port']

                        if not _process_exists(shell_port=shell_port, client=client):
                            local_path_to_downloaded_config_file = os.path.join(temp_dir, filename_only)
                            list_of_copied_connection_files.remove(local_path_to_downloaded_config_file)
                            os.remove(local_path_to_downloaded_config_file)

                    sftp.close()
                else:
                    show_info_dialog(
                        "Warning",
                        f"Could not find any jupyter configuration files in {location_of_jupyter_runtime}.")
            else:
                show_info_dialog(
                    "Warning",
                    f"Could not extract jupyter runtime location. Error from command line: {stderr.readlines()}")

        except NoValidConnectionsError as e:
            show_info_dialog("Error", f"Could not connect to hostname {host}")

        finally:
            client.close()

        return list_of_copied_connection_files


class KernelConnectionMainDialog(QDialog):
    """Dialog to connect to existing kernels (either local or remote)."""

    def __init__(self, parent=None):
        super(KernelConnectionMainDialog, self).__init__(parent)

        self.connection_settings_list: list = []
        # tmp = [
        #     LocalConnectionSettings(jupyter_runtime_dir(), None),
        #     RemoteConnectionSettings(username='pi', hostname='192.168.0.10',
        #                              port=22, password=None, keyfile_path='/home/sergej/.ssh/raspys_2018_03_26_rsa',
        #                              name='pi',
        #                              cmd_for_jupyter_runtime_location='cd spyder-dev; ~/.local/bin/pipenv run jupyter --runtime'
        #                              )]

        self.setWindowTitle(_('Connect to an existing kernel'))

        # Connection file
        cf_label = QLabel(_('Select kernel:'))
        self.cf = QComboBox()
        self.cf.setMinimumWidth(350)
        self.fetch_kernels_btn = QPushButton(_('Fetch kernels'))
        self.config_remote_kernels_btn = QPushButton(_('Configure kernel locations'))

        self.fetch_kernels_btn.clicked.connect(self._fetch_kernels)
        self.config_remote_kernels_btn.clicked.connect(self.configure_remote_kernels_dialog)

        cf_layout = QHBoxLayout()
        cf_layout.addWidget(cf_label)
        cf_layout.addWidget(self.cf)
        cf_layout.addWidget(self.fetch_kernels_btn)
        cf_layout.addWidget(self.config_remote_kernels_btn)

        # Ok and Cancel buttons
        self.accept_btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)

        self.accept_btns.accepted.connect(self.save_connection_settings)
        self.accept_btns.accepted.connect(self.accept)
        self.accept_btns.rejected.connect(self.reject)

        # Save connection settings checkbox
        self.save_layout = QCheckBox(self)
        self.save_layout.setText(_("Save connection settings"))

        btns_layout = QHBoxLayout()
        btns_layout.addWidget(self.save_layout)
        btns_layout.addWidget(self.accept_btns)

        # Dialog layout
        layout = QVBoxLayout(self)
        layout.addSpacerItem(QSpacerItem(QSpacerItem(0, 8)))
        layout.addLayout(cf_layout)
        layout.addSpacerItem(QSpacerItem(QSpacerItem(0, 12)))
        layout.addLayout(btns_layout)

        # List with connection file paths found on the remote host
        self.remote_conn_file_paths = []
        self.fetched_connection_files = {}

        self.load_connection_settings()

        self.fetch_thread = None

    def _finished_fetching_remote_files(self, conn_files_as_json):
        conn_files_as_dict = json.loads(conn_files_as_json)
        for r in conn_files_as_dict:
            if r["type"] == 'local':
                self.cf.addItem(f'Local: {r["path"]}')
            else:
                self.cf.addItem(f'Remote: {r["conn_setting_name"]} -> {r["path"]}')
        self.cf.setEnabled(True)
        self.setWindowTitle("Files fetched. Please choose a connection file.")
        self.fetched_connection_files = conn_files_as_dict

        if conn_files_as_json is None or len(conn_files_as_dict) == 0:
            self.accept_btns.setEnabled(False)

    def load_connection_settings(self):
        """Load the user's previously-saved kernel connection settings."""
        conn_settings_jsons = CONF.get("existing-kernel", "settings", [])
        if len(conn_settings_jsons) > 0:
            for single_entry in conn_settings_jsons:
                self.connection_settings_list.append(connection_settings_factory(single_entry))


    def save_connection_settings(self):
        """Save user's kernel connection settings."""
        if not self.save_layout.isChecked():
            return

        connection_settings_js = []
        for cs in self.connection_settings_list:
            js = cs.to_json()
            if isinstance(cs, LocalConnectionSettings):
                js['type'] = 'local'
            elif isinstance(cs, RemoteConnectionSettings):
                js['type'] = 'remote'
            connection_settings_js.append(js)

        CONF.set("existing-kernel", "settings", connection_settings_js)

        #
        # try:
        #     import keyring
        #     if is_ssh_key:
        #         keyring.set_password("spyder_remote_kernel",
        #                              "ssh_key_passphrase",
        #                              self.kfp.text())
        #     else:
        #         keyring.set_password("spyder_remote_kernel",
        #                              "ssh_password",
        #                              self.pw.text())
        # except Exception:
        #     pass
        pass

    def select_connection_file(self):
        cf = getopenfilename(self, _('Select kernel connection file'),
                             jupyter_runtime_dir(), '*.json;;*.*')[0]
        self.cf.setText(cf)

    def _fetch_kernels(self):
        self.fetch_thread = FetchConnectionFilesThread()
        self.fetch_thread.signal.connect(self._finished_fetching_remote_files)
        self.fetch_thread.connection_settings_list = self.connection_settings_list
        self.cf.setEnabled(False)
        self.setWindowTitle("...Fetching connection files from all configured locations...")
        self.fetch_thread.start()  # Finally starts the thread

    def configure_remote_kernels_dialog(self):
        remote_dialog = RemoteKernelSetupDialog()
        remote_dialog.set_connection_configs(self.connection_settings_list)
        remote_dialog.exec_()
        self.connection_settings_list = remote_dialog.get_connection_settings()

    @staticmethod
    def get_connection_parameters(parent=None, dialog=None):
        if not dialog:
            dialog = KernelConnectionMainDialog(parent)
        result = dialog.exec_()
        accepted = result == QDialog.Accepted
        selected_cf_idx = dialog.cf.currentIndex()
        if dialog.cf.count() > 0:
            conn_obj = dialog.fetched_connection_files[selected_cf_idx]
            conn_config = conn_obj['connection_settings_obj']
            if conn_obj['type'] == 'local':
                return conn_obj['path'], None, None, None, accepted
            elif conn_obj['type'] == 'remote':
                hostname_with_user = "{0}@{1}:{2}".format(conn_config['username'],
                                                conn_config['hostname'],
                                                conn_config['port'])
                return conn_obj['path'], hostname_with_user, conn_config['keyfile_path'], conn_config['password'], accepted
