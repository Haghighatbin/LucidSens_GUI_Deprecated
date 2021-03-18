"""
- make sure you've defined a layout in designer
- Promote to GraphicsWindow - Header: pyqtgraph - Add - Promote
- Beware of the GraphicsWindow (pyqtgraph) and centralwidget > just delete it!
- create the icons_qrc resource file
- add icons from the resource file (icons extensions have to be icns in MAC OS)
- Check the imports for the icons_rc and the pyqtgraph in the buttom of the appGui.py file

+ pyuic5 app.ui -o appGUI.py
+ pyrrc5 icons.qrc -o icons_rc.py (beware of the CURRENT path)

* add the appGUI to the h_c_thrd.py and finalise the app
* run pyinstaller (use the template) and you're done!

$ in packages app > Distribution > under-packages > Payload > drag and drop app.app file
$ do the rest (i. e. add README, License etc.) and then Build (from the Menu) and you're done!!

- to right-align the bluetooth button the following will be added in GUI file before adding the bluetooth action
to the toolbar:

spacer = QtGui.QWidget(self)
        spacer.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.toolBar.addWidget(spacer)

        self.toolBar.addAction(self.actionBluetooth)

Changes in version 1.03
- Wifi communication module was added
_ multi-threading was successfully tested simultaneously waiting for the incoming serial and wifi calls

Changes in version 1.04
- Bluetooth module was disabled from GUI  -> self.actionBluetooth.setVisible(False)

Changes in version 1.05
- Account.txt file was added for wifi credentials

Changes in version 1.07
- GUI was changed. sampling mod was added.
- code was modified accordingly.

Changes in version 1.08
- switched to loboris firmware
- the data transferring modules were all recoded.
"""
import sys
from PyQt5 import QtWidgets, QtTest, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot
import pyqtgraph as pg
# from PyQt5.QtWidgets import *
# from PyQt5.QtCore import *
# from PyQt5.QtGui import *
# from PyQt5 import QtTest
import matplotlib.pyplot as plt
import qdarkstyle
import csv
from numpy import trapz
import numpy as np
import serial
# import serial.tools.list_ports as lp
import sys
import time
import json
# import Image
import chardet
import socket
import os

import mainWindowGUI

cyan_font = "<font size='3' color='cyan'>"
red_font = "<font size='3' color='red'>"
green_font = "<font size='3' color='green'>"
blue_font = "<font size='3' color='blue'>"
end_font = "</font>"

board_ip = "192.168.1.95"
board_port = 3175

__APPNAME__ = "MinimalSens"
VERSION = "1.07"


class Form(QtWidgets.QMainWindow, mainWindowGUI.Ui_MainWindow):
    def __init__(self, parent=None):
        super(Form, self).__init__(parent)

        self.packet_size = 77
        self.content = ''

        self.serial_connection = False
        self.wifi_connection = False
        # self.bt_connected = False

        self.setupUi(self)
        self.actionOpen.triggered.connect(self.open)
        self.actionNew.triggered.connect(self.new)
        self.actionExit.triggered.connect(self.exit)
        self.actionAbout_Us.triggered.connect(self.about_us)
        self.actionHelp.triggered.connect(self.help)
        self.RunButton.clicked.connect(self.run)
        self.TestButton.clicked.connect(self.run_test)
        self.actionConnection.triggered.connect(self.connection_module)
        self.graphicsView.clear()
        # self.vb = pg.ViewBox()
        # self.graphicsView.setCentralItem(self.vb)
        # img = "/Users/aminhb/PycharmProjects/MinimalSensGUI_v0.01/MinimalSensGUI_v0.01/Logo_Splash.JPG"
        # img_data = np.asarray(Image.open(img))
        # image = pg.ImageItem(img_data)
        # self.vb.addItem(image)

        p0 = self.graphicsView.addPlot()
        p0.showAxis('right', show=True)
        p0.showAxis('top', show=True)
        p0.showGrid(x=True, y=True, alpha=1)
        # p0.setLabel('bottom', 'x', **{'color': 'white', 'font-size': '12px'})
        # p0.setLabel('left', 'f(x)', **{'color': 'white', 'font-size': '12px'})

        self.textBrowser.append("Copyright © 2020 " + blue_font + "Minimal" + end_font + red_font + "Sens" + end_font)
        self.textBrowser.append("Version {}\n".format(VERSION))
        self.textBrowser.append("Developed by M. Amin Haghighatbin")
        # "PhD, Postdoctoral Fellow\n"
        # "中国科学技术大学\n"
        # "University of Science and Technology of China (USTC)\n")
        self.textBrowser.append("-" * 36)
        self.checkBox_SampMod.stateChanged.connect(self.sampling_mod_state)
        self.checkBox_IncubMod.stateChanged.connect(self.incubation_mod_state)
        self.checkBox_PmMod.stateChanged.connect(self.pm_mod_state)
        self.checkBox_DataSmt.stateChanged.connect(self.data_processing_mod_state)
        self.checkBox_SigAmp.stateChanged.connect(self.sig_amp_mod_state)

        self.lineEdit_IP.editingFinished.connect(self.ip_chk)
        self.lineEdit_FP.editingFinished.connect(self.fp_chk)
        self.lineEdit_NC.editingFinished.connect(self.nc_chk)
        self.lineEdit_PW.editingFinished.connect(self.pw_chk)
        self.lineEdit_SI.editingFinished.connect(self.si_chk)
        self.lineEdit_EChemQT.editingFinished.connect(self.qt_chk)
        self.lineEdit_SampQT.editingFinished.connect(self.sqt_chk)
        self.lineEdit_SampNumbr.editingFinished.connect(self.sn_chk)
        self.lineEdit_SampT.editingFinished.connect(self.st_chk)
        self.lineEdit_IncubT.editingFinished.connect(self.it_chk)
        self.lineEdit_PmV.editingFinished.connect(self.pmv_chk)
        self.lineEdit_adcGn.editingFinished.connect(self.adcg_chk)
        self.lineEdit_adcSpd.editingFinished.connect(self.adcs_chk)

    def ip_chk(self):
        try:
            if not self.lineEdit_IP.text() or float(self.lineEdit_IP.text()) > 2.9 or float(
                    self.lineEdit_IP.text()) < 0:
                raise ValueError
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0 and 2.9""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_IP.setText('0.0')
        except Exception as e:
            print(e)
            self.lineEdit_IP.setText('0.0')

    def fp_chk(self):
        try:
            if not self.lineEdit_FP.text() or float(self.lineEdit_FP.text()) > 3 or float(
                    self.lineEdit_FP.text()) < 0:
                raise ValueError
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0 and 3""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_FP.setText('0.0')

        except Exception as e:
            print(e)
            self.lineEdit_FP.setText('0.0')

    def nc_chk(self):
        try:
            if not self.lineEdit_NC.text() or float(self.lineEdit_NC.text()) > 10 or float(
                    self.lineEdit_NC.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 1 and 10""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_NC.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 1 and 10""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_NC.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_NC.setText('1')

    def pw_chk(self):
        try:
            if not self.lineEdit_PW.text() or float(self.lineEdit_PW.text()) > 10 or float(
                    self.lineEdit_PW.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 1 and 10""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_PW.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 1 and 10""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_PW.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_PW.setText('1')

    def si_chk(self):
        try:
            if not self.lineEdit_SI.text() or float(self.lineEdit_SI.text()) > 1.001 or float(
                    self.lineEdit_SI.text()) < 0.001:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0.001 and 1.1""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_SI.setText('0.1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0.001 and 1.1""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_SI.setText('0.1')
        except Exception as e:
            print(e)
            self.lineEdit_SI.setText('0.1')

    def qt_chk(self):
        try:
            if not self.lineEdit_EChemQT.text() or float(self.lineEdit_EChemQT.text()) > 10 or float(
                    self.lineEdit_EChemQT.text()) < 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0 and 10""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_EChemQT.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0 and 10""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_EChemQT.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_EChemQT.setText('1')

    def sqt_chk(self):
        try:
            if not self.lineEdit_SampQT.text() or float(self.lineEdit_SampQT.text()) > 10 or float(
                    self.lineEdit_SampQT.text()) < 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0 and 10""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_SampQT.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0 and 10""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_SampQT.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_SampQT.setText('1')

    def sn_chk(self):
        try:
            if not self.lineEdit_SampNumbr.text() or float(self.lineEdit_SampNumbr.text()) > 10 or float(
                    self.lineEdit_SampNumbr.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 1 and 10""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_SampNumbr.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 1 and 10""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_SampNumbr.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_SampNumbr.setText('1')

    def st_chk(self):
        try:
            if not self.lineEdit_SampT.text() or float(self.lineEdit_SampT.text()) > 10 or float(
                    self.lineEdit_SampT.text()) < 0.1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0.1 and 10""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_SampT.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0.1 and 10""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_SampT.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_SampT.setText('1')

    def it_chk(self):
        try:
            if not self.lineEdit_IncubT.text() or float(self.lineEdit_IncubT.text()) > 180 or float(
                    self.lineEdit_IncubT.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 1 and 180""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_IncubT.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 1 and 180""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_IncubT.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_IncubT.setText('1')

    def pmv_chk(self):
        try:
            if not self.lineEdit_PmV.text() or float(self.lineEdit_PmV.text()) > 900 or float(
                    self.lineEdit_PmV.text()) < 100:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 100 and 900""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_PmV.setText('100')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 100 and 900""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_PmV.setText('100')
        except Exception as e:
            print(e)
            self.lineEdit_PmV.setText('100')

    def adcg_chk(self):
        try:
            if not self.lineEdit_adcGn.text() or int(self.lineEdit_adcGn.text()) not in [1, 2, 64, 128]:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value: 1, 2, 64, 128""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_adcGn.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value: 1, 2, 64, 128""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_adcGn.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_adcGn.setText('1')

    def adcs_chk(self):
        try:
            if not self.lineEdit_adcSpd.text() or int(self.lineEdit_adcSpd.text()) not in [1, 2]:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value: 1, 2""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_adcSpd.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value: 1, 2""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_adcSpd.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_adcSpd.setText('1')

    def sampling_mod_state(self):
        if self.checkBox_SampMod.isChecked():
            self.label_SampQT.setDisabled(False)
            self.label_SampT.setDisabled(False)
            self.label_SampNumbr.setDisabled(False)
            self.lineEdit_SampQT.setDisabled(False)
            self.lineEdit_SampT.setDisabled(False)
            self.lineEdit_SampNumbr.setDisabled(False)
            self.checkBox_IncubMod.setDisabled(True)
        else:
            self.label_SampQT.setDisabled(True)
            self.label_SampT.setDisabled(True)
            self.label_SampNumbr.setDisabled(True)
            self.lineEdit_SampQT.setDisabled(True)
            self.lineEdit_SampT.setDisabled(True)
            self.lineEdit_SampNumbr.setDisabled(True)
            self.checkBox_IncubMod.setDisabled(False)

        return

    def incubation_mod_state(self):
        if self.checkBox_IncubMod.isChecked():
            self.label_IncubT.setDisabled(False)
            self.lineEdit_IncubT.setDisabled(False)
            self.checkBox_SampMod.setDisabled(True)
            self.checkBox_DataSmt.setDisabled(True)
            self.checkBox_PmMod.setDisabled(True)
            self.checkBox_SigAmp.setDisabled(True)
            self.label_IP.setDisabled(True)
            self.label_FP.setDisabled(True)
            self.label_NS.setDisabled(True)
            self.label_PW.setDisabled(True)
            self.label_SI.setDisabled(True)
            self.label_EChemQT.setDisabled(True)
            self.lineEdit_IP.setDisabled(True)
            self.lineEdit_FP.setDisabled(True)
            self.lineEdit_NC.setDisabled(True)
            self.lineEdit_PW.setDisabled(True)
            self.lineEdit_SI.setDisabled(True)
            self.lineEdit_EChemQT.setDisabled(True)

        else:
            self.label_IncubT.setDisabled(True)
            self.lineEdit_IncubT.setDisabled(True)
            self.checkBox_SampMod.setDisabled(False)
            self.checkBox_DataSmt.setDisabled(False)
            self.checkBox_PmMod.setDisabled(False)
            self.checkBox_SigAmp.setDisabled(False)
            self.label_IP.setDisabled(False)
            self.label_FP.setDisabled(False)
            self.label_NS.setDisabled(False)
            self.label_PW.setDisabled(False)
            self.label_SI.setDisabled(False)
            self.label_EChemQT.setDisabled(False)
            self.lineEdit_IP.setDisabled(False)
            self.lineEdit_FP.setDisabled(False)
            self.lineEdit_NC.setDisabled(False)
            self.lineEdit_PW.setDisabled(False)
            self.lineEdit_SI.setDisabled(False)
            self.lineEdit_EChemQT.setDisabled(False)
        return

    def pm_mod_state(self):
        if self.checkBox_PmMod.isChecked():
            self.label_Vltg.setDisabled(False)
            self.lineEdit_PmV.setDisabled(False)
        else:
            self.label_Vltg.setDisabled(True)
            self.lineEdit_PmV.setDisabled(True)
        return

    def data_processing_mod_state(self):
        if self.checkBox_DataSmt.isChecked():
            self.comboBox_Smt.setDisabled(False)
            self.comboBox_ordrs.setDisabled(False)
            self.lineEdit_adcGn.setDisabled(False)
            self.lineEdit_adcSpd.setDisabled(False)
        else:
            self.comboBox_Smt.setDisabled(True)
            self.comboBox_ordrs.setDisabled(True)
            self.lineEdit_adcGn.setDisabled(True)
            self.lineEdit_adcSpd.setDisabled(True)
        return

    def sig_amp_mod_state(self):
        if self.checkBox_SigAmp.isChecked():
            self.label_adcGn.setDisabled(False)
            self.label_adcSpd.setDisabled(False)
            self.lineEdit_adcGn.setDisabled(False)
            self.lineEdit_adcSpd.setDisabled(False)
        else:
            self.label_adcGn.setDisabled(True)
            self.label_adcSpd.setDisabled(True)
            self.lineEdit_adcGn.setDisabled(True)
            self.lineEdit_adcSpd.setDisabled(True)
        return

    def wifi_check(self):
        self.textBrowser.append("Trying to establishing connection via Wifi...")
        response = os.system('ping -c 1 ' + board_ip)
        if response == 0:
            self.wifi_connection = True
        else:
            self.wifi_connection = False
        return self.wifi_connection

    def serial_check(self):
        try:
            self.textBrowser.append("Trying to establishing connection via serial ports...")
            # MacOs doesn't return tty! we'll find cu(calling unit) and then generating tty port from that! weird ha?!
            self.textBrowser.append("Scanning serial ports...")
            QtTest.QTest.qWait(1000)
            if lp.comports():
                self.textBrowser.append("Available ports:")
                serial_port = ""
                for idx, ports in enumerate(lp.comports()):
                    self.textBrowser.append("{}:  {}".format(idx, ports))
                    if "usbmodem" in str(ports.device) or "wch" in str(ports.device) or "SLAB" in str(ports.device):
                        serial_port = str(ports.device)
                QtTest.QTest.qWait(1000)

                if serial_port:
                    self.textBrowser.append("Initializing connection with the MinimalSens via Serial port...")
                    self.textBrowser.append("Serial port: " + green_font + serial_port + end_font)
                    QtTest.QTest.qWait(1000)

                    if "usbmodem" in serial_port:
                        serial_port = serial_port.replace("cu", "tty")
                    self.operator = serial.Serial(serial_port, baudrate=115200)
                    self.textBrowser.append("")
                    self.textBrowser.append("-" * 48)
                    self.serial_connection = True
                    QtTest.QTest.qWait(1000)

                else:
                    self.serial_connection = False
                    QtTest.QTest.qWait(1000)
                    self.textBrowser.append(
                        red_font + "No available serial connection with MinimalSens found! " + end_font)
            else:
                self.serial_connection = False
                QtTest.QTest.qWait(1000)
                self.textBrowser.append(red_font + "No available serial ports found! " + end_font)
            return self.serial_connection

        except Exception as e:
            self.serial_connection = False
            self.textBrowser.append(
                red_font + "No Serial connection found, switching to Wifi Mode..." + end_font + "\n")
            self.textBrowser.append(str(e) + "\n")
            return self.serial_connection

    def connection_module(self):
        self.actionConnection.setIcon(QtGui.QIcon(":/Icons/disconnect.icns"))

        self.serial_check()
        if self.serial_connection:
            self.textBrowser.append(
                cyan_font + "Connection with the MinimalSens is established via Serial port." + end_font)
            self.actionConnection.setIcon(QtGui.QIcon(":/Icons/connect.icns"))
        if not self.serial_connection:
            self.wifi_check()
            if self.wifi_connection:
                self.textBrowser.append(
                    cyan_font + "Connection with the MinimalSens is established via Wifi." + end_font)
                self.actionConnection.setIcon(QtGui.QIcon(":/Icons/connect.icns"))

            else:
                self.actionConnection.setIcon(QtGui.QIcon(":/Icons/connect.icns"))

                self.textBrowser.append(red_font + "Neither serial nor wifi connections were found." + end_font + "\n")
                msg = QtWidgets.QMessageBox()
                msg.setText("Communication with the" + blue_font +
                            " Minimal" + end_font + red_font + "Sens " + end_font + "was failed!\n" +
                            "please check your connections and try again.")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setWindowTitle("Warning")
                msg.exec_()

        # Dialog to send username and password
        # self.wifi_check()
        # # if self.wifi_connection:
        # msg = QtWidgets.QMessageBox()
        # button_reply = msg.question(self, 'Connection', "Do you have Wireless access to MinimalSens? Would you like to try Wifi connection?", msg.Yes | msg.No)
        # if button_reply == msg.Yes:
        #     print("Wifi YES")
        #     login = Login()
        #
        #     if login.exec_() == QtWidgets.QDialog.Accepted:
        #         print("password Accepted")
        #
        # else:
        #     print("No")
        # # msg.exec_()

    def serial_sndr_recvr(self, command):
        delay = 1000  # in ms
        print('Waiting for invitation', end='')
        while b's_thread: READY.\n' not in self.operator.read_all():
            print('.', end='')
            QtTest.QTest.qWait(delay)
        print('\nInvited, sending GO!')

        while b'got it!\n' not in self.operator.read_all():
            self.operator.write('go#'.encode())
            QtTest.QTest.qWait(delay)

        pck_size_tot = 0
        t0 = time.time()

        def chunker(cmd):
            # return [cmd[i:i + self.pck_size] for i in range(0, len(cmd), self.pck_size)]
            data = []
            segments = [cmd[i:i + self.packet_size] for i in range(0, len(cmd), self.packet_size)]
            for segment in segments:
                if segment == segments[-1]:
                    data.append(segment + '*#')
                else:
                    data.append(segment + '_#')
            return data

        try:
            if len(command) > self.packet_size:
                print('Data larger than {} chars, calling Chunker...'.format(self.packet_size))
                for idx, data in enumerate([chunk for chunk in chunker(command)]):
                    print('packet[{}]: {} --- length: {} chars --- size: {}'.format(idx, data, len(data),
                                                                                    sys.getsizeof(data)))
                    self.operator.write(data.encode())
                    QtTest.QTest.qWait(delay)
                    resp = self.operator.read_all()
                    if 'EOF received.\n' in resp.decode():
                        print('_MinimalSens: EOF received in first run, file was sent successfully.')
                        pck_size_tot += sys.getsizeof(data)
                    elif b'got it!\n' in resp:
                        print('packet [{}] received on the first try.'.format(idx))
                        pck_size_tot += sys.getsizeof(data)
                    else:
                        print('sending packet again: {}', end='')
                        while True:
                            print('.', end='')
                            self.operator.write(data.encode())
                            QtTest.QTest.qWait(delay)
                            resp = self.operator.read_all()
                            # print(resp)
                            if 'EOF received.\n' in resp.decode():
                                print('EOF received in retry')
                                pck_size_tot += sys.getsizeof(data)
                                break
                            elif b'got it!\n' in resp:
                                print('packet sent in retry.')
                                pck_size_tot += sys.getsizeof(data)
                                break
                            else:
                                QtTest.QTest.qWait(delay)
                                pass
                        print('packet received eventually.')

            else:
                print('Data not larger than {} chars, no need to call Chunker.'.format(self.packet_size))
                self.operator.write(command.encode())
                QtTest.QTest.qWait(delay)
                resp = self.operator.read_all()
                if 'EOF received.\n' in resp.decode():
                    print('\n_MinimalSens: EOF received on the first try.')
                    pck_size_tot += sys.getsizeof(command)
                elif b'got it!\n' in resp:
                    print('\n_MinimalSens: packet received on the first try.')
                    pck_size_tot += sys.getsizeof(command)
                else:
                    print('sending packet again', end='')
                    while True:
                        self.operator.write(command.encode())
                        print('.', end='')
                        QtTest.QTest.qWait(delay)
                        resp = self.operator.read_all()
                        if 'EOF received.\n' in resp.decode():
                            print('\n_MinimalSens: EOF received in retry.')
                            pck_size_tot += sys.getsizeof(command)
                            break
                        elif b'got it!\n' in self.operator.read_all():
                            print('\n_MinimalSens: packet sent in retry.')
                            pck_size_tot += sys.getsizeof(command)
                            break
                        else:
                            QtTest.QTest.qWait(delay)
                            pass
                    print('Packet received eventually.')

            print('{} seconds for {} bytes to be transferred.'.format((time.time() - t0), pck_size_tot))
            print('Receiving', end='')

            while '*' not in self.content:
                try:
                    QtTest.QTest.qWait(delay)
                    data = self.operator.read_all()
                    data_decd = data.decode()
                    if '#' in data_decd and data_decd[:-2] not in self.content:
                        if data_decd[-2] == '*':
                            self.content += data_decd[:-1]
                            print('Done!')
                            break
                        elif data_decd[-2] == '_':
                            self.content += data_decd[:-2]
                            self.operator.write('got it!\n'.encode())
                            print('.', end='')
                            # QtTest.QTest.qWait(delay)
                        else:
                            pass
                    else:
                        QtTest.QTest.qWait(delay)
                        pass
                except:
                    pass
            print('\nResponse: {}'.format(self.content))
            if '*' in self.content:
                self.operator.write('EOF received.\n'.encode())
                # print('Content: {}\n'.format(content))
                # print('length: {} chars\n'.format(len(content)))
                raw_cmd = open('resp.txt', 'w')
                raw_cmd.write(self.content[:-1])
                raw_cmd.close()
                print('Response file is saved.')
                print('Processing the response.')
                with open('resp.txt', 'r') as f:
                    for line in f:
                        if eval(line)['header'] == 'test_asteroid':
                            print('Asteroid list is received, illustrating...')
                            self.test_A(eval(line)['body'])
                        if eval(line)['header'] == 'run_incubator':
                            print('_MinimalSens: {}'.format(eval(line)['body']))
        except KeyboardInterrupt:
            print('Aborted!')
        except Exception as e:
            print(e)
        print('Done.')
        return

    def wifi_sndr_recr(self, command):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((board_ip, board_port))
            # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            #     sock.connect((board_ip, board_port))
            self.textBrowser.append("sending out wifi invitation signal...")
            QtTest.QTest.qWait(1000)

            sock.sendall(command)

            def recvall(sock):
                BUFF_SIZE = 4096  # 4 KiB
                data = b''
                while True:
                    part = sock.recv(BUFF_SIZE)
                    data += part
                    if len(part) < BUFF_SIZE:
                        # either 0 or end of data.py
                        break
                return data

            data = recvall(sock)

            if "body" not in data.decode():
                attempts = 0
                while attempts < 5:
                    print("{}/5 attempt failed...re-trying.".format(attempts))
                    sock.sendall('a'.encode())
                    print("test command is sent.")
                    data = sock.recv(1024)
                    QtTest.QTest.qWait(1000)
                    if "body" in data.decode():
                        break
                    else:
                        attempts += 1

            parsed_data = json.loads(data.decode())
            self.test_A(parsed_data["body"])

        except Exception as e:
            print(e)

        except KeyboardInterrupt:
            print("Aborted!")

    def test_A(self, list_t):
        try:
            self.graphicsView.clear()
            p2 = self.graphicsView.addPlot()
            p2.showAxis('right', show=True)
            p2.showAxis('top', show=True)
            for _ in range(1):
                for i in range(len(list_t)):
                    p2.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][1], pen=pg.mkPen((i, 2), width=1))
                    QtTest.QTest.qWait(10)
                    p2.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][2], pen=pg.mkPen((i, 2), width=1))
                    QtTest.QTest.qWait(10)
                QtTest.QTest.qWait(3000)
                for i in reversed(range(len(list_t))):
                    p2.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][1], pen=pg.mkPen('k', width=1))
                    QtTest.QTest.qWait(10)
                    p2.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][2], pen=pg.mkPen('k', width=1))
                    QtTest.QTest.qWait(10)
            self.textBrowser.append("Software just had a successful talk with the" + blue_font +
                                    " Minimal" + end_font + red_font + "Sens" + end_font + " via Wifi.")
            self.textBrowser.append("-" * 57)
            p2.clear()
            p2.showGrid(x=True, y=True, alpha=1)
            return
        except Exception as e:
            print(e)

    def run_test(self):
        command = ({'header': 'test'})
        command.update({'body': {'it': 20}})
        jsnd_cmd = json.dumps(command)
        jsnd_cmd += '*#'

        if self.serial_connection:
            self.serial_sndr_recvr(jsnd_cmd)

        elif self.wifi_connection:
            self.wifi_sndr_recr(jsnd_cmd)

        else:
            self.textBrowser.append("No available connections to the MinimalSens.")
            self.textBrowser.append("Please re-establish your connection first.")
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the" + blue_font +
                        " Minimal" + end_font + red_font + "Sens!" + end_font + "\n" +
                        "please check your connections and try again.")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setWindowTitle("Warning")
            msg.exec_()
        return

    def run(self):
        command = ({'header': 'run'})
        command.update(
            {'body': {'ip': float(self.lineEdit_IP.text()) if not self.checkBox_IncubMod.isChecked() else '',
                      'fp': float(self.lineEdit_FP.text()) if not self.checkBox_IncubMod.isChecked() else '',
                      'nc': float(self.lineEdit_NC.text()) if not self.checkBox_IncubMod.isChecked() else '',
                      'pw': float(self.lineEdit_PW.text()) if not self.checkBox_IncubMod.isChecked() else '',
                      'si': float(self.lineEdit_SI.text()) if not self.checkBox_IncubMod.isChecked() else '',
                      'eqt': float(
                          self.lineEdit_EChemQT.text()) if not self.checkBox_IncubMod.isChecked() else '',

                      'sqt': float(self.lineEdit_SampQT.text()) if self.checkBox_SampMod.isChecked() else '',
                      'sn': float(self.lineEdit_SampNumbr.text()) if self.checkBox_SampMod.isChecked() else '',
                      'st': float(self.lineEdit_SampT.text()) if self.checkBox_SampMod.isChecked() else '',

                      'it': float(self.lineEdit_IncubT.text()) if self.checkBox_IncubMod.isChecked() else '',

                      'pv': int(self.lineEdit_PmV.text()) if self.checkBox_PmMod.isChecked() else '',

                      'ag': int(self.lineEdit_adcGn.text()) if self.checkBox_SigAmp.isChecked() else 1,
                      'as': int(self.lineEdit_adcSpd.text()) if self.checkBox_SigAmp.isChecked() else 1,
                      }})
        jsnd_cmd = json.dumps(command)
        # print('collected command parameters.')

        if self.serial_connection:
            # print('Sending command via serial port...')
            self.serial_sndr_recvr(jsnd_cmd)

        elif self.wifi_connection:
            print('Sending command via wifi port...')
            self.wifi_sndr_recr(jsnd_cmd)

        else:
            self.textBrowser.append("No available connections to the MinimalSens.")
            self.textBrowser.append("Please re-establish your connection first.")
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the" + blue_font +
                        " Minimal" + end_font + red_font + "Sens!" + end_font + "\n" +
                        "please check your connections and try again.")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

    def about_us(self):
        msg = QtWidgets.QMessageBox()
        msg.setText("""
        Copyright © 2019 MinimalSens(M. Amin Haghighatbin)

        This software is under MIT License.

        Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.""")
        msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        msg.setWindowTitle("About Us")
        msg.exec_()

    def help(self):
        msg = QtWidgets.QMessageBox()
        msg.setText("Can't help you mate, you're done!")
        msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        msg.setWindowTitle("Help")
        msg.exec_()

    def new(self):
        self.graphicsView.clear()
        p0 = self.graphicsView.addPlot()
        p0.showGrid(x=True, y=True, alpha=1)
        self.tableWidget.clear()
        self.setText("Plot is now cleared.")

    def exit(self):
        msg = QtWidgets.QMessageBox()
        msg.setText("Are you sure you want to exit?")
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        msg.setIcon(QtWidgets.QMessageBox.Warning)  # Information - Critical - Question
        msg.exec_()
        if msg.clickedButton() == msg.button(QtWidgets.QMessageBox.Yes):
            sys.exit(0)
        elif msg.clickedButton() == msg.button(QtWidgets.QMessageBox.No):
            msg.close()

    def open(self):

        dir = "/Users/aminhb/Desktop/"
        open_file_obj = QtWidgets.QFileDialog.getOpenFileName(caption=__APPNAME__ + "QDialog Open File", directory=dir,
                                                              filter="Text Files (*.csv)")
        # self.importTable(open_file_obj)
        self.title = "".join((open_file_obj[0]).split('/')[-1:])

    def import_table(self, dataFile):
        self.tableWidget.setHorizontalHeaderLabels(['x', 'y'])
        with open(dataFile[0]) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')

            for idx, cols in enumerate(csv_reader):
                try:
                    value_x = float(cols[0])
                    item_x = QtWidgets.QTableWidgetItem()
                    item_x.setData(QtCore.Qt.EditRole, value_x)
                    self.tableWidget.setItem(idx, 0, item_x)
                except Exception as e:
                    print(e)
                    print("Error is handled: String values were removed from the table." + '\n')

                try:
                    value_y = float(cols[1])
                    item_y = QtWidgets.QTableWidgetItem()
                    item_y.setData(QtCore.Qt.EditRole, value_y)
                    self.tableWidget.setItem(idx, 1, item_y)
                except Exception as e:
                    print(e)
                    print("Error is handled: String values were removed from the table." + '\n')

        # if self.tableWidget.currentItem() is None:
        #     self.tableWidget.removeRow(self.tableWidget.currentRow())
        # print(self.tableWidget.rowCount())
        self.tableWidget.setRowCount(idx + 1)
        self.setText("Datafile is imported to the table.")

    def plot_data(self):
        self.graphicsView.clear()
        data_x, data_y = [], []
        for col in range(self.tableWidget.columnCount()):
            for row in range(self.tableWidget.rowCount()):
                try:
                    if col == 0:
                        data_x.append(float(self.tableWidget.item(row, 0).text()))
                    elif col == 1:
                        data_y.append(float(self.tableWidget.item(row, 1).text()))
                except Exception as e:
                    print(e)
                    print("Error is handled: NoneType values were removed." + '\n')
        area = trapz(data_y, dx=(data_x[2] - data_x[1]))

        p1 = self.graphicsView.addPlot(title="Normal Distribution", x=data_x, y=data_y, pen='r')
        p1.showGrid(x=True, y=True, alpha=1)
        p1.setLabel('bottom', 'x', **{'color': 'white', 'font-size': '12px'})
        p1.setLabel('left', 'f(x)', **{'color': 'white', 'font-size': '12px'})
        self.setText("{} is now presented.".format(self.title))

        if self.AreaBox.isChecked():
            self.setText("The Area under curve is equal to: {}".format(area))
            self.graphicsView.clear()
            p2 = self.graphicsView.addPlot(title=self.title, x=data_x, y=data_y, pen='r', fillLevel=0, fillBrush="b")
            p2.showGrid(x=True, y=True, alpha=1)
            p2.setLabel('bottom', 'x', **{'color': 'white', 'font-size': '12px'})
            p2.setLabel('left', 'f(x)', **{'color': 'white', 'font-size': '12px'})


class MySplashScreen(QtWidgets.QSplashScreen):

    def __init__(self, animation, flags):
        QtWidgets.QSplashScreen.__init__(self, QtGui.QPixmap(), flags)

        self.movie = QtGui.QMovie(animation)
        self.movie.setScaledSize(QtCore.QSize(350, 250))
        size = self.movie.scaledSize()
        self.movie.frameChanged.connect(self.onNextFrame)
        self.movie.start()

    @pyqtSlot()
    def onNextFrame(self):
        pixmap = self.movie.currentPixmap()
        self.setPixmap(pixmap)
        self.setMask(pixmap.mask())


# class Login(QtWidgets.QDialog):
#     def __init__(self, parent=None):
#         super(Login, self).__init__(parent)
#         self.label_user = QtWidgets.QLabel(self)
#         self.label_user.setText("Username: ")
#         self.label_pass = QtWidgets.QLabel(self)
#         self.label_pass.setText("Password: ")
#         self.textName = QtWidgets.QLineEdit(self)
#         self.textPass = QtWidgets.QLineEdit(self)
#         self.buttonLogin = QtWidgets.QPushButton('Login', self)
#         self.buttonLogin.clicked.connect(self.handleLogin)
#         layout = QtWidgets.QGridLayout(self)
#         layout.addWidget(self.label_user)
#         layout.addWidget(self.textName)
#         layout.addWidget(self.label_pass)
#         layout.addWidget(self.textPass)
#         layout.addWidget(self.buttonLogin)
#
#
#     def handleLogin(self):
#         if self.textName.text() == 'foo' and self.textPass.text() == 'bar':
#             self.accept()
#         else:
#             QtWidgets.QMessageBox.warning(self, 'Error', 'Bad user or password')


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(
        QtGui.QIcon("/Users/aminhb/PycharmProjects/MinimalSensGUI_v0.01/MinimalSensGUI_v0.01/Icons/miniamlsens.icns"))

    # splash = MySplashScreen("/Users/aminhb/PycharmProjects/MinimalSensGUI_v0.01/MinimalSensGUI_v0.01/Logo_Splash.gif", QtCore.Qt.WindowStaysOnTopHint)
    # splash.setMask(splash.mask())
    # splash.raise_()
    # splash.show()
    #
    # initLoop = QtCore.QEventLoop()
    # QtCore.QTimer.singleShot(9000, initLoop.quit)
    # initLoop.exec_()
    #
    # splash.close()

    form = Form()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    form.show()
    # splash.finish(form)
    app.exec_()
