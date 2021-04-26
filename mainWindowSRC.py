import sys, os, time, json, serial, socket
from PyQt5 import QtWidgets, QtTest, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QSettings
import pyqtgraph as pg
import matplotlib.pyplot as plt
import numpy as np
import serial.tools.list_ports as lp
from array import array
import csv
import pandas as pd
import qdarkstyle, qdarkgraystyle
import threading
import traceback
import mainWindowGUI, WifiWindow, PreferencesWindow

__APPNAME__ = "LucidSens"
__VERSION__ = "0.04"

class WorkerSignals(QtCore.QObject):
    '''
    Defined Signals for the Worker thread:
    DONE: str -> resp['header']
    ERROR: tuple -> (exctype, value, traceback.format_exc())
    OUTPUT: dict -> response
    PROGRESS: int -> (progress in %)
    '''
    DONE = pyqtSignal(str)
    ERROR = pyqtSignal(tuple)
    OUTPUT = pyqtSignal(dict)
    PROGRESS = pyqtSignal(int)

class Worker(QtCore.QRunnable):
    ''' Worker thread '''
    def __init__(self, method, *args, **kwargs):
        super(Worker, self).__init__()
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.kwargs['progress_callback'] = self.signals.PROGRESS

    @pyqtSlot()
    def run(self):
        '''Worker thread runner method'''
        try:
            output = self.method(*self.args, **self.kwargs)
            # print(output, type(output))
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.ERROR.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.OUTPUT.emit(output) 
        finally:
            self.signals.DONE.emit(output['header'])

class Delegate(QtWidgets.QStyledItemDelegate):
    """Creates a deleagte for the Preferences options"""
    def editorEvent(self, event, model, option, index):
        value = QtWidgets.QStyledItemDelegate.editorEvent(self, event, model, option, index)        
        if value:
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                if index.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                    parent = index.parent()
                    for i in range(model.rowCount(parent)):
                        if i != index.row():
                            ix = parent.child(i, 0)
                            model.setData(ix, QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)
        return value

class Preferences(QtWidgets.QMainWindow, PreferencesWindow.Ui_Preferences):
    """Preferences Window"""
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.treeWidget.setHeaderHidden(True)
        self.treeWidget.setItemDelegate(Delegate())
        self.treeWidget.expandAll()
        self.settings = QSettings('Theme')
        self._theme = self.settings.value('Theme')
        if self._theme:
            self.treeWidget.setCurrentItem(self.treeWidget.topLevelItem(0))
            model = self.treeWidget.model()
            index = self.treeWidget.currentIndex()
            if model.data(index) == 'Themes':
                index = self.treeWidget.currentIndex().child(0,0)
            parent_idx = index.parent()
            for i in range(model.rowCount(parent_idx)):
                idx = parent_idx.child(i, 0)
                if model.data(idx) == self._theme:
                    model.setData(idx, QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
                else:
                    pass

class WifiSettings(QtWidgets.QWidget, WifiWindow.Ui_WifiSettings):
    """Wifi Window"""
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class Form(QtWidgets.QMainWindow, mainWindowGUI.Ui_MainWindow):
    """Main window"""
    def __init__(self, parent=None):
        super(Form, self).__init__(parent)

        self.content = ''
        self.current_file = ''
        # self.timer = QtCore.QTimer()
        self.threadpool = QtCore.QThreadPool()

        self.serial_connection = False
        self.wifi_connection = False
        # self.bt_connected = False

        self.setupUi(self)
        self.actionOpen.triggered.connect(self.open)
        self.actionNew.triggered.connect(self.new)
        self.actionSave_As.triggered.connect(self.save_as)
        self.actionSave.triggered.connect(self.save)
        self.actionStop.triggered.connect(self.stop)
        self.actionExit.triggered.connect(self.exit)
        self.actionAbout_Us.triggered.connect(self.about_us)
        self.actionHelp.triggered.connect(self.help)
        self.actionWifi.triggered.connect(self.wifi_panel) 
        self.RunButton.clicked.connect(self.run)
        self.TestButton.clicked.connect(self.run_test)
        self.actionConnection.triggered.connect(self.connection_status)
        self.actionPreferences.triggered.connect(self.preferences)
        
        self.graphicsView.clear()
        self.p0 = self.graphicsView.addPlot()
        self.p0.showAxis('right', show=True)
        self.p0.showAxis('top', show=True)
        self.p0.showGrid(x=True, y=True, alpha=1)
        
        self.textBrowser.append(self.pen(3, 'cyan') +  "Lucid" + "</font>" + self.pen(3, 'orange') + "Sens" + "</font>" + self.pen(2, 'white') + " (Chemiluminescence-wing)" + "</font>")
        self.textBrowser.append(self.pen(2, 'green') + "-"*75)
        self.textBrowser.append(self.pen(2, 'green') + f"Version {__VERSION__}")
        self.textBrowser.append(self.pen(2, 'green') +"Developed by M. Amin Haghighatbin")
        self.textBrowser.append(self.pen(2, 'green') +"中国科学技术大学")
        self.textBrowser.append(self.pen(2, 'green') +"University of Science and Technology of China (USTC)")
        self.textBrowser.append(self.pen(2, 'green') +"-"* 75)

        self.checkBox_SampMod.stateChanged.connect(self.sampling_mod_status)
        self.checkBox_IncubMod.stateChanged.connect(self.incubation_mod_status)
        self.checkBox_DataSmth.stateChanged.connect(self.data_processing_mod_status)

        # # EChem Settings
        # self.lineEdit_InitE.editingFinished.connect(self.EChemSettings().ip_chk())
        # self.lineEdit_FinalE.editingFinished.connect(self.EChemSettings().fp_chk())
        # self.lineEdit_NS.editingFinished.connect(self.EChemSettings().nc_chk())
        # self.lineEdit_PulseWidth.editingFinished.connect(self.EChemSettings.pw_chk())
        # self.lineEdit_SampleIntrvl.editingFinished.connect(self.EChemSettings().esi_chk())
        # self.lineEdit_EQuietTime.editingFinished.connect(self.EChemSettings().eqt_chk())
        
        # Incubation Mode
        self.lineEdit_IncubTime.editingFinished.connect(self.itm_chk)
        self.lineEdit_IncubTemp.editingFinished.connect(self.itp_chk)
        self.comboBox_BlowerStat.currentIndexChanged.connect(self.bf_chk)

        # Sampling Mode
        self.lineEdit_SampQuietTime.editingFinished.connect(self.sqt_chk)
        self.lineEdit_NumbSamps.editingFinished.connect(self.sn_chk)
        self.lineEdit_SampTime.editingFinished.connect(self.st_chk)
        self.lineEdit_SampIntrvl.editingFinished.connect(self.csi_chk)
        self.lineEdit_Raw2Avrg.editingFinished.connect(self.r2avg_chk)

        # Photodetection Settings
        self.lineEdit_PMV.editingFinished.connect(self.pmv_chk)
        self.comboBox_SampReadMod.currentIndexChanged.connect(self.adcr_chk)
        self.lineEdit_ADCGain.editingFinished.connect(self.adcg_chk)
        self.lineEdit_ADCSpd.editingFinished.connect(self.adcs_chk)

        # Data Smooting
        self.comboBox_SGorders.currentIndexChanged.connect(self.smth_chk)

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

    def sqt_chk(self):
        """Sampler Quiet Time: A quiet time before initialising the aquisition, no data will be collected during this time"""
        try:
            if not self.lineEdit_SampQuietTime.text() or float(self.lineEdit_SampQuietTime.text()) > 100 or float(self.lineEdit_SampQuietTime.text()) < 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0 and 100 seconds.""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle('Value Error')
                self.lineEdit_SampQuietTime.setText('1')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0 and 100 seconds.""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle('Value Error')
            self.lineEdit_SampQuietTime.setText('1')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_SampQuietTime.setText('1')

    def sn_chk(self):
        """Number of Samples: LucidSens has currently been designed to collect 3 samples in one cycle"""
        try:
            if not self.lineEdit_NumbSamps.text() or float(self.lineEdit_NumbSamps.text()) > 18 or float(
                    self.lineEdit_NumbSamps.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 1 and 18 samples.""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle('Value Error')
                self.lineEdit_NumbSamps.setText('3')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 1 and 18 samples.""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            self.lineEdit_NumbSamps.setText('3')
            msg.setWindowTitle('Value Error')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_NumbSamps.setText('3')

    def st_chk(self):
        """Sampling Acquistion time: The total time that the photodetection module will be collecting data from each sample"""
        try:
            if not self.lineEdit_SampTime.text() or float(self.lineEdit_SampTime.text()) > 120 or float(
                    self.lineEdit_SampTime.text()) < 0.1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0.1 and 180 seconds.""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle('Value Error')
                self.lineEdit_SampTime.setText('1')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0.1 and 180 seconds.""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            self.lineEdit_SampTime.setText('1')
            msg.setWindowTitle('Value Error')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_SampTime.setText('1')

    def csi_chk(self):
        """Sampling Intervals: The time between data collections during the acquisition time"""
        try: 
            if not self.lineEdit_SampIntrvl.text() or float(self.lineEdit_SampIntrvl.text()) > 10 or float(
                    self.lineEdit_SampIntrvl.text()) < 0.001:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0.001 and 10 seconds.""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                self.lineEdit_SampIntrvl.setText('0.01')
                msg.setWindowTitle('Value Error')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0.001 and 10 seconds.""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle('Value Error')
            self.lineEdit_SampIntrvl.setText('0.01')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_SampIntrvl.setText('0.01')

    def r2avg_chk(self):
        """Raw to Average: Number of samples to be collected and averaged between two sampling intervals"""
        try:
            if not self.lineEdit_Raw2Avrg.text() or float(self.lineEdit_Raw2Avrg.text()) > 101 or float(
                    self.lineEdit_Raw2Avrg.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0 and 101 samples per collection.""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                self.lineEdit_Raw2Avrg.setText('10')
                msg.setWindowTitle('Value Error')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0 and 101 samples per collection.""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            self.lineEdit_Raw2Avrg.setText('10')
            msg.setWindowTitle('Value Error')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_Raw2Avrg.setText('10')

    def itm_chk(self):
        """Incubation Time: Incubation time in minutes"""
        try:
            if not self.lineEdit_IncubTime.text() or float(self.lineEdit_IncubTime.text()) > 180 or float(
                    self.lineEdit_IncubTime.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 1 and 180 minutes.""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle('Value Error')
                self.lineEdit_IncubTime.setText('15')
                msg.exec_()
            else:
                return self.line
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 1 and 180 minutes.""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            self.lineEdit_IncubTime.setText('15')
            msg.setWindowTitle('Value Error')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_IncubTime.setText('15')

    def itp_chk(self):
        """Incubation Temperature: The incubatiobn temperature will be adjusted on the defined temperature +/- 2C"""
        try:
            if not self.lineEdit_IncubTemp.text() or float(self.lineEdit_IncubTemp.text()) > 45 or float(
                    self.lineEdit_IncubTemp.text()) < 15:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 15 and 45C degrees.""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle('Value Error')
                self.lineEdit_IncubTemp.setText('30')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 15 and 45C degrees.""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            self.lineEdit_IncubTemp.setText('30')
            msg.setWindowTitle('Value Error')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_IncubTemp.setText('30')

    def bf_chk(self):
        """Blower Status: This module could be turned off in case the incubation occurs under an external gas source"""
        return str(self.comboBox_BlowerStat.currentText())

    def adcr_chk(self):
        """Sampling ADC reading Mode: The default setting is Slow for Chemiluminescence measuremnents"""
        return str(self.comboBox_SampReadMod.currentText())

    def pmv_chk(self):
        """Silicon Photomultiplier Power Set: This module supplies the HV required for the SiPM to operate"""
        try:
            if not self.lineEdit_PMV.text() or float(self.lineEdit_PMV.text()) > 35 or float(
                    self.lineEdit_PMV.text()) < 20:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 25 and 35 volts.""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                self.lineEdit_PMV.setText('30')
                msg.setWindowTitle('Value Error')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 25 and 35 volts.""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            self.lineEdit_PMV.setText('30')
            msg.setWindowTitle('Value Error')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_PMV.setText('30')

    def adcg_chk(self):
        """Silicon Photomultiplier ADC gain: refer to ADS1232 datasheet - default value is 1"""
        try:
            if not self.lineEdit_ADCGain.text() or int(self.lineEdit_ADCGain.text()) not in [1, 2, 64, 128]:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value: 1, 2, 64, 128""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle('Value Error')
                self.lineEdit_ADCGain.setText('1')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value: 1, 2, 64, 128""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            self.lineEdit_ADCGain.setText('1')
            msg.setWindowTitle('Value Error')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_ADCGain.setText('1')

    def adcs_chk(self):
        """Silicon Photomultiplier ADC gain: refer to the ADS1232 datasheet - default value is 1"""
        try:
            if not self.lineEdit_ADCSpd.text() or int(self.lineEdit_ADCSpd.text()) not in [1, 2]:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value: 1 or 2""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                self.lineEdit_ADCSpd.setText('1')
                msg.setWindowTitle('Value Error')
                msg.exec_()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value: 1, 2""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            self.lineEdit_ADCSpd.setText('1')
            msg.setWindowTitle('Value Error')
            msg.exec_()
        except Exception as e:
            print(e)
            self.lineEdit_ADCSpd.setText('1')
    
    def smth_chk(self):
        """Data Smoothing Algorithm: Runs the smoothing algorithm on the collected raw data"""
        self.algo = self.comboBox_Smt.currentText()
        self.order = self.comboBox_SGorders.currentText()
        return [self.algo, self.order] 

    def error_report(self, tpl):
        """Error report: Thread exceptions will be reflecred on the textBrowser"""
        self.textBrowser.append(f'THREAD: ERROR:\n{tpl}')

    def thread_completed(self, txt):
        """Thread completion method"""
        if 'test' in txt:
            txt = 'Just had a nice chat with the LS! serial connection is up and running.'

        elif 'kill' in txt:
            txt = 'Incubation has been canceled.'

        elif 'wifi' in txt:
            txt = 'Wifi credentials were updated, please restart the device and re-establish your connection.'

        elif 'incubation' in txt:
            txt = 'Incubation in progress. please be patient. \n\nNote: Incubation can be canceled by clicking on the Stop button.'

        elif 'sampling' in txt:
            txt = 'Sampling is initialised, please be patient.'

        else:
            txt = 'Task was not clear, howerver, it is handled now!'

        self.statusbar.showMessage("Done.")
        self.textBrowser.append(self.pen() + txt + "</font>")

    def progress_status(self, n):
        self.statusbar.showMessage(f"Received: {n}%")

    def writer(self, txt, font_size=8, color='green'):
        """Writer method"""
        self.textBrowser.setTextColor(QtGui.QColor(f'{color}'))
        self.textBrowser.setFontPointSize(10)
        for idx, char in enumerate(txt):
            self.textBrowser.insertPlainText(char)
            QtTest.QTest.qWait(20)
        self.textBrowser.moveCursor(QtGui.QTextCursor.End)
        self.textBrowser.ensureCursorVisible()
        
    def pen(self, size=2, color='green'):
        """Default pen method for the textBrowser"""
        return f"<font size='{size}' color='{color}'>"
       
    def sampling_mod_status(self):
        """Manages the status of the labels and lineEdits in the Sampling Mode section"""
        if self.checkBox_SampMod.isChecked():
            self.lineEdit_SampQuietTime.setDisabled(False)
            self.lineEdit_NumbSamps.setDisabled(False)
            self.lineEdit_SampTime.setDisabled(False)
            self.lineEdit_SampIntrvl.setDisabled(False)
            self.lineEdit_Raw2Avrg.setDisabled(False)

            self.label_SampQuietT.setDisabled(False)
            self.label_NoSamp.setDisabled(False)
            self.label_SampT.setDisabled(False)
            self.label_SampIntrvls.setDisabled(False)
            self.label_Raw2Avrg.setDisabled(False)

            self.label_PDSets.setDisabled(False)

            self.label_SampReadMod.setDisabled(False)
            self.label_Vltg.setDisabled(False)
            self.label_adcG.setDisabled(False)
            self.label_adcS.setDisabled(False)

            self.comboBox_SampReadMod.setDisabled(False)
            self.lineEdit_PMV.setDisabled(False)
            self.lineEdit_ADCGain.setDisabled(False)
            self.lineEdit_ADCSpd.setDisabled(False)

            self.checkBox_IncubMod.setDisabled(True)
        else:
            self.lineEdit_SampQuietTime.setDisabled(True)
            self.lineEdit_NumbSamps.setDisabled(True)
            self.lineEdit_SampTime.setDisabled(True)
            self.lineEdit_SampIntrvl.setDisabled(True)
            self.lineEdit_Raw2Avrg.setDisabled(True)

            self.label_SampQuietT.setDisabled(True)
            self.label_NoSamp.setDisabled(True)
            self.label_SampT.setDisabled(True)
            self.label_SampIntrvls.setDisabled(True)
            self.label_Raw2Avrg.setDisabled(True)

            self.label_PDSets.setDisabled(True)

            self.label_SampReadMod.setDisabled(True)
            self.label_Vltg.setDisabled(True)
            self.label_adcG.setDisabled(True)
            self.label_adcS.setDisabled(True)

            self.comboBox_SampReadMod.setDisabled(True)
            self.lineEdit_PMV.setDisabled(True)
            self.lineEdit_ADCGain.setDisabled(True)
            self.lineEdit_ADCSpd.setDisabled(True)

            self.checkBox_IncubMod.setDisabled(False)

    def incubation_mod_status(self):
        """Manages the status of the labels and lineEdits in the Incubation Mode section"""
        if self.checkBox_IncubMod.isChecked():
            self.label_IncubTime.setDisabled(False)
            self.lineEdit_IncubTime.setDisabled(False)
            self.label_IncubTemp.setDisabled(False)
            self.lineEdit_IncubTemp.setDisabled(False)
            self.label_Blower.setDisabled(False)
            self.comboBox_BlowerStat.setDisabled(False)
            self.checkBox_SampMod.setDisabled(True)
            self.checkBox_DataSmth.setDisabled(True)
            self.label_PDSets.setDisabled(True)

        else:
            self.label_IncubTime.setDisabled(True)
            self.lineEdit_IncubTime.setDisabled(True)
            self.label_IncubTemp.setDisabled(True)
            self.lineEdit_IncubTemp.setDisabled(True)
            self.label_Blower.setDisabled(True)
            self.comboBox_BlowerStat.setDisabled(True)
            self.checkBox_SampMod.setDisabled(False)
            self.checkBox_DataSmth.setDisabled(False)
            self.label_PDSets.setDisabled(False)

    def data_processing_mod_status(self):
        """Manages the status of the labels and lineEdits in the Data-Processing section"""
        if self.checkBox_DataSmth.isChecked():
            self.comboBox_Smt.setDisabled(False)
            self.comboBox_SGorders.setDisabled(False)

        else:
            self.comboBox_Smt.setDisabled(True)
            self.comboBox_SGorders.setDisabled(True)
 
    def serial_port(self):
        """Initialises the serial communication with the LucidSens device"""
        try:
            if lp.comports():
                for idx, port in enumerate(lp.comports()):

                    # MAC OS
                    if "usbmodem" in str(port.device) or "wch" in str(port.device) or "SLAB" in str(port.device):
                        serial_port = str(port.device)
                        serial_port = serial_port.replace("cu", "tty")

                    # Windows OS
                    if "CP210x" in str(port):
                        serial_port = str(port.device)

                self.writer("\nEstablishing connection via serial port\nScanning serial ports...")
                self.writer(f"\nAvailable port: {serial_port}\n")

                if serial_port:
                    self.operator = serial.Serial(serial_port, baudrate=115200)
                    self.serial_connection = True

                else:
                    self.serial_connection = False
                    1000, lambda: self.textBrowser.append(
                        self.pen(2, 'red') + "Failed to communicate via Serial port!" + "</font>")
                    QtTest.QTest.qWait(1000)
            else:
                self.serial_connection = False
                self.textBrowser.append(self.pen(2, 'red') + "Failed to find any available Serial ports! " + "</font>")
                QtTest.QTest.qWait(1000)
            return self.serial_connection

        except Exception as e:
            self.serial_connection = False
            self.textBrowser.append(
            self.pen(2, 'red') + "Failed to communicate via Serial port!" + "</font>")
            self.textBrowser.append(str(e) + "\n")
            return self.serial_connection

    def connection_status(self):
        """Manages the serial connection status"""
        if not self.serial_connection:
            self.serial_port()
            QtTest.QTest.qWait(1000)
            self.writer("Connection established via Serial port.", 8, 'cyan')
            self.actionConnection.setIcon(QtGui.QIcon(":/Icons/connection_green.icns"))

        else:
            self.actionConnection.setIcon(QtGui.QIcon(":/Icons/disconnect.icns"))
            self.operator.close()
            self.serial_connection = False
            msg = QtWidgets.QMessageBox()
            QtTest.QTest.qWait(1000)
            msg.setText("Serial communication with " + self.pen(2, 'blue') +
                        " Lucid" + "</font>" + self.pen(2, 'orange') + "Sens " + "</font>" + "was disrupted!\n" +
                        "please check your connections and try again.")
            self.textBrowser.append(
                self.pen(2, 'red') + "Serial connection is disrupted." + "</font>")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setWindowTitle("Warning")
            msg.exec_()

    def serial_sndr_recvr(self, command, progress_callback=1):
        """This method encapsulates, encodes and decodes the commands and responses to and from the LucidSens"""
        def chopper(cmd):
            data = []
            segments = [cmd[i:i + 256] for i in range(0, len(cmd), 256)]
            for segment in segments:
                if segment == segments[-1]:
                    data.append(segment + '*#')
                else:
                    data.append(segment + '_#')
            return data

        self.content = ''
        delay = 1000
        print('Waiting for invitation', end='')
        self.statusbar.showMessage('Waiting for invitation')
        while b'sr_receiver: READY\n' not in self.operator.read_all():
            QtTest.QTest.qWait(delay)
        print('\nInvited, sending GO!')
        self.statusbar.showMessage('Invited, sending GO!')

        while b'got it.\n' not in self.operator.read_all():
            self.operator.write('go#'.encode())
            QtTest.QTest.qWait(delay)

        # __SERIAL SENDER__ 
        try:
            if len(command) > 256:
                for idx, data in enumerate([chunk for chunk in chopper(command)]):
                    while True:
                        self.operator.write(data.encode())
                        QtTest.QTest.qWait(delay)
                        resp = self.operator.read_all()
                        if 'EOF received.\n' in resp.decode():
                            break
                        elif 'got it.\n' in resp.decode():
                            pass
                        else:
                            QtTest.QTest.qWait(delay)
                    print('Command received by the LS.')

            else:
                self.statusbar.showMessage('Sending...')
                command += '*#'
                self.operator.write(command.encode())
                QtTest.QTest.qWait(delay)
                resp = self.operator.read_all()
                while 'EOF received.\n' not in resp.decode():
                    self.operator.write(command.encode())
                    QtTest.QTest.qWait(delay)
                    resp = self.operator.read_all()
                    if 'EOF received.\n' in resp.decode():
                        break
                    elif 'got it.\n' in resp.decode():
                        break
                    else:
                        pass
                print('Command received by the LucidSens.')
            
            # __SERIAL RECEIVER__
            self.statusbar.showMessage('Waiting...')
            print('Waiting...')
            counter = 0
            while '*' not in self.content:
                try:
                    QtTest.QTest.qWait(100)
                    data = self.operator.read_all()
                    data_decd = data.decode()
                    a_idx = data_decd.find('<') - len(data_decd)
                    current_idx = data_decd[a_idx+1:data_decd.find('/')]
                    z_idx = data_decd[data_decd.find('/')+1:data_decd.find('>')]

                    if '#' in data_decd :
                        self.statusbar.showMessage('Receiving...')
                        if '*' in data_decd:
                            self.content += data_decd[:-1]
                            print('Response received.')
                            self.statusbar.showMessage('[Received]: 100%')
                            QtTest.QTest.qWait(500)
                            break
                        elif '_' in data_decd and int(current_idx) > counter:
                            self.content += data_decd[:a_idx]
                            self.operator.write('got it.#'.encode())
                            progress = round((int(current_idx) / int(z_idx)) * 100)
                            sys.stdout.write(f"[Received]: {progress}%\r")
                            sys.stdout.flush()
                            counter += 1
                            progress_callback.emit(round((int(current_idx) / int(z_idx)) * 100))
                            QtTest.QTest.qWait(100)
                        else:
                            pass
                    else:
                        QtTest.QTest.qWait(delay)
                except:
                    pass
            counter = 0
            # print(f'Response: {self.content}')
            if '*' in self.content:
                self.operator.write('EOF received.#'.encode())
                with open('resp.txt', 'w') as raw_resp:
                    raw_resp.write(self.content[:-1])
                self.statusbar.showMessage('Response is being processed.\nDone.')
                with open('resp.txt', 'r') as f:
                    for line in f:
                        return eval(line)
            else:
                return {'header':'Corrupted Data!'}
                
        except KeyboardInterrupt:
            return {'header': 'User interruption.'}
        except Exception as e:
            print(e)
            return {'header':'Corrupted Data!'}

    def response_handler(self, resp):
        """Handles the responses and task completion signs"""
        if 'test' in resp['header']:
            self.statusbar.showMessage('Just had a nice chat with the LS! serial connection is up and running.')
            self.test()
        
        elif 'kill' in resp['header']:
            self.statusbar.showMessage('Incubation was canceled.')
            msg = QtWidgets.QMessageBox()
            msg.setText(resp['body'])
            msg.setWindowTitle('Task accomplished')
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.exec_()

        elif 'wifi' in resp['header']:
            self.statusbar.showMessage('Wifi Credentials were updated, please restart the device')
            msg = QtWidgets.QMessageBox()
            msg.setText(resp['body'])
            msg.setWindowTitle('Task accomplished')
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.exec_()

        elif 'incubation' in resp['header']:
            self.statusbar.showMessage('Incubation in progress')
            msg = QtWidgets.QMessageBox()
            msg.setText(resp['body'])
            msg.setWindowTitle('Task accomplished')
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.exec_()

        elif 'sampling' in resp['header']:
            self.statusbar.showMessage('Sampling in progress')
            time_axis = [round((i*resp['notes'][2]), 2) for i in range(int(resp['notes'][1]/resp['notes'][2]))]
            data = []
            samples = resp['notes'][0]
            colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w', '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

            for i in range(samples):
                data.append((resp['body'][i][1]).tolist())
                # Plotting each sample
                self.plot_data(time_axis, resp['body'][i][1].tolist(), color=colors[i], title=f'Sample #{i+1}')
            # Saving data as a CSV file
            data[0:0] = [time_axis]
            _, merged_list = [], []
            for i in range(len(data[0])):
                for j in range(samples + 1): 
                    _.append(data[j][i])
                merged_list.append(_)
                _ = []

            with open('latest_data.csv', 'w', newline='') as f:
                writer = csv.writer(f)
                headers = [f'Sample #{i+1}' for i in range(samples)]
                headers[0:0] = ['Time (s)']
                writer.writerow(headers)
                for row in merged_list:
                    writer.writerow(row)
                self.current_file = 'latest_data.csv'
            with open('latest_data.csv', 'r') as f:
                self.current_file = os.path.realpath(f.name)
        else:
            print(f'response: {resp}', type(resp))

    def test(self):
        """Plots the serial test module"""
        while not os.path.exists('resp.txt'):
            pass
        try:
            with open('resp.txt', 'r') as f:
                for line in f:
                    if 'test' in eval(line)['header']:
                        self.statusbar.showMessage('Astroid list is received, illustrating...')
                        list_t = eval(line)['body']
                    else:
                        print('Something is wrong with the received list.')
            self.graphicsView.clear()
            self.p0 = self.graphicsView.addPlot()
            self.p0.showAxis('right', show=True)
            self.p0.showAxis('top', show=True)
            self.p0.showGrid(x=True, y=True, alpha=1)
            for _ in range(1):
                for i in range(len(list_t)):
                    self.p0.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][1], pen=pg.mkPen((i, 2), width=2))
                    QtTest.QTest.qWait(10)
                    self.p0.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][2], pen=pg.mkPen((i, 2), width=2))
                    QtTest.QTest.qWait(10)
                QtTest.QTest.qWait(3000)
                for i in reversed(range(len(list_t))):
                    QtTest.QTest.qWait(10)
                    self.p0.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][1], pen=pg.mkPen('k', width=2))
                    QtTest.QTest.qWait(10)
                    self.p0.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][2], pen=pg.mkPen('k', width=2))
                    QtTest.QTest.qWait(10)
            self.graphicsView.clear()
            self.p0 = self.graphicsView.addPlot()
            self.p0.showAxis('right', show=True)
            self.p0.showAxis('top', show=True)
            self.p0.showGrid(x=True, y=True, alpha=1)
        except Exception as e:
            print(e)

    def run_test(self):
        """Prepares the serial test command"""
        if os.path.exists("resp.txt"):
            os.remove("resp.txt")

        command = ({'header': 'test'})
        command.update({'body': {'it': int(self.comboBox.currentText())}})
        jsnd_cmd = json.dumps(command)

        if self.serial_connection:
            test_worker = Worker(self.serial_sndr_recvr, jsnd_cmd)
            test_worker.signals.DONE.connect(self.thread_completed)
            test_worker.signals.OUTPUT.connect(self.response_handler)
            test_worker.signals.ERROR.connect(self.error_report)
            test_worker.signals.PROGRESS.connect(self.progress_status)
            self.threadpool.start(test_worker)
            # self.timer.singleShot(15000, lambda: self.test())
            QtTest.QTest.qWait(20000)

        else:
            self.textBrowser.append(self.pen() + "No available connections to the LucidSens,\nPlease re-establish the connection first." + "</font>")
            
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the" + self.pen(2, 'blue') +
                        " Lucid" + "</font>" + self.pen(2, 'orange') + "Sens!" + "</font>"+ "\n" +
                        "please check your connections and try again.")
            msg.setWindowTitle("Warning")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.exec_()
        
    def run(self):
        """Prepares the run command"""
        if os.path.exists("resp.txt"):
            os.remove("resp.txt")
        self.p0.clear()
        if self.checkBox_IncubMod.isChecked():
            command = ({'header': 'incubation'})
            command.update({'body': {
                'it': float(self.lineEdit_IncubTime.text()),
                'ip': float(self.lineEdit_IncubTemp.text()),
                'bf': str(self.comboBox_BlowerStat.currentText())}})

        if self.checkBox_SampMod.isChecked():
            command = ({'header': 'sampling'})
            command.update({'body': {
                'sqt': float(self.lineEdit_SampQuietTime.text()),
                'sn': int(self.lineEdit_NumbSamps.text()),
                'st': float(self.lineEdit_SampTime.text()),
                'si': float(self.lineEdit_SampIntrvl.text()),
                'r2avg': int(self.lineEdit_Raw2Avrg.text()),
                'pmr': str(self.comboBox_SampReadMod.currentText()),
                'pv': float(self.lineEdit_PMV.text()),
                'ag': int(self.lineEdit_ADCGain.text()),
                'as': int(self.lineEdit_ADCSpd.text())}})

        jsnd_cmd = json.dumps(command)
        if self.serial_connection:
            run_worker = Worker(self.serial_sndr_recvr, jsnd_cmd)
            run_worker.signals.DONE.connect(self.thread_completed)
            run_worker.signals.OUTPUT.connect(self.response_handler)
            run_worker.signals.ERROR.connect(self.error_report)
            run_worker.signals.PROGRESS.connect(self.progress_status)
            self.threadpool.start(run_worker)

        else:
            self.textBrowser.append(self.pen() + "No available connections to the LucidSens,\nPlease re-establish your connection first." + "</font>")
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the" + self.pen(2, 'blue') +
                        " Lucid" + "</font>" + self.pen(2, 'orange') + "Sens!" + "</font>" + "\n" +
                        "please check your connections and try again.")
            msg.setWindowTitle('Warning')
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

    def about_us(self):
        """About Us"""
        msg = QtWidgets.QMessageBox()
        _theme = QSettings('Theme').value('Theme')
        if _theme:
            color = 'black' if _theme in ['Fusion', 'Light-Classic'] else 'white'
        QtWidgets.QMessageBox.about(msg, 'About Us',
            f"""<font size='4' color='blue'><p><b>Lucid<font size=4 color='orange'>Sens</font><font color={color}> &copy;2021</p></b></font>
            <font color={color}><p>Version:      {__VERSION__}</p><br></br>
            
            <p><b>Author:       M.Amin Haghighatbin</b> </font></p>
            
            <font color={color}><p><b>Email: </b>aminhb@tutanota.com</p><p>aminhb@ustc.edu.cn</p>
            
            <font color='red'><p><b>Github: <a href='https://github.com/haghighatbin/LucidSens_GUI'>https://github.com/haghighatbin/LucidSens_GUI</a></b></p></font><br></br>
            
            
            <b><p>*This software is under XXX license.</p></b></font>""")

    def help(self):
        """Operational manual and documentations will be added here"""
        msg = QtWidgets.QMessageBox()
        msg.setText("Can't help you mate, you're done!")
        msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        msg.setWindowTitle("Help")
        msg.exec_()

    def new(self):
        """Clears the graphicsView Window"""
        self.graphicsView.clear()
        self.p0 = self.graphicsView.addPlot()
        self.p0.showGrid(x=True, y=True, alpha=1)

    def exit(self):
        """Exits the app"""
        msg = QtWidgets.QMessageBox()
        msg.setText("Are you sure you want to exit?")
        msg.setWindowTitle('Exit')
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        msg.setIcon(QtWidgets.QMessageBox.Warning)  # Information - Critical - Question
        msg.exec_()
        if msg.clickedButton() == msg.button(QtWidgets.QMessageBox.Yes):
            sys.exit(0)
        elif msg.clickedButton() == msg.button(QtWidgets.QMessageBox.No):
            msg.close()

    def save(self):
        """Save Method"""
        # this method needs to be modified after implementing an editable data-table
        df = pd.read_csv(self.current_file)
        df.to_csv(self.current_file, index=False)

    def save_as(self):
        """Save as Method"""
        save_as_file_obj = QtWidgets.QFileDialog.getSaveFileName(caption=__APPNAME__ + "QDialog Open File", filter="Text Files (*.csv)")
        if not save_as_file_obj[0]:
            return
        if not self.current_file:
            return

        df = pd.read_csv(self.current_file)
        df.to_csv(save_as_file_obj[0], index=False)

    def open(self):
        """Opens a CSV file"""
        open_file_obj = QtWidgets.QFileDialog.getOpenFileName(caption=__APPNAME__ + "QDialog Open File", filter="Text Files (*.csv)")
        if not open_file_obj[0]:
            return
        # self.title = "".join((open_file_obj[0]).split('/')[-1:])
        try:
            self.current_file = open_file_obj[0]
            df = pd.read_csv(self.current_file)
            if len(df.columns) < 2:
                msg = QtWidgets.QMessageBox()
                QtTest.QTest.qWait(1000)
                msg.setText("Seems like your dara is incomplete! faild to preview.")
                self.textBrowser.append("Data file sounds incomplete.")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setWindowTitle("Warning")
                msg.exec_()

            else:
                colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w', '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
                time_idx = df['Time (s)'].tolist()
                for i in range(1, len(df.columns)):
                    self.plot_data(time_idx, df[f'Sample #{i}'].tolist(), color=colors[i-1], title=f'Sample #{i}')
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("Invalid file format. Are you sure file was created by the LucidSens!?")
            msg.setWindowTitle('File Error')
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

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

    def plot_data(self, x, y, color='w', title='Data'):
        """Handles data-plotting"""
        data_x, data_y = x, y
        self.p0.addLegend(offset=(548,8))
        self.p0.plot(x=data_x, y=data_y, pen=pg.mkPen(color=color, width=2), name=title)
        self.p0.showGrid(x=True, y=True, alpha=1)
        _theme = QSettings('Theme').value('Theme')
        if _theme:
            color = 'black' if _theme in ['Fusion', 'Light-Classic'] else 'white'
        self.p0.setLabel('bottom', 'Time (s)', **{'color': color, 'font-size': '12px'})
        self.p0.setLabel('left', 'Counts (a.u.)', **{'color': color, 'font-size': '12px'})

    def stop(self):
        """Kill switch to interrupt the on-going operation on the LucidSens"""
        command = ({'header': 'kill'})
        jsnd_cmd = json.dumps(command)
        if self.serial_connection:
            stop_worker = Worker(self.serial_sndr_recvr, jsnd_cmd)
            stop_worker.signals.DONE.connect(self.thread_completed)
            stop_worker.signals.OUTPUT.connect(self.response_handler)
            stop_worker.signals.ERROR.connect(self.error_report)
            stop_worker.signals.PROGRESS.connect(self.progress_status)
            self.threadpool.start(stop_worker)

    def preferences(self):
        """Preferences window."""
        self.prefs = Preferences()
        self.prefs.buttonBox.accepted.connect(self.preferences_accept)
        self.prefs.buttonBox.rejected.connect(self.preferences_reject)
        self.prefs.show()
    
    def preferences_accept(self):
        """Manages the theme, saves and restores the preferences."""
        index = self.prefs.treeWidget.currentIndex()
        model = self.prefs.treeWidget.model()
        if model.data(index) == 'Themes':
            index = self.prefs.treeWidget.currentIndex().child(0,0)
        parent_idx = index.parent()
        for i in range(model.rowCount(parent_idx)):
            idx = parent_idx.child(i, 0)
             
            if model.data(idx) == "Light-Classic":
                app.setStyleSheet(open("./Themes/Light-Classic.css").read())
                self.graphicsView.setBackground(background='w')
                self.prefs.treeWidget.itemFromIndex(idx).setSelected(True)
                self.prefs.settings.setValue('Theme', 'Light-Classic')
                self.prefs.close()

            elif model.data(idx) == "Fusion" and idx.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                app.setStyle('Fusion')
                self.graphicsView.setBackground(background='w')
                self.prefs.treeWidget.itemFromIndex(idx).setSelected(True)
                self.prefs.settings.setValue('Theme', 'Fusion')
                self.prefs.close()
            
            elif model.data(idx) == "Windows" and idx.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                app.setStyle('Windows')
                self.graphicsView.setBackground(background='w')
                self.prefs.treeWidget.itemFromIndex(idx).setSelected(True)
                self.prefs.settings.setValue('Theme', 'Windows')
                self.prefs.close()

            elif model.data(idx) == "Dark" and idx.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
                self.graphicsView.setBackground(background='k')
                self.prefs.treeWidget.itemFromIndex(idx).setSelected(True)
                self.prefs.settings.setValue('Theme', 'Dark')
                self.prefs.close()

            elif model.data(idx) == "Dark-Blue" and idx.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                app.setStyleSheet(open("./Themes/Dark-Blue.css").read())
                self.graphicsView.setBackground(background='k')
                self.prefs.treeWidget.itemFromIndex(idx).setSelected(True)
                self.prefs.settings.setValue('Theme', 'Dark-Blue')
                self.prefs.close()

            elif model.data(idx) == "Dark-Gray" and idx.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                app.setStyleSheet(qdarkgraystyle.load_stylesheet())
                self.graphicsView.setBackground(background='k')
                self.prefs.treeWidget.itemFromIndex(idx).setSelected(True)
                self.prefs.settings.setValue('Theme', 'Dark-Gray')
                self.prefs.close()

            elif model.data(idx) == "Dark-Orange" and idx.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                app.setStyleSheet(open("./Themes/Dark-Orange.css").read())
                self.graphicsView.setBackground(background='k')
                self.prefs.treeWidget.itemFromIndex(idx).setSelected(True)
                self.prefs.settings.setValue('Theme', 'Dark-Orange')
                self.prefs.close()
            else:
                pass
        self.prefs.close()

    def preferences_reject(self):
        """Closes the preferences window."""
        self.prefs.close()

    def wifi_panel(self):
        """Wifi settings window"""
        self.wf = WifiSettings()
        self.wf.buttonBox.accepted.connect(self.wf_accept)
        self.wf.buttonBox.rejected.connect(self.wf_reject)
        self.wf.show()

    def wf_accept(self):
        """Prepares the wifi command"""
        command = ({'header': 'wifi'})
        command.update({'body': {
            'ip': str(self.wf.lineEdit_ip.text()),
            'port': str(self.wf.lineEdit_port.text()),
            'subnet': str(self.wf.lineEdit_subnet.text()),
            'gateway': str(self.wf.lineEdit_gateway.text()),
            'dns': str(self.wf.lineEdit_dns.text()),
            'essid': str(self.wf.lineEdit_essid.text()),
            'password': str(self.wf.lineEdit_password.text())
            }})
        jsnd_cmd = json.dumps(command)
        if self.serial_connection:
            wf_worker = Worker(self.serial_sndr_recvr, jsnd_cmd)
            wf_worker.signals.DONE.connect(self.thread_completed)
            wf_worker.signals.OUTPUT.connect(self.response_handler)
            wf_worker.signals.PROGRESS.connect(self.progress_status)
            wf_worker.signals.ERROR.connect(self.error_report)
            self.threadpool.start(wf_worker)

        else:
            self.textBrowser.append(self.pen() + "No available connections to the LucidSens,\nPlease re-establish your connection first."  + "</font>")
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the LucidSens, please check your connections and try again.")
            msg.setWindowTitle('Warning')
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
        self.wf.close()

    def wf_reject(self):
        """Closes the wifi windows"""
        self.textBrowser.append("No wifi settings has been updated.")
        self.wf.close()

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

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    # app.setWindowIcon(
    #     QtGui.QIcon(":/Icons/lucidsens_2.icns"))

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
    settings = QSettings('Theme')
    _theme = settings.value('Theme')
    if _theme:
        if _theme in ['Dark-Blue', 'Dark-Orange', 'Light-Classic']:
            app.setStyleSheet(open(f"./Themes/{_theme}.css").read())
            if _theme == 'Light-Classic':
                form.graphicsView.setBackground(background='w')
            else:
                form.graphicsView.setBackground(background='k')

        elif _theme in ['Dark', 'Dark-Gray']:
            if _theme == 'Dark':
                app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
            else:
                app.setStyleSheet(qdarkgraystyle.load_stylesheet())
            form.graphicsView.setBackground(background='k')

        elif _theme in ['Fusion', 'Windows']:
            app.setStyle(_theme)
            form.graphicsView.setBackground(background='w')
        else:
            pass

    form.show()
    # splash.finish(form)
    app.exec_()