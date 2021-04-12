import sys, os, time, json, serial, socket
from PyQt5 import QtWidgets, QtTest, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QSettings
import pyqtgraph as pg
import matplotlib.pyplot as plt
import numpy as np
import serial.tools.list_ports as lp
import csv
import qdarkstyle, qdarkgraystyle
import threading
import traceback
import mainWindowGUI, WifiWindow, PreferencesWindow

__APPNAME__ = "LucidSens"
VERSION = "0.03"

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

        self.packet_size = 256
        self.content = ''
        self.timer = QtCore.QTimer()
        self.threadpool = QtCore.QThreadPool()

        self.serial_connection = False
        self.wifi_connection = False
        # self.bt_connected = False

        self.setupUi(self)
        self.actionOpen.triggered.connect(self.open)
        self.actionNew.triggered.connect(self.new)
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
        p0 = self.graphicsView.addPlot()
        p0.showAxis('right', show=True)
        p0.showAxis('top', show=True)
        p0.showGrid(x=True, y=True, alpha=1)
        
        self.textBrowser.append(self.pen(3, 'cyan') +  "Lucid" + "</font>" + self.pen(3, 'orange') + "Sens" + "</font>" + self.pen(2, 'white') + " (Chemiluminescence-wing)" + "</font>")
        self.textBrowser.append(self.pen(2, 'green') + "-"*75)
        self.textBrowser.append(self.pen(2, 'green') + f"Version {VERSION}")
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
        self.lineEdit_SampleIntrvl.editingFinished.connect(self.csi_chk)
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
        """Sampler Quiet Time: A quiet time before initialising the aquisition, no data will be collected during this time."""
        try:
            if not self.lineEdit_SampQuietTime.text() or float(self.lineEdit_SampQuietTime.text()) > 100 or float(self.lineEdit_SampQuietTime.text()) < 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0 and 100""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_SampQuietTime.setText('1')

        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0 and 100""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_SampQuietTime.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_SampQuietTime.setText('1')

    def sn_chk(self):
        """Number of Samples: LucidSens has currently been designed to collect 3 samples in one cycle."""
        try:
            if not self.lineEdit_NumbSamps.text() or float(self.lineEdit_NumbSamps.text()) > 18 or float(
                    self.lineEdit_NumbSamps.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 1 and 18""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_NumbSamps.setText('3')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 1 and 18""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_NumbSamps.setText('3')
        except Exception as e:
            print(e)
            self.lineEdit_NumbSamps.setText('3')

    def st_chk(self):
        """Sampling Acquistion time: The total time that the photodetection module will be collecting data from each sample."""
        try:
            if not self.lineEdit_SampTime.text() or float(self.lineEdit_SampTime.text()) > 120 or float(
                    self.lineEdit_SampTime.text()) < 0.1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0.1 and 120""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_SampTime.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0.1 and 120""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_SampTime.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_SampTime.setText('1')

    def csi_chk(self):
        """Sampling Intervals: The time between data collections during the acquisition time."""
        try:
            if not self.lineEdit_SampIntrvls.text() or float(self.lineEdit_SampIntrvls.text()) > 10 or float(
                    self.lineEdit_SampIntrvls.text()) < 0.001:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0.001 and 10""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_SampIntrvls.setText('0.01')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0.001 and 10""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_SampIntrvls.setText('0.01')
        except Exception as e:
            print(e)
            self.lineEdit_SampIntrvls.setText('0.01')

    def r2avg_chk(self):
        """Raw to Average: Number of samples to be collected and averaged between two sampling intervals."""
        try:
            if not self.lineEdit_Raw2Avrg.text() or float(self.lineEdit_Raw2Avrg.text()) > 101 or float(
                    self.lineEdit_Raw2Avrg.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 0 and 101""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_Raw2Avrg.setText('10')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 0 and 101""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_Raw2Avrg.setText('10')
        except Exception as e:
            print(e)
            self.lineEdit_Raw2Avrg.setText('10')

    def itm_chk(self):
        """Incubation Time: Incubation time in minutes."""
        try:
            if not self.lineEdit_IncubTime.text() or float(self.lineEdit_IncubTime.text()) > 180 or float(
                    self.lineEdit_IncubTime.text()) < 1:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 1 and 180""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_IncubTime.setText('15')
            else:
                return self.line
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 1 and 180""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_IncubTime.setText('15')
        except Exception as e:
            print(e)
            self.lineEdit_IncubTime.setText('15')

    def itp_chk(self):
        """Incubation Temperature: The incubatiobn temperature will be adjusted on the defined temperature +/- 2C."""
        try:
            if not self.lineEdit_IncubTemp.text() or float(self.lineEdit_IncubTemp.text()) > 45 or float(
                    self.lineEdit_IncubTemp.text()) < 15:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 15 and 45C""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_IncubTemp.setText('30')
            else:
                return self.lineEdit_IncubTemp.text()
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 15 and 15""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_IncubTemp.setText('30')
        except Exception as e:
            print(e)
            self.lineEdit_IncubTemp.setText('30')

    def bf_chk(self):
        """Blower Status: This module could be turned off in case the incubation occurs under and external gas source."""
        return str(self.comboBox_BlowerStat.currentText())

    def adcr_chk(self):
        """Sampling ADC reading Mode: The default setting is Slow for Chemiluminescence measuremnents."""
        return str(self.comboBox_SampReadMod.currentText())

    def pmv_chk(self):
        """Silicon Photomultiplier Power Set: This module supplies the HV required for the SiPM to operate."""
        try:
            if not self.lineEdit_PMV.text() or float(self.lineEdit_PMV.text()) > 35 or float(
                    self.lineEdit_PMV.text()) < 25:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value between 25 and 35""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_PMV.setText('32')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value between 25 and 35""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_PMV.setText('32')
        except Exception as e:
            print(e)
            self.lineEdit_PMV.setText('32')

    def adcg_chk(self):
        """Silicon Photomultiplier ADC gain: refer to ADS1232 datasheet - default value is 1."""
        try:
            if not self.lineEdit_ADCGain.text() or int(self.lineEdit_ADCGain.text()) not in [1, 2, 64, 128]:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value: 1, 2, 64, 128""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_ADCGain.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value: 1, 2, 64, 128""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_ADCGain.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_ADCGain.setText('1')

    def adcs_chk(self):
        """Silicon Photomultiplier ADC gain: refer to the ADS1232 datasheet - default value is 1."""
        try:
            if not self.lineEdit_ADCSpd.text() or int(self.lineEdit_ADCSpd.text()) not in [1, 2]:
                msg = QtWidgets.QMessageBox()
                msg.setText("""Please enter a valid value: 1, 2""")
                msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.exec_()
                self.lineEdit_ADCSpd.setText('1')
        except ValueError:
            msg = QtWidgets.QMessageBox()
            msg.setText("""Please enter a valid value: 1, 2""")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
            self.lineEdit_ADCSpd.setText('1')
        except Exception as e:
            print(e)
            self.lineEdit_ADCSpd.setText('1')
    
    def smth_chk(self):
        """Data Smoothing Algorithm: Runs the smoothing algorithm on the collected raw data."""
        self.algo = self.comboBox_Smt.currentText()
        self.order = self.comboBox_SGorders.currentText()
        return [self.algo, self.order] 

    def progress_status(self, n):
        self.statusbar.showMessage(f'{n}%')

    def error_report(self, tpl):
        self.textBrowser.append(f'THREAD: ERROR:\n{tpl}')

    def thread_completed(self):
        self.statusbar.showMessage("THREAD: Done.")

    def writer(self, txt, font_size=8, color='green'):
        self.textBrowser.setTextColor(QtGui.QColor(f'{color}'))
        self.textBrowser.setFontPointSize(10)
        for idx, char in enumerate(txt):
            self.textBrowser.insertPlainText(char)
            QtTest.QTest.qWait(20)
        
    def pen(self, size, color):
        return f"<font size='{size}' color='{color}'>"
       
    def sampling_mod_status(self):
        if self.checkBox_SampMod.isChecked():
            self.lineEdit_SampQuietTime.setDisabled(False)
            self.lineEdit_NumbSamps.setDisabled(False)
            self.lineEdit_SampTime.setDisabled(False)
            self.lineEdit_SampIntrvls.setDisabled(False)
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
            self.lineEdit_SampIntrvls.setDisabled(True)
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
        if self.checkBox_DataSmth.isChecked():
            self.comboBox_Smt.setDisabled(False)
            self.comboBox_SGorders.setDisabled(False)

        else:
            self.comboBox_Smt.setDisabled(True)
            self.comboBox_SGorders.setDisabled(True)
 
    def serial_port(self):
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

                # serial_chk_worker = Worker(self.writer,"\nEstablishing connection via serial port\nScanning serial ports...\nAvailable port: {}\n".format(serial_port), color='green')
                # self.threadpool.start(serial_chk_worker)
                # self.textBrowser.append("\nEstablishing connection via serial port\nScanning serial ports...")
                # self.textBrowser.append("\nAvailable port: {}\n".format(serial_port))
                self.writer("\nEstablishing connection via serial port\nScanning serial ports...")
                self.writer(f"\nAvailable port: {serial_port}\n")

                if serial_port:
                    # worker_serial2 = Worker(self.writer, "Connection established.\n--------------------------------------".format(serial_port))
                    # self.timer.singleShot(6000, lambda: self.threadpool.start(worker_serial2))
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
            self.pen(2, 'red') + "Failed to communicate via Serial!" + "</font>")
            self.textBrowser.append(str(e) + "\n")
            return self.serial_connection

    def connection_status(self):
        # self.actionConnection.setIcon(QtGui.QIcon(":/Icons/disconnect.icns"))
        if not self.serial_connection:
            self.serial_port()
            QtTest.QTest.qWait(1000)
            self.textBrowser.append(
                self.pen(2, 'cyan') + "Connection established via Serial port." + "</font>")
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
        self.content = ''
        delay = 1000  # in ms
        print('Waiting for invitation', end='')
        self.statusbar.showMessage('Waiting for invitation')
        while b'sr_receiver: READY\n' not in self.operator.read_all():
            # self.timer.singleShot(1000, lambda: print('.', end=''))
            print('.', end='')
            QtTest.QTest.qWait(delay)
        print('\nInvited, sending GO!')
        self.statusbar.showMessage('Invited, sending GO!')

        while b'got it.\n' not in self.operator.read_all():
            self.operator.write('go#'.encode())
            # self.timer.singleShot(1000, lambda: self.operator.write('go#'.encode()))
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
                print(f'Data larger than {self.packet_size} chars, calling Chopper...')
                for idx, data in enumerate([chunk for chunk in chopper(command)]):
                    print(f'packet[{idx}]: {data} --- length: {len(data)} chars --- size: {sys.getsizeof(data)}')
                    self.operator.write(data.encode())
                    QtTest.QTest.qWait(delay)
                    resp = self.operator.read_all()
                    # resp = self.timer.singleShot(1000, lambda: self.operator.read_all())
                    print(resp)
                    if 'EOF received.\n' in resp.decode():
                        print('_LucidSens: EOF received in first run, file was sent successfully.')
                        pck_size_tot += sys.getsizeof(data)
                    elif b'got it.\n' in resp:
                        print(f'packet [{ixd}] received on the first try.')
                        pck_size_tot += sys.getsizeof(data)
                    else:
                        print('sending packet again: {}', end='')
                        while True:
                            print('.', end='')
                            self.operator.write(data.encode())
                            QtTest.QTest.qWait(delay)
                            resp = self.operator.read_all()
                            # resp = self.timer.singleShot(1000, lambda: self.operator.read_all())
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
                self.statusbar.showMessage('Sending...')
                print(f'Data not larger than {self.packet_size} chars, no need to call the Chopper.')
                command += '*#'
                self.operator.write(command.encode())
                QtTest.QTest.qWait(delay)
                resp = self.operator.read_all()
                # resp = self.timer.singleShot(1000, lambda: self.operator.read_all())
                print(resp)
                if 'EOF received.' in resp.decode():
                    print('\n_LucidSens: EOF received by LS on the first try.')
                    self.statusbar.showMessage('Command was Sent.')
                    pck_size_tot += sys.getsizeof(command)
                
                else:
                    # print('sending packet again', end='')
                    while True:
                        self.operator.write(command.encode())
                        print('.', end='')
                        QtTest.QTest.qWait(delay)
                        resp = self.operator.read_all()
                        # resp = self.timer.singleShot(1000, lambda: self.operator.read_all())
                        print(resp)
                        if 'EOF received.' in resp.decode():
                            print('\n_LucidSens: EOF received in retry.')
                            pck_size_tot += sys.getsizeof(command)
                            break
                        elif b'got it.' in self.operator.read_all():
                            # print('\n_LucidSens: packet sent in retry.')
                            pck_size_tot += sys.getsizeof(command)
                            break
                        else:
                            # QtTest.QTest.qWait(delay)
                            pass
                    self.statusbar.showMessage('Command was sent.')
                    print('Packet eventually received by LucidSens.')

            print(f'Took {(time.time() - t0)} seconds to {pck_size_tot} bytes.')
            
            ### RECEIVER ###
            # print('\nReceiving', end='')
            self.statusbar.showMessage('Receiving...')
            while '*' not in self.content:
                try:
                    QtTest.QTest.qWait(delay)
                    data = self.operator.read_all()
                    # data = self.timer.singleShot(1000, lambda: self.operator.read_all())
                    data_decd = data.decode()
                    print(data_decd)
                    if '#' in data_decd and data_decd[:-2] not in self.content:
                        if data_decd[-2] == '*':
                            self.content += data_decd[:-1]
                            print('\nResponse received!')
                            self.statusbar.showMessage('Response is received')
                            # self.operator.write('EOF received.#'.encode())
                            break
                        elif data_decd[-2] == '_':
                            # if 'size' in blah
                            self.content += data_decd[:-2]
                            self.operator.write('got it.#'.encode())
                            print('.', end='')
                            QtTest.QTest.qWait(delay)
                        else:
                            pass
                    else:
                        QtTest.QTest.qWait(delay)
                        pass
                except:
                    pass
            print(f'\nResponse: {self.content}')
            if '*' in self.content:
                self.operator.write('EOF received.#'.encode())
                with open('resp.txt', 'w') as raw_resp:
                    raw_resp.write(self.content[:-1])
                print('Processing the response.')
                self.statusbar.showMessage('Processing the response...')
                with open('resp.txt', 'r') as resp:
                    for line in resp:
                        if 'LS: wfcreds was updated.' in line:
                            print('wfcreds created.')
                            self.textBrowser.append('Wifi credetntials were updated on LucidSens.')
                            # resp.close()
                            # return "wfcreds created."
                            # message
                        if 'LS: incubation initialised.' in line:
                            self.textBrowser.append('Incubation initialised.')
                            print('incubation initiated.')
                            # return 'incubation initialised.' 
                        else:
                            print(f'response: {line}')
                            # return line

        except KeyboardInterrupt:
            print('Aborted!')
        except Exception as e:
            print(e)
        return 'Exiting Sender_Receiver.'

    def test(self):
        while not os.path.exists('resp.txt'):
            pass
        try:
            with open('resp.txt', 'r') as f:
                for line in f:
                    if eval(line)['header'] == 'test_astroid':
                        print('Test_Astroid list is received, illustrating...')
                        list_t = eval(line)['body']
                    else:
                        print('Something is wrong with the received list.')

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
                    QtTest.QTest.qWait(10)
                    p2.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][1], pen=pg.mkPen('k', width=1))
                    QtTest.QTest.qWait(10)
                    p2.plot(title="Connection Test", x=list_t[i][0], y=list_t[i][2], pen=pg.mkPen('k', width=1))
                    QtTest.QTest.qWait(10)

            txt = "\nSerial port is up and running.\n----------------------------------------"
            # txt_worker = Worker(self.writer, txt, color='green')
            self.textBrowser.append("\nSerial port is up and running.\n----------------------------------------")
            # self.threadpool.start(txt_worker)
            
            p2.clear()
            p2.showGrid(x=True, y=True, alpha=1)

        except Exception as e:
            print(e)

    def run_test(self):
        if os.path.exists("resp.txt"):
            os.remove("resp.txt")

        command = ({'header': 'test'})
        command.update({'body': {'it': int(self.comboBox.currentText())}})
        jsnd_cmd = json.dumps(command)
        # jsnd_cmd += '*#'
        print(jsnd_cmd, type(jsnd_cmd))

        if self.serial_connection:
            test_worker = Worker(self.serial_sndr_recvr, jsnd_cmd)
            test_worker.signals.DONE.connect(self.thread_completed)
            # test_worker.signals.PROGRESS.connect(self.progress_status)
            test_worker.signals.ERROR.connect(self.error_report)
            self.threadpool.start(test_worker)
            print(f'active threads after running test: {self.threadpool.activeThreadCount()}')
            # self.timer.singleShot(15000, lambda: self.test())
            QtTest.QTest.qWait(20000)
            self.test()
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
        if self.checkBox_IncubMod.isChecked():
            command.update({'body': {
                'it': float(self.lineEdit_IncubTime.text()),
                'ip': float(self.lineEdit_IncubTemp.text()),
                'bf': str(self.comboBox_BlowerStat.currentText())}})

        if self.checkBox_SampMod.isChecked():
            command.update({'body': {
                'sqt': float(self.lineEdit_SampQuietTime.text()),
                'sn': int(self.lineEdit_NumbSamps.text()),
                'st': float(self.lineEdit_SampTime.text()),
                'si': float(self.lineEdit_SampIntrvls.text()),
                'r2avg': int(self.lineEdit_Raw2Avrg.text()),
                'pmr': str(self.comboBox_SampReadMod.currentText()),
                'pv': float(self.lineEdit_PMV.text()),
                'ag': int(self.lineEdit_ADCGain.text()),
                'as': int(self.lineEdit_ADCSpd.text())}})

        jsnd_cmd = json.dumps(command)
        # jsnd_cmd += '*#'
        print(jsnd_cmd, type(jsnd_cmd))

        if self.serial_connection:
            run_worker = Worker(self.serial_sndr_recvr, jsnd_cmd)
            run_worker.signals.DONE.connect(self.thread_completed)
            # test_worker.signals.PROGRESS.connect(self.progress_status)
            run_worker.signals.ERROR.connect(self.error_report)
            self.threadpool.start(run_worker)
            self.threadpool.waitForDone()
            # self.timer.singleShot(15000, lambda: self.test())

        else:
            self.textBrowser.append("No available connections to the LucidSens.")
            self.textBrowser.append("Please re-establish your connection first.")
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the" + self.pen(2, 'blue') +
                        " Lucid" + "</font>" + self.pen(2, 'orange') + "Sens!" + "</font>" + "\n" +
                        "please check your connections and try again.")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()

    def about_us(self):
        msg = QtWidgets.QMessageBox()
        msg.setText("""
        Copyright © 2019 LucidSens(M. Amin Haghighatbin)

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
        self.setText(f"{self.title} is now presented.")

        if self.AreaBox.isChecked():
            self.setText(f"The Area under curve is equal to: {area}")
            self.graphicsView.clear()
            p2 = self.graphicsView.addPlot(title=self.title, x=data_x, y=data_y, pen='r', fillLevel=0, fillBrush="b")
            p2.showGrid(x=True, y=True, alpha=1)
            p2.setLabel('bottom', 'x', **{'color': 'white', 'font-size': '12px'})
            p2.setLabel('left', 'f(x)', **{'color': 'white', 'font-size': '12px'})

    def stop(self):
        command = ({'header': 'kill'})
        jsnd_cmd = json.dumps(command)
        jsnd_cmd += '*#'
        msg = QtWidgets.QMessageBox()
        QtTest.QTest.qWait(1000)
        msg.setText("Experiment canceled.")
        self.textBrowser.append("LucidSens stopped.")
        msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
        msg.setWindowTitle("Warning")
        msg.exec_()

    def preferences(self):
        self.prefs = Preferences()
        self.prefs.buttonBox.accepted.connect(self.preferences_accept)
        self.prefs.buttonBox.rejected.connect(self.preferences_reject)
        self.prefs.show()
    
    def preferences_accept(self):
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
        self.prefs.close()

    def wifi_panel(self):
        self.wf = WifiSettings()
        self.wf.buttonBox.accepted.connect(self.wf_accept)
        self.wf.buttonBox.rejected.connect(self.wf_reject)
        self.wf.show()

    def wf_accept(self):
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
        print(jsnd_cmd, f'--> length: {len(jsnd_cmd)}')
        if self.serial_connection:
            wf_worker = Worker(self.serial_sndr_recvr, jsnd_cmd)
            wf_worker.signals.DONE.connect(self.thread_completed)
            # test_worker.signals.PROGRESS.connect(self.progress_status)
            wf_worker.signals.ERROR.connect(self.error_report)
            self.threadpool.start(wf_worker)
            print(f"active threads after running wifi settings: {self.threadpool.activeThreadCount()}")

        else:
            self.textBrowser.append("No available connections to the LucidSens.")
            self.textBrowser.append("Please re-establish your connection first.")
            msg = QtWidgets.QMessageBox()
            msg.setText("No available connections with the LucidSens, please check your connections and try again.")
            msg.setDefaultButton(QtWidgets.QMessageBox.Ok)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.exec_()
        self.wf.close()

    def wf_reject(self):
        print('No wifi settings has been updated.')
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