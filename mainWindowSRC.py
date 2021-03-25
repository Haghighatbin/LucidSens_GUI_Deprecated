import sys, os, time, json, serial, socket
from PyQt5 import QtWidgets, QtTest, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, pyqtSignal
import pyqtgraph as pg
import matplotlib.pyplot as plt
import numpy as np
import serial.tools.list_ports as lp
import csv
import qdarkstyle
import threading
import traceback

import mainWindowGUI

# Default IP/Port on LucidSens 
board_ip = "192.168.1.95"
board_port = 3175
__APPNAME__ = "LucidSens"
VERSION = "0.02"

class WorkerSignals(QtCore.QObject):
    '''
    Defined Signals for the Worker thread:
    DONE: -> None
    ERROR: tuple -> (exctype, value, traceback.format_exc())
    OUTPUT: depends
    PROGRESS: int -> (progress in %)
    '''
    DONE = pyqtSignal()
    ERROR = pyqtSignal(tuple)
    OUTPUT = pyqtSignal(object)
    PROGRESS = pyqtSignal(int)

class Worker(QtCore.QRunnable):
    ''' Worker thread '''
    def __init__(self, method, *args, **kwargs):
        super(Worker, self).__init__()
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        if self.kwargs:
            self.kwargs['progress_status'] = self.signals.PROGRESS

    @pyqtSlot()
    def run(self):
        '''Worker thread runner method'''
        try:
            output = self.method(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.ERROR.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.OUTPUT.emit(output) 
        finally:
            self.signals.DONE.emit()

class Form(QtWidgets.QMainWindow, mainWindowGUI.Ui_MainWindow):
    def __init__(self, parent=None):
        super(Form, self).__init__(parent)

        self.packet_size = 128
        self.content = ''
        self.timer = QtCore.QTimer()
        self.threadpool = QtCore.QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

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
        self.actionConnection.triggered.connect(self.connection_status)
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
        self.textBrowser.append("<font size='4' color='blue'>" + "Lucid" + "</font>" + "<font size='4' color='orange'>" + "Sens" + "</font>" + "<font size='2' color='white'>" + " (Chemiluminescence-wing)" + "</font>")
        intro_txt = """\nVersion {}\nDeveloped by M. Amin Haghighatbin\n中国科学技术大学\nUniversity of Science and Technology of China (USTC)\n---------------------------------------------------------------""".format(VERSION)
        self.checkBox_SampMod.stateChanged.connect(self.sampling_mod_status)
        self.checkBox_IncubMod.stateChanged.connect(self.incubation_mod_status)
        self.checkBox_PMMod.stateChanged.connect(self.pm_mod_status)
        self.checkBox_DataSmth.stateChanged.connect(self.data_processing_mod_status)

        # # EChem Settings
        # self.lineEdit_InitE.editingFinished.connect(self.EChemSettings().ip_chk())
        # self.lineEdit_FinalE.editingFinished.connect(self.EChemSettings().fp_chk())
        # self.lineEdit_NS.editingFinished.connect(self.EChemSettings().nc_chk())
        # self.lineEdit_PulseWidth.editingFinished.connect(self.EChemSettings.pw_chk())
        # self.lineEdit_SampleIntrvl.editingFinished.connect(self.EChemSettings().esi_chk())
        # self.lineEdit_EQuietTime.editingFinished.connect(self.EChemSettings().eqt_chk())
        
        # Sampling Mode
        self.lineEdit_SampQuietTime.editingFinished.connect(self.SamplingMode().sqt_chk)
        self.lineEdit_NumbSamps.editingFinished.connect(self.SamplingMode().sn_chk)
        self.lineEdit_SampTime.editingFinished.connect(self.SamplingMode().st_chk)
        self.lineEdit_SampleIntrvl.editingFinished.connect(self.SamplingMode().csi_chk)
        self.lineEdit_Raw2Avrg.editingFinished.connect(self.SamplingMode().r2avg_chk)

        # Incubation Mode
        self.lineEdit_IncubTime.editingFinished.connect(self.IncubationMode().itm_chk)
        self.lineEdit_IncubTemp.editingFinished.connect(self.IncubationMode().itp_chk)
        self.comboBox_BlowerStat.currentIndexChanged.connect(self.IncubationMode().bf_chk)

        # Photodetection Settings
        self.lineEdit_PMV.editingFinished.connect(self.PhotodetectionSettings().pmv_chk)
        self.comboBox_SampReadMod.currentIndexChanged.connect(self.PhotodetectionSettings().adcr_chk)
        self.lineEdit_ADCGain.editingFinished.connect(self.PhotodetectionSettings().adcg_chk)
        self.lineEdit_ADCSpd.editingFinished.connect(self.PhotodetectionSettings().adcs_chk)

        # Data Smooting
        self.comboBox_SGorders.currentIndexChanged.connect(self.DataSmoothing().smth_chk)

        worker_intro = Worker(self.writer, intro_txt, color='yellow')
        self.threadpool.start(worker_intro)

    def writer(self, txt, progress_status, font_size=8, color='green', delay=10):
        for idx, char in enumerate(txt):
            self.textBrowser.setTextColor(QtGui.QColor('{}'.format(color)))
            self.textBrowser.setFontPointSize(10)
            self.textBrowser.insertPlainText(char)
            QtTest.QTest.qWait(delay)
        
    def pen(self, size, color):
        return "<font size='{}' color='{}'>".format(size, color)
       
    def sampling_mod_status(self):
        if self.checkBox_SampMod.isChecked():
            self.label_SampQuietT.setDisabled(False)
            self.label_NoSamp.setDisabled(False)
            self.label_SampT.setDisabled(False)
            self.label_SampIntrvls.setDisabled(False)
            self.label_Raw2Avrg.setDisabled(False)
            self.lineEdit_SampQuietTime.setDisabled(False)
            self.lineEdit_NumbSamps.setDisabled(False)
            self.lineEdit_SampTime.setDisabled(False)
            self.lineEdit_SampIntrvls.setDisabled(False)
            self.lineEdit_Raw2Avrg.setDisabled(False)
            self.checkBox_IncubMod.setDisabled(True)
        else:   
            self.label_SampQuietT.setDisabled(True)
            self.label_NoSamp.setDisabled(True)
            self.label_SampT.setDisabled(True)
            self.label_SampIntrvls.setDisabled(True)
            self.label_Raw2Avrg.setDisabled(True)
            self.lineEdit_SampQuietTime.setDisabled(True)
            self.lineEdit_NumbSamps.setDisabled(True)
            self.lineEdit_SampTime.setDisabled(True)
            self.lineEdit_SampIntrvls.setDisabled(True)
            self.lineEdit_Raw2Avrg.setDisabled(True)
            self.checkBox_IncubMod.setDisabled(False)

    def incubation_mod_status(self):
        if self.checkBox_IncubMod.isChecked():
            self.label_IncubTime.setDisabled(False)
            self.lineEdit_IncubTime.setDisabled(False)
            self.label_IncubTemp.setDisabled(False)
            self.lineEdit_IncubTemp.setDisabled(False)
            self.label_Blower.setDisabled(False)
            self.comboBox_BlowerStat.setDisabled(False)
            self.checkBox_SampMod.setDisabled(True)
            self.checkBox_DataSmth.setDisabled(True)
            self.checkBox_PMMod.setDisabled(True)
            # self.checkBox_EChemMod.setDisabled(True)
            # self.label_IP.setDisabled(True)
            # self.label_FP.setDisabled(True)
            # self.label_NS.setDisabled(True)
            # self.label_PW.setDisabled(True)
            # self.label_SI.setDisabled(True)
            # self.label_EChemQuietT.setDisabled(True)
            # self.lineEdit_IP.setDisabled(True)
            # self.lineEdit_FP.setDisabled(True)
            # self.lineEdit_NS.setDisabled(True)
            # self.lineEdit_PW.setDisabled(True)
            # self.lineEdit_SI.setDisabled(True)
            # self.lineEdit_EQuietTime.setDisabled(True)

        else:
            self.label_IncubTime.setDisabled(True)
            self.lineEdit_IncubTime.setDisabled(True)
            self.label_IncubTemp.setDisabled(True)
            self.lineEdit_IncubTemp.setDisabled(True)
            self.label_Blower.setDisabled(True)
            self.comboBox_BlowerStat.setDisabled(True)
            self.checkBox_SampMod.setDisabled(False)
            self.checkBox_DataSmth.setDisabled(False)
            self.checkBox_PMMod.setDisabled(False)
            # self.checkBox_EChemMod.setDisabled(False)
            # self.label_IP.setDisabled(False)
            # self.label_FP.setDisabled(False)
            # self.label_NS.setDisabled(False)
            # self.label_PW.setDisabled(False)
            # self.label_SI.setDisabled(False)
            # self.label_EChemQuietT.setDisabled(False)
            # self.lineEdit_IP.setDisabled(False)
            # self.lineEdit_FP.setDisabled(False)
            # self.lineEdit_NC.setDisabled(False)
            # self.lineEdit_PW.setDisabled(False)
            # self.lineEdit_SI.setDisabled(False)
            # self.lineEdit_EQuietTime.setDisabled(False)

    def pm_mod_status(self):
        if self.checkBox_PMMod.isChecked():
            self.label_SampReadMod.setDisabled(False)
            self.comboBox_SampReadMod.setDisabled(False)
            self.label_Vltg.setDisabled(False)
            self.lineEdit_PMV.setDisabled(False)
            self.label_adcG.setDisabled(False)
            self.label_adcS.setDisabled(False)
            self.lineEdit_ADCGain.setDisabled(False)
            self.lineEdit_ADCSpd.setDisabled(False)
        else:
            self.label_SampReadMod.setDisabled(True)
            self.comboBox_SampReadMod.setDisabled(True)
            self.label_Vltg.setDisabled(True)
            self.lineEdit_PMV.setDisabled(True)
            self.label_adcG.setDisabled(True)
            self.label_adcS.setDisabled(True)
            self.lineEdit_ADCGain.setDisabled(True)
            self.lineEdit_ADCSpd.setDisabled(True)

    def data_processing_mod_status(self):
        if self.checkBox_DataSmth.isChecked():
            self.comboBox_Smt.setDisabled(False)
            self.comboBox_SGorders.setDisabled(False)

        else:
            self.comboBox_Smt.setDisabled(True)
            self.comboBox_SGorders.setDisabled(True)
    
    # class EChemSettings():
        # def ip_chk(self):
        #     try:
        #         if not self.lineEdit_IP.text() or float(self.lineEdit_IP.text()) > 2.9 or float(
        #                 self.lineEdit_IP.text()) < 0:
        #             raise ValueError
        #     except ValueError:
        #         msg = QtWidgets.QMessageBox()
        #         msg.setText("""Please enter a valid value between 0 and 2.9""")
        #         msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #         msg.setIcon(QtWidgets.QMessageBox.Warning)
        #         msg.exec_()
        #         self.lineEdit_IP.setText('0.0')
        #     except Exception as e:
        #         print(e)
        #         self.lineEdit_IP.setText('0.0')

        # def fp_chk(self):
        #     try:
        #         if not self.lineEdit_FP.text() or float(self.lineEdit_FP.text()) > 3 or float(
        #                 self.lineEdit_FP.text()) < 0:
        #             raise ValueError
        #     except ValueError:
        #         msg = QtWidgets.QMessageBox()
        #         msg.setText("""Please enter a valid value between 0 and 3""")
        #         msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #         msg.setIcon(QtWidgets.QMessageBox.Warning)
        #         msg.exec_()
        #         self.lineEdit_FP.setText('0.0')

        #     except Exception as e:
        #         print(e)
        #         self.lineEdit_FP.setText('0.0')

        # def nc_chk(self):
        #     try:
        #         if not self.lineEdit_NC.text() or float(self.lineEdit_NC.text()) > 10 or float(
        #                 self.lineEdit_NC.text()) < 1:
        #             msg = QtWidgets.QMessageBox()
        #             msg.setText("""Please enter a valid value between 1 and 10""")
        #             msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #             msg.setIcon(QtWidgets.QMessageBox.Warning)
        #             msg.exec_()
        #             self.lineEdit_NC.setText('1')
        #     except ValueError:
        #         msg = QtWidgets.QMessageBox()
        #         msg.setText("""Please enter a valid value between 1 and 10""")
        #         msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #         msg.setIcon(QtWidgets.QMessageBox.Warning)
        #         msg.exec_()
        #         self.lineEdit_NC.setText('1')
        #     except Exception as e:
        #         print(e)
        #         self.lineEdit_NC.setText('1')

        # def pw_chk(self):
        #     try:
        #         if not self.lineEdit_PW.text() or float(self.lineEdit_PW.text()) > 10 or float(
        #                 self.lineEdit_PW.text()) < 1:
        #             msg = QtWidgets.QMessageBox()
        #             msg.setText("""Please enter a valid value between 1 and 10""")
        #             msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #             msg.setIcon(QtWidgets.QMessageBox.Warning)
        #             msg.exec_()
        #             self.lineEdit_PW.setText('1')
        #     except ValueError:
        #         msg = QtWidgets.QMessageBox()
        #         msg.setText("""Please enter a valid value between 1 and 10""")
        #         msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #         msg.setIcon(QtWidgets.QMessageBox.Warning)
        #         msg.exec_()
        #         self.lineEdit_PW.setText('1')
        #     except Exception as e:
        #         print(e)
        #         self.lineEdit_PW.setText('1')

        # def esi_chk(self):
        #     try:
        #         if not self.lineEdit_SI.text() or float(self.lineEdit_SI.text()) > 1.001 or float(
        #                 self.lineEdit_SI.text()) < 0.001:
        #             msg = QtWidgets.QMessageBox()
        #             msg.setText("""Please enter a valid value between 0.001 and 1.1""")
        #             msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #             msg.setIcon(QtWidgets.QMessageBox.Warning)
        #             msg.exec_()
        #             self.lineEdit_SI.setText('0.1')
        #     except ValueError:
        #         msg = QtWidgets.QMessageBox()
        #         msg.setText("""Please enter a valid value between 0.001 and 1.1""")
        #         msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #         msg.setIcon(QtWidgets.QMessageBox.Warning)
        #         msg.exec_()
        #         self.lineEdit_SI.setText('0.1')
        #     except Exception as e:
        #         print(e)
        #         self.lineEdit_SI.setText('0.1')

        # def eqt_chk(self):
        #     try:
        #         if not self.lineEdit_EChemQT.text() or float(self.lineEdit_EChemQT.text()) > 10 or float(
        #                 self.lineEdit_EChemQT.text()) < 0:
        #             msg = QtWidgets.QMessageBox()
        #             msg.setText("""Please enter a valid value between 0 and 10""")
        #             msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #             msg.setIcon(QtWidgets.QMessageBox.Warning)
        #             msg.exec_()
        #             self.lineEdit_EChemQT.setText('1')
        #     except ValueError:
        #         msg = QtWidgets.QMessageBox()
        #         msg.setText("""Please enter a valid value between 0 and 10""")
        #         msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        #         msg.setIcon(QtWidgets.QMessageBox.Warning)
        #         msg.exec_()
        #         self.lineEdit_EChemQT.setText('1')
        #     except Exception as e:
        #         print(e)
        #         self.lineEdit_EChemQT.setText('1')

    class SamplingMode():
        def sqt_chk(self):
            try:
                if not self.lineEdit_SampQuietTime.text() or float(self.lineEdit_SampQuietTime.text()) > 10 or float(
                        self.lineEdit_SampQuietTime.text()) < 0:
                    msg = QtWidgets.QMessageBox()
                    msg.setText("""Please enter a valid value between 0 and 10""")
                    msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                    msg.setIcon(QtWidgets.QMessageBox.Warning)
                    msg.exec_()
                    self.lineEdit_SampQuietTime.setText('1')
            except ValueError:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0 and 10""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_SampQuietTime.setText('1')
            except Exception as e:
                print(e)
                self.lineEdit_SampQuietTime.setText('1')

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

        def csi_chk(self):
            pass
        
        def r2avg_chk(self):
            pass
    
    class IncubationMode():
        def itm_chk(self):
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

        def itp_chk(self):
            pass

        def bf_chk(self):
            pass

    class PhotodetectionSettings():

        def adcr_chk(self):
            pass
            
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
        
    class DataSmoothing():
        def smth_chk(self):
            pass 
 
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
            if lp.comports():
                for idx, port in enumerate(lp.comports()):

                    # in MAC OS
                    if "usbmodem" in str(port.device) or "wch" in str(port.device) or "SLAB" in str(port.device):
                        serial_port = str(port.device)
                        serial_port = serial_port.replace("cu", "tty")

                    # in Windows OS
                    if "CP210x" in str(port):
                        serial_port = str(port.device)

                worker_serial = Worker(self.writer,"\nEstablishing connection via serial port\nScanning serial ports...\nAvailable port: {}\n".format(serial_port), color='green')
                self.threadpool.start(worker_serial)
                if serial_port:
                    # worker_serial2 = Worker(self.writer, "Connection established.\n--------------------------------------".format(serial_port))
                    # self.timer.singleShot(6000, lambda: self.threadpool.start(worker_serial2))
                    self.operator = serial.Serial(serial_port, baudrate=115200)
                    self.serial_connection = True

                else:
                    self.serial_connection = False
                    self.timer.singleShot(1000, lambda: self.textBrowser.append(
                        self.pen(2, 'red') + "Failed to communicate via Serial port!" + "</font>"))
                    
            else:
                self.serial_connection = False
                self.timer.singleShot(1000, self.textBrowser.append(self.pen(2, 'red') + "Failed to find any available Serial ports! " + "</font>"))
                
            return self.serial_connection
        except Exception as e:
            self.serial_connection = False
            self.textBrowser.append(
            self.pen(2, 'red') + "Failed to communicate via Serial!" + "</font>")
            self.textBrowser.append(str(e) + "\n")
            return self.serial_connection

    def connection_status(self):
        self.actionConnection.setIcon(QtGui.QIcon(":/Icons/disconnect.icns"))

        self.serial_check()
        if self.serial_connection:
            self.timer.singleShot(5000, lambda: self.textBrowser.append(
                self.pen(2, 'cyan') + "Connection established via Serial port." + "</font>"))
            
            self.actionConnection.setIcon(QtGui.QIcon(":/Icons/connect.icns"))
        if not self.serial_connection:
            self.wifi_check()
            if self.wifi_connection:
                self.textBrowser.append(
                    self.pen(2, 'cyan') + "Wifi connection established." + "</font>")
                self.actionConnection.setIcon(QtGui.QIcon(":/Icons/connect.icns"))

            else:
                self.actionConnection.setIcon(QtGui.QIcon(":/Icons/disconnect.icns"))

                self.textBrowser.append(self.pen(2, 'red') + "Neither serial nor wifi connections were found." + "</font>" + "\n")
                msg = QtWidgets.QMessageBox()
                msg.setText("Communication with " + self.pen(2, 'blue') +
                            " Minimal" + "</font>" + self.pen(2, 'orange') + "Sens " + "</font>" + "was failed!\n" +
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
        while b'sr_receiver: READY\n' not in self.operator.read_all():
            print('.', end='')
            QtTest.QTest.qWait(delay)
        print('\nInvited, sending GO!')

        while b'got it.\n' not in self.operator.read_all():
            self.operator.write('go#'.encode())
            QtTest.QTest.qWait(delay)

        pck_size_tot = 0
        t0 = time.time()

        def chopper(cmd):
            # return [cmd[i:i + self.pck_size] for i in range(0, len(cmd), self.pck_size)]
            data = []
            segments = [cmd[i:i + self.packet_size] for i in range(0, len(cmd), self.packet_size)]
            for segment in segments:
                if segment == segments[-1]:
                    data.append(segment + '*#')
                else:
                    data.append(segment + '_#')
            return data

        ### SENDER ###
        try:
            if len(command) > self.packet_size:
                print('Data larger than {} chars, calling Chunker...'.format(self.packet_size))
                for idx, data in enumerate([chunk for chunk in chopper(command)]):
                    print('packet[{}]: {} --- length: {} chars --- size: {}'.format(idx, data, len(data),
                                                                                    sys.getsizeof(data)))
                    self.operator.write(data.encode())
                    QtTest.QTest.qWait(delay)
                    resp = self.operator.read_all()
                    print(resp)
                    if 'EOF received.\n' in resp.decode():
                        print('_LucidSens: EOF received in first run, file was sent successfully.')
                        pck_size_tot += sys.getsizeof(data)
                    elif b'got it.\n' in resp:
                        print('packet [{}] received on the first try.'.format(idx))
                        pck_size_tot += sys.getsizeof(data)
                    else:
                        print('sending packet again: {}', end='')
                        while True:
                            print('.', end='')
                            self.operator.write(data.encode())
                            QtTest.QTest.qWait(delay)
                            resp = self.operator.read_all()
                            print(resp)
                            if 'EOF received.\n' in resp.decode():
                                print('EOF received in retry, file was successfully sent.')
                                pck_size_tot += sys.getsizeof(data)
                                break
                            elif b'got it.\n' in resp:
                                print('packet sent in retry.')
                                pck_size_tot += sys.getsizeof(data)
                                break
                            else:
                                QtTest.QTest.qWait(delay)
                                pass
                        print('packet eventually received by LS.')

            else:
                print('Data not larger than {} chars, no need to call the Chunker.'.format(self.packet_size))
                command += '*#'
                self.operator.write(command.encode())
                QtTest.QTest.qWait(delay)
                resp = self.operator.read_all()
                print(resp)
                if 'EOF received.' in resp.decode():
                    print('\n_LucidSens: EOF received by LS on the first try.')
                    pck_size_tot += sys.getsizeof(command)
                
                else:
                    print('sending packet again', end='')
                    while True:
                        self.operator.write(command.encode())
                        print('.', end='')
                        QtTest.QTest.qWait(delay)
                        resp = self.operator.read_all()
                        if 'EOF received.' in resp.decode():
                            print('\n_LucidSens: EOF received in retry.')
                            pck_size_tot += sys.getsizeof(command)
                            break
                        elif b'got it.' in self.operator.read_all():
                            print('\n_LucidSens: packet sent in retry.')
                            pck_size_tot += sys.getsizeof(command)
                            break
                        else:
                            QtTest.QTest.qWait(delay)
                            pass
                    print('Packet eventually received by LucidSens.')

            print('Took {} seconds to {} bytes.'.format((time.time() - t0), pck_size_tot))
            
            ### RECEIVER ###
            print('Receiving', end='')
            while '*' not in self.content:
                try:
                    QtTest.QTest.qWait(delay)
                    data = self.operator.read_all()
                    data_decd = data.decode()
                    # print(data_decd)
                    if '#' in data_decd and data_decd[:-2] not in self.content:
                        if data_decd[-2] == '*':
                            self.content += data_decd[:-1]
                            print('Response received!')
                            # self.operator.write('EOF received.#'.encode())
                            break
                        elif data_decd[-2] == '_':
                            # if 'size' in blah
                            self.content += data_decd[:-2]
                            self.operator.write('got it.#'.encode())
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
                self.operator.write('EOF received.#'.encode())
                # print('Content: {}\n'.format(content))
                # print('length: {} chars\n'.format(len(content)))
                raw_cmd = open('resp.txt', 'w')
                raw_cmd.write(self.content[:-1])
                raw_cmd.close()
                print('Processing the response.')

                with open('resp.txt', 'r') as f:
                    for line in f:
                        if eval(line)['header'] == 'test_astroid':
                            print('Astroid list received, illustrating...')
                            self.test(eval(line)['body'])
                        if eval(line)['header'] == 'run_incubator':
                            print('_LucidSens: {}'.format(eval(line)['body']))
        except KeyboardInterrupt:
            print('Aborted!')
        except Exception as e:
            print(e)
        return 'Exiting Sender_Receiver.'

    def wifi_sndr_recvr(self, command):
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
            self.test(parsed_data["body"])

        except Exception as e:
            print(e)

        except KeyboardInterrupt:
            print("Aborted!")

    def test(self, list_t):
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
            self.textBrowser.append("Software just had a successful talk with the" + self.pen(2, 'blue') +
                                    " Minimal" + "</font>" + self.pen(2, 'orange') + "Sens" + "</font>")
            self.textBrowser.append("-" * 57)
            p2.clear()
            p2.showGrid(x=True, y=True, alpha=1)
            return
        except Exception as e:
            print(e)

    def run_test(self):
        command = ({'header': 'test'})
        command.update({'body': {'it': 10}})
        jsnd_cmd = json.dumps(command)
        jsnd_cmd += '*#'

        if self.serial_connection:
            print(self.serial_sndr_recvr(jsnd_cmd))

        # elif self.wifi_connection:
        #     self.wifi_sndr_recr(jsnd_cmd)

        else:
            self.textBrowser.append("No available connections to the LucidSens.")
            self.textBrowser.append("Please re-establish your connection first.")
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the" + self.pen(2, 'blue') +
                        " Lucid" + "</font>" + self.pen(2, 'orange') + "Sens!" + "</font>"+ "\n" +
                        "please check your connections and try again.")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setWindowTitle("Warning")
            msg.exec_()
        
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

                      'sqt': float(self.lineEdit_SampQuietTime.text()) if self.checkBox_SampMod.isChecked() else '',
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
            self.wifi_sndr_recvr(jsnd_cmd)

        else:
            self.textBrowser.append("No available connections to the MinimalSens.")
            self.textBrowser.append("Please re-establish your connection first.")
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the" + self.pen(2, 'blue') +
                        " Minimal" + "</font>" + self.pen(2, 'orange') + "Sens!" + "</font>" + "\n" +
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
        msg.setWindowTitle('EXIT')
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        msg.setIcon(QtWidgets.QMessageBox.Warning)  # Information - Critical - Question
        msg.exec_()
        if msg.clickedButton() == msg.button(QtWidgets.QMessageBox.Yes):
            sys.exit(0)
        elif msg.clickedButton() == msg.button(QtWidgets.QMessageBox.No):
            msg.close()

    def save(self):
        pass

    def save_as(self):
        pass

    def open(self):

        dir = "/Users/aminhb/Desktop/"
        open_file_obj = QtWidgets.QFileDialog.getOpenFileName(caption=__APPNAME__ + "QDialog Open File", directory=dir,
                                                              filter="Text Files (*.csv)")
        # self.importTable(open_file_obj)
        self.title = "".join((open_file_obj[0]).split('/')[-1:])

    def preferences(self):
        pass

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
    # app.setStyleSheet(open('classicTheme.css').read())
    # app.setStyleSheet(open('darkBlueTheme.css').read())
    # app.setStyleSheet(open('darkOrangeTheme.css').read())
    # app.setStyleSheet(open('classicTheme.css').read())

    form.show()
    # splash.finish(form)
    
    app.exec_()
    