import matplotlib.pyplot as plt
import sys
import enum
import json
import os
import glob
import re
from pathlib import Path
from mpldatacursor import datacursor

from PyQt5.QtWidgets import QHeaderView, QAbstractItemView, QMessageBox, QMainWindow, QApplication, QDialog, \
    QVBoxLayout, QLineEdit, QPushButton, QLabel, QTextEdit, QFileDialog, QComboBox
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QDate, QSortFilterProxyModel, QSettings

import pandas as pd
import numpy as np
import pypac
import requests
from openpyxl import load_workbook
from requests.auth import HTTPProxyAuth
from datetime import datetime, timedelta
from pandas.plotting import register_matplotlib_converters
from matplotlib.patches import Rectangle
from teap_data import teap_required_points, teap_weights, teap_categories, spreadsheet_cells
from GetDataFromComet import GetDataFromCometWindow
from ui.teap_report_main import Ui_MainWindow

plt.rcParams["hatch.linewidth"] = 2

__version__ = '0.0.9'
name = "ROMP TEAPTracker"

register_matplotlib_converters()


class competency_columns(enum.Enum):
    competency = 0
    score = 1
    feedback = 2
    submission_status = 3
    grading_status = 4


competency_reference_data = {
    '1': {'complete_colour': '#948a54', 'incomplete_colour': '#eeece1', 'total_points': 15},
    '2': {'complete_colour': '#f79646', 'incomplete_colour': '#fde9d9', 'total_points': 50},
    '3': {'complete_colour': '#4bacc6', 'incomplete_colour': '#daeef3', 'total_points': 80},
    '4': {'complete_colour': '#76923c', 'incomplete_colour': '#eaf1dd', 'total_points': 100},
    '5': {'complete_colour': '#8064a2', 'incomplete_colour': '#e5dfec', 'total_points': 80},
    '6': {'complete_colour': '#c0504d', 'incomplete_colour': '#f2dbdb', 'total_points': 35},
    '7': {'complete_colour': '#4f81bd', 'incomplete_colour': '#dbe5f1', 'total_points': 15},
    '8': {'complete_colour': '#f6dd4e', 'incomplete_colour': '#ffffcc', 'total_points': 25}
}

cache_location = 'cached_data'


class MainWindow(QMainWindow):
    """
    Main window for the application, this houses most of the logic and visible components
    """

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(f'{name} {__version__}')

        column_headers = ['Competency', 'Score', 'Feedback', 'Submission Status', 'Last modified date',
                          'Grading Status', 'Grading date']

        system_location = os.path.dirname(os.path.abspath(sys.argv[0]))
        QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, system_location)
        self.settings = QSettings("settings.ini", QSettings.IniFormat)

        show_plan_in_tracking_plot = self.settings.value('Appearance/show_plan_in_tracking_plot', type=bool)
        if show_plan_in_tracking_plot:
            self.ui.checkBoxShowPlan.setChecked(True)

        show_extrapolation_in_tracking_plot = self.settings.value('Appearance/show_extrapolation_in_tracking_plot',
                                                                  type=bool)
        if show_extrapolation_in_tracking_plot:
            self.ui.checkBoxShowExtrapolation.setChecked(True)

        months_to_extrapolate_in_tracking_plot = self.settings.value('Extrapolation/months_to_extrapolate', type=int)
        if months_to_extrapolate_in_tracking_plot:
            self.ui.spinBoxMonthsToExtrapolate.setValue(months_to_extrapolate_in_tracking_plot)

        self.assessed_competency_model = QStandardItemModel()
        self.assessed_competency_model.setHorizontalHeaderLabels(column_headers)
        self.assessed_competency_proxy_model = MultiColumnProxyModel()
        self.assessed_competency_proxy_model.setSourceModel(self.assessed_competency_model)
        self.ui.tableViewModules.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.tableViewModules.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ui.tableViewModules.setModel(self.assessed_competency_proxy_model)

        today = QDate.currentDate()
        self.ui.dateEditPlanStart.setDate(today)
        self.ui.dateEditPlanEnd.setDate(today.addDays(60))

        self.ui.tableViewModules.setColumnHidden(competency_columns.feedback.value, True)
        self.ui.tableViewModules.setSortingEnabled(True)
        self.ui.tableViewModules.verticalHeader().setVisible(False)
        for col in range(self.assessed_competency_model.columnCount()):
            self.ui.tableViewModules.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)

        self.ui.comboBoxTEAPLength.addItems(['3', '4', '5'])

        # Setup the competency info model. This contains the data from the CTG
        comp_info = pd.read_csv('TEAPCTGData.csv')
        self.competency_info_data_model = QStandardItemModel()
        self.competency_info_data_model.setHorizontalHeaderLabels(comp_info.columns)
        self.competency_info_proxy_model = QSortFilterProxyModel()
        self.competency_info_proxy_model.setFilterKeyColumn(0)
        self.competency_info_proxy_model.setFilterRegExp('a^')  # Match nothing to begin with
        self.competency_info_proxy_model.setSourceModel(self.competency_info_data_model)
        self.ui.tableViewCategoryOverview.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ui.tableViewCategoryOverview.verticalHeader().hide()
        self.ui.tableViewCategoryOverview.setModel(self.competency_info_proxy_model)
        for index, row in comp_info.iterrows():
            new_row = [QStandardItem(str(row['Comp'])),
                       QStandardItem(self.trim_competency_data_text(row['RIOTs'])),
                       QStandardItem(self.trim_competency_data_text(row['Evidence'])),
                       QStandardItem(self.trim_competency_data_text(row['Assessment'])),
                       QStandardItem(self.trim_competency_data_text(row['Criteria']))
                       ]
            self.competency_info_data_model.appendRow(new_row)

        for col in range(self.competency_info_data_model.columnCount()):
            self.ui.tableViewCategoryOverview.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)

        for cat in teap_weights:
            if len(cat) != 1:
                teap_weights[cat] = teap_weights[cat] * competency_reference_data[cat[0]]['total_points'] / \
                                    teap_weights[cat[0]]

        self.data = None
        self.tracking_df = None
        self.getCometDataWindow = None
        self.datacursor = None
        self.loaded_data = {}
        self.category_overview_rectangles = []
        self.training_plan = {'competencies': [], 'notes': {}}

        self.ui.splitterCategoryOverview.setSizes((1, 1))

        self.ui.pushButtonLoadPreviousData.clicked.connect(self.get_new_data_from_comet)
        self.ui.checkBoxOverviewPlotRelative.clicked.connect(self.update_overview_plot)
        self.ui.tableViewModules.selectionModel().selectionChanged.connect(self.competency_table_view_selection_changed)
        self.ui.comboBoxTEAPLength.currentTextChanged.connect(self.update_tracking_plot)
        self.ui.dateEditProgramStart.dateChanged.connect(self.update_tracking_plot)
        self.ui.pushButtonLoadSelectedCachedFile.clicked.connect(self.load_cached_data)

        self.ui.dateEditPlanStart.dateChanged.connect(lambda: self.update_tracking_plot())
        self.ui.dateEditPlanEnd.dateChanged.connect(lambda: self.update_tracking_plot())

        self.ui.checkBoxShowPlan.clicked.connect(lambda: self.update_tracking_plot())
        self.ui.checkBoxShowExtrapolation.clicked.connect(lambda: self.update_tracking_plot())
        self.ui.spinBoxMonthsToExtrapolate.valueChanged.connect(lambda: self.update_tracking_plot())
        self.ui.checkBoxShowPlan.clicked.connect(lambda: self.settings.setValue('Appearance/show_plan_in_tracking_plot',
                                                                                self.ui.checkBoxShowPlan.isChecked()))
        self.ui.checkBoxShowExtrapolation.clicked.connect(lambda: self.save_extrapolation_settings())
        self.ui.spinBoxMonthsToExtrapolate.valueChanged.connect(lambda: self.save_extrapolation_settings())

        self.show()

        self.search_for_cached_data()
        # If there isn't any cached data, pop up a dialog to help the user download their data
        if self.ui.comboBoxCachedData.count() == 0:
            download_dialog = InitialDownloadDialog()
            if download_dialog.exec() == QDialog.Accepted:
                self.getCometDataWindow = GetDataFromCometWindow(session=download_dialog.session)
                if self.getCometDataWindow.exec():
                    self.handle_new_data_from_gui()
            else:
                pass
        # If there is only one cached file, load it
        elif self.ui.comboBoxCachedData.count() == 1:
            self.ui.comboBoxCachedData.setCurrentIndex(
                0)  # This might be unneeded, but I feel it's safer to leave it in
            self.load_data_from_filepath(self.ui.comboBoxCachedData.currentData())
        # If there is more than 1, show a dialog to allow the user to choose
        elif self.ui.comboBoxCachedData.count() > 1:
            json_files = glob.glob(f'{cache_location}/*.json')
            registrar_list = {}
            for file in json_files:
                try:
                    with open(file, 'r') as f:
                        data = json.load(f)
                        user_name = data['profile_data']['name']
                        registrar_list[user_name] = file
                except:
                    pass
            load_registrar_dialog = LoadDataDialog(registrar_list=registrar_list)
            if load_registrar_dialog.exec() == QDialog.Accepted:
                self.load_data_from_filepath(load_registrar_dialog.load_filepath)
            else:
                pass

        # Need to connect these afterwards to make sure they don't overwrite the loaded settings
        self.ui.comboBoxGradingFilter.currentTextChanged.connect(self.update_score_filters)
        self.ui.comboBoxSubmissionFilter.currentTextChanged.connect(self.update_score_filters)

        self.ui.comboBoxTEAPLength.currentTextChanged.connect(self.save_teap_settings)
        self.ui.dateEditProgramStart.dateChanged.connect(self.save_teap_settings)

        self.ui.MplWidgetCategoryOverview.canvas.mpl_connect('motion_notify_event', self.update_category_sidepane)
        self.ui.MplWidgetCategoryOverview.canvas.mpl_connect('button_press_event', self.update_category_plan)
        self.ui.dateEditPlanStart.dateChanged.connect(lambda: self.updated_plan_dates())
        self.ui.dateEditPlanEnd.dateChanged.connect(lambda: self.updated_plan_dates())

        self.ui.actionExport_official_spreadsheet.triggered.connect(self.export_official_spreadsheet)


    def load_data_from_filepath(self,filepath : str):
        if filepath is not None:
            with open(filepath, 'r') as f:
                self.data = json.load(f)
                if 'training_plan' in self.data:
                    self.training_plan = self.data['training_plan']
                    if not 'notes' in self.training_plan:
                        self.training_plan['notes'] = {}
                self.new_data_loaded()

    def save_extrapolation_settings(self):
        self.settings.setValue('Appearance/show_extrapolation_in_tracking_plot',
                               self.ui.checkBoxShowExtrapolation.isChecked())
        self.settings.setValue('Extrapolation/months_to_extrapolate', self.ui.spinBoxMonthsToExtrapolate.value())

    def updated_plan_dates(self):
        qdate_start = self.ui.dateEditPlanStart.date()
        self.training_plan['start_date'] = datetime.strftime(
            datetime(qdate_start.year(), qdate_start.month(), qdate_start.day()), '%Y-%m-%d %H:%M:%S')
        qdate_end = self.ui.dateEditPlanEnd.date()
        self.training_plan['end_date'] = datetime.strftime(
            datetime(qdate_end.year(), qdate_end.month(), qdate_end.day()), '%Y-%m-%d %H:%M:%S')

        self.save_data()

    def trim_competency_data_text(self, text):
        txt = str(text)
        final_text = txt.replace('\n', ' ')
        final_text = final_text.replace('o  ', '\no ')
        return final_text[1:]  # Return whole string but the first newline

    def update_category_sidepane(self, event):
        for rec in self.category_overview_rectangles:
            if rec.contains(event)[0]:
                self.competency_info_proxy_model.setFilterRegExp(rec.get_label())

    def update_category_plan(self, event):
        for rec in self.category_overview_rectangles:
            if rec.contains(event)[0]:
                if event.button == 1:  # Left click
                    self._set_rect_selected(rec)
                if event.button == 2:
                    if rec.get_label() in self.training_plan['notes'].keys():
                        current_note = self.training_plan['notes'][rec.get_label()]
                    else:
                        current_note = ''

                    update_note_dialog = UpdateNoteDialog(current_note=current_note)
                    if update_note_dialog.exec() == QDialog.Accepted:
                        self.training_plan['notes'][rec.get_label()] = update_note_dialog.note
                    else:
                        pass
                elif event.button == 3:  # right click
                    self._set_rect_unselected(rec)

                self.update_tracking_plot()

                self.ui.MplWidgetCategoryOverview.canvas.flush_events()
                self.ui.MplWidgetCategoryOverview.canvas.draw()
        self.save_data()

    def _set_rect_selected(self, rec):
        # A bit hacky, but works. This stores the old edge color back as a property on the rectangle, so if we unselect
        # it we know what to change it back to this. This method is not ideal, as the old_edgecolor property is made up
        # by me, and not a standard property of te rectangle
        rec.old_edgecolor = rec.get_edgecolor()
        rec.set_edgecolor('Blue')
        rec.set_linewidth(3.5)
        rec.set_zorder(1000)

        competency = rec.get_label()
        if competency not in self.training_plan['competencies']:
            self.training_plan['competencies'].append(competency)

    def _set_rect_unselected(self, rec):
        # This is only true if it's been turned on atleast once
        if hasattr(rec, 'old_edgecolor'):
            rec.set_edgecolor(rec.old_edgecolor)
            rec.set_linewidth(1)
            rec.set_zorder(1)

            competency = rec.get_label()
            if competency in self.training_plan['competencies']:
                self.training_plan['competencies'].remove(competency)

    def search_for_cached_data(self):
        json_files = glob.glob(f'{cache_location}/*.json')
        for file in json_files:
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    user_name = data['profile_data']['name']
                    user_id = Path(file).stem
                    self.loaded_data[user_id] = self.generate_tracking_data(data)
                self.ui.comboBoxCachedData.addItem(user_name, file)

            except Exception:
                pass

    def load_cached_data(self):
        filepath = self.ui.comboBoxCachedData.currentData()
        if filepath is not None:
            with open(filepath, 'r') as f:
                self.data = json.load(f)
                self.new_data_loaded()

    def update_score_filters(self):
        self.assessed_competency_proxy_model.set_grading_status_filter(self.ui.comboBoxGradingFilter.currentText())
        self.assessed_competency_proxy_model.set_submission_status_filter(
            self.ui.comboBoxSubmissionFilter.currentText())

    def competency_table_view_selection_changed(self, index):
        incidies = index.indexes()
        if len(incidies) != 0:
            current_row_number = self.assessed_competency_proxy_model.mapToSource(incidies[0]).row()
            feedback = self.assessed_competency_model.item(current_row_number, competency_columns.feedback.value).text()
            self.ui.textEditCompetencyFeedback.setText(feedback)
        else:
            self.ui.textEditCompetencyFeedback.setText('')

    def update_models_from_data(self):
        # Goes through self.data and populates the assessed_competency_model with rows
        # Each row is a competency
        # If there were row present before, they are cleared
        if self.data is not None:
            self.assessed_competency_model.setRowCount(0)

        for competency in self.data['competencies']:
            new_row = [QStandardItem(str(competency['name'])),
                       QStandardItem(str(competency['score'])),
                       QStandardItem(str(competency['feedback'])),
                       QStandardItem(str(competency['submission_status'])),
                       QStandardItem(str(competency['last_modify_date'])),
                       QStandardItem(str(competency['grading_status'])),
                       QStandardItem(str(competency['grade_date']))]
            self.assessed_competency_model.appendRow(new_row)

    def save_data(self):
        if self.data is not None:
            user_id = self.data['profile_data']['user_id']

            if not os.path.exists(cache_location):
                os.mkdir(cache_location)

            with open(f'{cache_location}/{user_id}.json', 'w') as f:
                self.data['training_plan'] = self.training_plan
                json.dump(self.data, f, default=str, indent=4)

            # Loading the data back ensures consistency of what we've saved, both data and types
            self.load_data_from_filepath(f'{cache_location}/{user_id}.json')

    def get_new_data_from_comet(self):
        if self.ui.lineEditCometUsername.text() == '' or self.ui.lineEditCometPassword.text() == '':
            msg_box = QMessageBox()
            msg_box.setWindowTitle('Error')
            msg_box.setText("Neither username or password can be blank")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            return None
        session = make_session(username=self.ui.lineEditCometUsername.text(),
                                    password=self.ui.lineEditCometPassword.text())
        if session is None:
            return
        self.getCometDataWindow = GetDataFromCometWindow(session)

        if self.getCometDataWindow.exec():
            self.handle_new_data_from_gui()

    def handle_new_data_from_gui(self):
        if self.getCometDataWindow.competency_data is not None:
            new_data = self.getCometDataWindow.competency_data
            # We'll still keep the old start date and length, as the website is probably wrong and the user manually
            # fixed it
            if self.data is not None:
                new_data['profile_data']['start_date'] = self.data['profile_data']['start_date']
                new_data['profile_data']['program_length'] = self.data['profile_data']['program_length']
            self.data = new_data
            self.save_data()
            self.getCometDataWindow = None
            self.new_data_loaded()
        else:
            return

        msg_box = QMessageBox()
        msg_box.setWindowTitle('Success')
        msg_box.setText("Data downloaded successfully")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.exec()

        self.ui.tabWidgetMain.setCurrentIndex(0)

    def save_teap_settings(self):
        if self.data is not None:
            qdate = self.ui.dateEditProgramStart.date()
            self.data['profile_data']['start_date'] = datetime.strftime(datetime(qdate.year(), qdate.month(), qdate.day()),
                                                                        '%Y-%m-%d %H:%M:%S')
            self.data['profile_data']['program_length'] = self.ui.comboBoxTEAPLength.currentText()

            self.save_data()

    def new_data_loaded(self):
        # Called whenever new data is loaded to update the state of the application, e.g. models, plots etc.
        program_start_date = datetime.strptime(self.data['profile_data']['start_date'], '%Y-%m-%d %H:%M:%S')
        self.ui.dateEditProgramStart.setDate(
            QDate(program_start_date.year, program_start_date.month, program_start_date.day))
        self.ui.comboBoxTEAPLength.setCurrentText(str(self.data['profile_data']['program_length']))

        if 'start_date' in self.training_plan:
            training_program_start_date = datetime.strptime(self.training_plan['start_date'], '%Y-%m-%d %H:%M:%S')
            self.ui.dateEditPlanStart.setDate(QDate(training_program_start_date.year, training_program_start_date.month,
                                                    training_program_start_date.day))

        if 'end_date' in self.training_plan:
            training_program_end_date = datetime.strptime(self.training_plan['end_date'], '%Y-%m-%d %H:%M:%S')
            self.ui.dateEditPlanEnd.setDate(
                QDate(training_program_end_date.year, training_program_end_date.month, training_program_end_date.day))

        self.tracking_df = self.generate_tracking_data(self.data)

        if self.tracking_df is not None:
            self.ui.comboBoxGradingFilter.addItems(['All'] + list(self.tracking_df['grading_status'].unique()))
            self.ui.comboBoxSubmissionFilter.addItems(['All'] + list(self.tracking_df['submission_status'].unique()))

        self.update_models_from_data()
        self.update_category_overview_plot()
        self.update_overview_plot()
        self.update_tracking_plot()
        self.update_misc_stats()
        self.update_score_filters()

    def update_misc_stats(self):
        if self.data is not None and self.tracking_df is not None:
            number_of_signed_off_comps = 0
            number_of_partially_signed_off_comps = 0
            number_waiting_on_grading = 0

            competencies = self.data['competencies']
            for competency in competencies:
                if competency['score'] == 1.0:
                    number_of_signed_off_comps += 1
                elif 0 < competency['score'] < 1.0:
                    number_of_partially_signed_off_comps += 1

                if competency['submission_status'] == 'Submitted' and competency['grading_status'] == 'Not graded':
                    number_waiting_on_grading += 1

            number_of_comps = len(competencies) - 6  # - 6 due to the electives in module 8

            self.ui.labelSignedOffCompetencies.setText(
                f'{number_of_signed_off_comps} [{number_of_signed_off_comps * 100 / number_of_comps:.2f}%]')
            self.ui.labelNonSignedOffCompetencies.setText(
                f'{number_of_comps - number_of_partially_signed_off_comps - number_of_signed_off_comps} '
                f'[{(number_of_comps - number_of_partially_signed_off_comps - number_of_signed_off_comps) * 100 / number_of_comps:.2f}%]')
            self.ui.labelPartialSignedOffCompetencies.setText(
                f'{number_of_partially_signed_off_comps} [{number_of_partially_signed_off_comps * 100 / number_of_comps:.2f}%]')
            self.ui.labelWaitingOnGradingCompetencies.setText(
                f'{number_waiting_on_grading} [{number_waiting_on_grading * 100 / number_of_comps:.2f}%]')
            difference = (self.tracking_df['grade_date'] - self.tracking_df['last_modify_date']).mean().days
            self.ui.labelAverageWaitingTimeForSignOff.setText(f'{difference} days')

    def generate_tracking_data(self, data):
        # This takes the normal data object (i.e. the dictionary returned from the GetDataFromComet dialog or parsed
        # from the saved JSON) and generates a dataframe showing how the points have been updating over time

        if data is None:
            return None

        competencies = data['competencies']
        tracking_df = pd.DataFrame()
        for competency in competencies:
            submission_status = competency['submission_status']
            grading_status = competency['grading_status']
            score = competency['score']
            name = competency['name']

            if competency['last_modify_date'] is not None:
                last_modify_date = datetime.strptime(competency['last_modify_date'], '%Y-%m-%d %H:%M:%S')
            else:
                last_modify_date = pd.NaT

            if competency['grade_date'] is not None:
                grade_date = datetime.strptime(competency['grade_date'], '%Y-%m-%d %H:%M:%S')
            else:
                grade_date = pd.NaT

            tracking_df = tracking_df.append({'submission_status': submission_status, 'grading_status': grading_status,
                                              'score': score, 'last_modify_date': last_modify_date,
                                              'grade_date': grade_date, 'name': name}, ignore_index=True)

        tracking_df['count'] = 1
        tracking_df['cat'] = tracking_df['name'].str[0:5]
        tracking_df['weight'] = tracking_df['name'].str[0:3].map(teap_weights)

        mask = (tracking_df['name'].str[4] == '1') & (~tracking_df['name'].str[0].isin(('1', '7', '8')))
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.2
        mask = (tracking_df['name'].str[4] == '2') & (~tracking_df['name'].str[0].isin(('1', '7', '8')))
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.5
        mask = (tracking_df['name'].str[4] == '3') & (~tracking_df['name'].str[0].isin(('1', '7', '8')))
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.3
        mask = tracking_df['name'].str[0:5] == '1.1.1'

        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.8
        mask = tracking_df['name'].str[0:5] == '1.1.2'
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.2
        mask = tracking_df['name'].str[0:5] == '1.2.1'
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.4
        mask = tracking_df['name'].str[0:5] == '1.2.2'
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.6

        mask = tracking_df['name'].str[0:5] == '7.2.1'
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.6
        mask = tracking_df['name'].str[0:5] == '7.2.2'
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.4
        mask = tracking_df['name'].str[0:5] == '7.4.1'
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.3
        mask = tracking_df['name'].str[0:5] == '7.4.2'
        tracking_df.loc[mask, 'weight'] = tracking_df[mask]['weight'] * 0.7

        tracking_df['weighted_score'] = tracking_df['score'] * tracking_df['weight'] / tracking_df['count'].groupby(
            tracking_df['cat']).transform('sum')
        tracking_df['max_uploaded_score'] = 1 * tracking_df['weight'] / tracking_df['count'].groupby(
            tracking_df['cat']).transform('sum')

        return tracking_df

    def update_tracking_plot(self):
        if self.data is not None and self.tracking_df is not None:
            program_start_qdate = self.ui.dateEditProgramStart.date()
            start_date = datetime(program_start_qdate.year(), program_start_qdate.month(), program_start_qdate.day())
            length_of_program = self.ui.comboBoxTEAPLength.currentText()

            self.ui.MplWidgetTracking.reset_axis(start_date, datetime.now(), 0, 400)

            # Modified plot
            plot_df = self.tracking_df[self.tracking_df['submission_status'] != 'No attempt'].sort_values(
                'last_modify_date')
            modify_dates = plot_df['last_modify_date'].values
            modify_dates = np.append(modify_dates, np.datetime64(datetime.now()))
            total_modified_points = np.array(plot_df['max_uploaded_score'].cumsum())
            total_modified_points = np.append(total_modified_points, total_modified_points[-1])
            self.ui.MplWidgetTracking.canvas.ax.plot(modify_dates, total_modified_points, label='Uploaded',
                                                     drawstyle='steps-post')

            # Graded plot
            plot_df = self.tracking_df[self.tracking_df['grading_status'] == 'Graded'].sort_values('grade_date')
            graded_dates = plot_df['grade_date'].values
            graded_dates = np.append(graded_dates, np.datetime64(datetime.now()))
            total_accepted_points = np.array(plot_df['weighted_score'].cumsum())
            total_accepted_points = np.append(total_accepted_points, total_accepted_points[-1])
            self.ui.MplWidgetTracking.canvas.ax.plot(graded_dates, total_accepted_points, label='Graded',
                                                     drawstyle='steps-post')

            # Expected
            self.ui.MplWidgetTracking.canvas.ax.plot(
                list(datetime(start_date.year + n, start_date.month, start_date.day) for n in
                     range(len(teap_required_points[length_of_program])))
                , teap_required_points[length_of_program], label='Expected')

            def get_unixtime(dt64):
                return dt64.astype('datetime64[s]').astype('int')

            # Plan
            if len(self.training_plan['competencies']) > 0 and self.ui.checkBoxShowPlan.isChecked():
                plan_start_qdate = self.ui.dateEditPlanStart.date()
                plan_start_date = datetime(plan_start_qdate.year(), plan_start_qdate.month(), plan_start_qdate.day())

                plan_end_qdate = self.ui.dateEditPlanEnd.date()
                plan_end_date = datetime(plan_end_qdate.year(), plan_end_qdate.month(), plan_end_qdate.day())

                planned_score = \
                self.tracking_df[self.tracking_df['name'].str.contains('|'.join(self.training_plan['competencies']))][
                    'max_uploaded_score'].sum()

                points_start = np.interp(plan_start_date.timestamp(), [get_unixtime(d) for d in modify_dates],
                                         total_modified_points)
                self.ui.MplWidgetTracking.canvas.ax.plot((plan_start_date, plan_end_date),
                                                         (points_start, points_start + planned_score), label='Plan',
                                                         linestyle='--', color='red')

            # Extrapolation
            if self.ui.checkBoxShowExtrapolation.isChecked():
                today = datetime.now()
                number_of_weeks = self.ui.spinBoxMonthsToExtrapolate.value() * 4
                delta = timedelta(weeks=number_of_weeks)
                before = today - delta
                current_uploaded_points = total_modified_points[-1]

                before_indicies = np.where(modify_dates <= np.datetime64(before))
                if len(before_indicies) == 0:
                    before_uploaded_points = 0
                else:
                    try:
                        before_uploaded_points = total_modified_points[before_indicies[0][-1]]
                    except:
                        before_uploaded_points = 0
                points_per_week = (current_uploaded_points - before_uploaded_points) / number_of_weeks

                # 638 is just a random magic number to ensure it's off the plot so the number is big enough
                final_point = today + timedelta(weeks=638)
                final_points = current_uploaded_points + 638 * points_per_week

                self.ui.MplWidgetTracking.canvas.ax.autoscale(tight=True)
                ylim = self.ui.MplWidgetTracking.canvas.ax.get_ylim()
                xlim = self.ui.MplWidgetTracking.canvas.ax.get_xlim()

                self.ui.MplWidgetTracking.canvas.ax.plot((before, final_point), (before_uploaded_points, final_points),
                                                         color='purple', label='Extrapolation')

                self.ui.MplWidgetTracking.canvas.ax.set_ylim(ylim)
                self.ui.MplWidgetTracking.canvas.ax.set_xlim(xlim)

            self.ui.MplWidgetTracking.canvas.ax.legend()

            # Don't autoscale if it's extrapolating, as the point is off the plot
            if not self.ui.checkBoxShowExtrapolation.isChecked():
                self.ui.MplWidgetTracking.canvas.ax.autoscale(tight=True)
            self.ui.MplWidgetTracking.canvas.flush_events()
            self.ui.MplWidgetTracking.canvas.draw()

    def update_category_overview_plot(self):
        if self.tracking_df is not None:
            self.ui.MplWidgetCategoryOverview.reset_axis()
            self.category_overview_rectangles = []
            ax = self.ui.MplWidgetCategoryOverview.canvas.ax

            row_number = 0
            labels = []

            for module in reversed(teap_categories.keys()):
                for category in reversed(teap_categories[module].keys()):
                    tmp_df = self.tracking_df[self.tracking_df['name'].str.startswith(f'{module}.{category}')]
                    number_of_comps = {1: len(tmp_df[tmp_df['name'].str[4] == '1']),
                                       2: len(tmp_df[tmp_df['name'].str[4] == '2']),
                                       3: len(tmp_df[tmp_df['name'].str[4] == '3'])}
                    for level in ('1', '2', '3'):
                        for comp_number, (index, row) in enumerate(tmp_df[tmp_df['name'].str[4] == level].iterrows()):
                            level_as_int = int(level)
                            offset = (level_as_int - 1) + comp_number / number_of_comps[level_as_int]

                            extra_options = {}
                            if row['score'] == 1:
                                face_color = competency_reference_data[module]['complete_colour']
                                extra_options['edgecolor'] = 'Black'
                            elif row['submission_status'] != 'No attempt':
                                face_color = competency_reference_data[module]['incomplete_colour']

                                extra_options['hatch'] = '///'
                                extra_options['linewidth'] = 0
                                extra_options['edgecolor'] = competency_reference_data[module]['complete_colour']

                                rect2 = Rectangle((offset, row_number), 1 / number_of_comps[level_as_int], 1,
                                                  edgecolor='Black',
                                                  zorder=100, facecolor='none')
                                ax.add_patch(rect2)
                            else:
                                face_color = competency_reference_data[module]['incomplete_colour']
                                extra_options['edgecolor'] = 'Black'

                            rect = Rectangle((offset, row_number), 1 / number_of_comps[level_as_int], 1,
                                             label=f'{module}.{category}.{level}.{comp_number + 1}',
                                             facecolor=face_color, **extra_options)
                            ax.add_patch(rect)
                            self.category_overview_rectangles.append(rect)

                    labels.append(teap_categories[module][category])
                    row_number += 1

            self.update_trainingplan_selected_view()

            ax.set_xlim((0, 3))
            ax.set_ylim((0, row_number))
            ax.set_yticks(list(n + 0.5 for n in range(row_number)))
            ax.set_yticklabels(labels)
            ax.set_xticks((0.5, 1.5, 2.5))
            ax.set_xticklabels(('1', '2', '3'))
            ax.set_xlabel('Level')
            ax.autoscale(tight=True)


            if self.datacursor is None:
                self.datacursor = datacursor(artists=self.category_overview_rectangles,
                                             formatter=self.format_category_overview_note,
                                             axes=ax, hover=True, bbox=dict(alpha=1), hide_button=None, tolerance=1,
                                             keep_inside=True,
                                             arrowprops=dict(alpha=0))

            self.ui.MplWidgetCategoryOverview.canvas.flush_events()
            self.ui.MplWidgetCategoryOverview.canvas.draw()

    def update_trainingplan_selected_view(self):
        # Called to set the correct borders on the competencies part of a training plan
        for rec in self.category_overview_rectangles:
            if rec.get_label() in self.training_plan['competencies']:
                self._set_rect_selected(rec)

    def format_category_overview_note(self, **kwargs):
        comp = kwargs['label']
        if comp in self.training_plan['notes']:
            return self.training_plan['notes'][comp]
        else:
            return None

    def export_official_spreadsheet(self):
        if self.data is not None:
            filepath = QFileDialog.getSaveFileName(self, 'Save spreadsheet', 'CTG v3.6 Progression Monitor Tool.xlsx', '(*.xlsx)')[0]
            if filepath != '':
                if not filepath.endswith('.xlsx'):
                    filepath += '.xlsx'

                workbook = load_workbook('resources/CTG v3.6 Progression Monitor Tool.xlsx')
                worksheet = workbook.active
                worksheet[spreadsheet_cells['name']] = self.data['profile_data']['name']
                worksheet[spreadsheet_cells['program_length']] = int(self.data['profile_data']['program_length'])
                worksheet[spreadsheet_cells['start_date']] = datetime.strptime(self.data['profile_data']['start_date'], '%Y-%m-%d %H:%M:%S')
                worksheet[spreadsheet_cells['todays_date']] = datetime.now()
                worksheet[spreadsheet_cells['intended_brachy_level']] = 'Level 2'

                for competency_start,cell in spreadsheet_cells['competencies'].items():
                    points = self.tracking_df[(self.tracking_df['cat'] == competency_start)]['score'].mean()
                    worksheet[cell] = points

                workbook.save(filepath)

    def update_overview_plot(self):
        if self.data is not None:
            self.ui.MplWidgetOverview.reset_axis()

            relative_plot = self.ui.checkBoxOverviewPlotRelative.isChecked()

            complete = []
            uploaded = []
            unattempted = []
            modules = ('1', '2', '3', '4', '5', '6', '7', '8')
            for module in modules:
                total_available_points = competency_reference_data[module]['total_points']
                uploaded_points = self.tracking_df[(self.tracking_df['name'].str.startswith(module))
                        & (self.tracking_df['submission_status'] != 'No attempt')]['max_uploaded_score'].sum()
                graded_points = self.tracking_df[(self.tracking_df['name'].str.startswith(module)) & (
                            self.tracking_df['grading_status'] == 'Graded')]['weighted_score'].sum()
                if relative_plot:
                    uploaded_points = uploaded_points / total_available_points * 100
                    graded_points = graded_points / total_available_points * 100
                    total_available_points = 100
                complete.append(graded_points)
                uploaded.append(uploaded_points - graded_points)
                unattempted.append(total_available_points - uploaded_points)
            self.ui.MplWidgetOverview.canvas.ax.bar(modules, complete,
                                                    color=list(
                                                        competency_reference_data[mod]['complete_colour'] for mod in
                                                        modules))
            self.ui.MplWidgetOverview.canvas.ax.bar(modules, uploaded, bottom=complete,
                                                    color=list(
                                                        competency_reference_data[mod]['incomplete_colour'] for mod in
                                                        modules), hatch='//',
                                                    edgecolor=list(
                                                        competency_reference_data[mod]['complete_colour'] for mod in
                                                        modules))
            self.ui.MplWidgetOverview.canvas.ax.bar(modules, unattempted,
                                                    bottom=[sum(x) for x in zip(complete, uploaded)],
                                                    color=list(
                                                        competency_reference_data[mod]['incomplete_colour'] for mod in
                                                        modules))

            self.ui.MplWidgetOverview.canvas.ax.set_xlabel('Module')
            self.ui.MplWidgetOverview.canvas.ax.set_ylabel(
                'Percentage complete' if relative_plot else 'Points signed off')

            self.ui.MplWidgetOverview.canvas.flush_events()
            self.ui.MplWidgetOverview.canvas.draw()


class ProxyLoginDialog(QDialog):
    def __init__(self, parent=None):
        super(ProxyLoginDialog, self).__init__(parent)
        self.setWindowTitle('Proxy login details required')
        self.label = QLabel(
            "Please enter your proxy username and password (this probably isn't your login details for COMET, more likely this is your institution login details (e.g. Peter Mac, Alfred, Austin etc.)")
        self.lineEditUsername = QLineEdit(self)
        self.lineEditPassword = QLineEdit(self)
        self.lineEditPassword.setEchoMode(QLineEdit.Password)
        self.pushButtonLogin = QPushButton('Login', self)
        self.pushButtonLogin.clicked.connect(self.accepting)
        self.pushButtonCancel = QPushButton('Cancel', self)
        self.pushButtonCancel.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.lineEditUsername)
        layout.addWidget(self.lineEditPassword)
        layout.addWidget(self.pushButtonLogin)
        layout.addWidget(self.pushButtonCancel)

        self.username = None
        self.password = None

    def accepting(self):
        self.username = self.lineEditUsername.text()
        self.password = self.lineEditPassword.text()

        self.accept()


class UpdateNoteDialog(QDialog):
    def __init__(self, parent=None, current_note=None):
        super(UpdateNoteDialog, self).__init__(parent)
        self.setWindowTitle('Update note')
        self.textEditNote = QTextEdit(self)
        if current_note is not None:
            self.textEditNote.setText(current_note)
        self.pushButtonAccept = QPushButton('OK', self)
        self.pushButtonAccept.clicked.connect(self.accepting)
        self.pushButtonCancel = QPushButton('Cancel', self)
        self.pushButtonCancel.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.textEditNote)
        layout.addWidget(self.pushButtonAccept)
        layout.addWidget(self.pushButtonCancel)

        self.note = None

    def accepting(self):
        self.note = self.textEditNote.toPlainText()

        self.accept()

class LoadDataDialog(QDialog):
    def __init__(self, parent=None, registrar_list: dict = None):
        super(LoadDataDialog, self).__init__(parent)
        self.setWindowTitle('Load data')
        self.labelExplanation = QLabel('Please choose a registrar to load their data')
        self.comboBoxRegistrars = QComboBox(self)
        for registrar_name, filepath in registrar_list.items():
            self.comboBoxRegistrars.addItem(registrar_name,filepath)
        self.pushButtonAccept = QPushButton('OK', self)
        self.pushButtonAccept.clicked.connect(self.accepting)
        self.pushButtonCancel = QPushButton('Cancel', self)
        self.pushButtonCancel.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.labelExplanation)
        layout.addWidget(self.comboBoxRegistrars)
        layout.addWidget(self.pushButtonAccept)
        layout.addWidget(self.pushButtonCancel)

        self.load_filepath = None

    def accepting(self):
        self.load_filepath = self.comboBoxRegistrars.currentData()

        self.accept()

class InitialDownloadDialog(QDialog):
    def __init__(self, parent=None, registrar_list: dict = None):
        super(InitialDownloadDialog, self).__init__(parent)
        self.setWindowTitle('Download data')
        self.labelExplanation = QLabel('Please login with your COMET details')
        self.lineEditUsername = QLineEdit()
        self.lineEditPassword = QLineEdit()
        self.lineEditPassword.setEchoMode(QLineEdit.Password)

        self.pushButtonAccept = QPushButton('OK', self)
        self.pushButtonAccept.clicked.connect(self.accepting)
        self.pushButtonCancel = QPushButton('Cancel', self)
        self.pushButtonCancel.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.labelExplanation)
        layout.addWidget(self.lineEditUsername)
        layout.addWidget(self.lineEditPassword)
        layout.addWidget(self.pushButtonAccept)
        layout.addWidget(self.pushButtonCancel)

        self.session = None

    def accepting(self):
        if self.lineEditUsername.text() == '' or self.lineEditPassword.text() == '':
            msg_box = QMessageBox()
            msg_box.setWindowTitle('Error')
            msg_box.setText("Neither username or password can be blank")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            return None

        self.session = make_session(username=self.lineEditUsername.text(),
                                    password=self.lineEditPassword.text())
        if self.session is None:
            return
        else:
            self.accept()

class MultiColumnProxyModel(QSortFilterProxyModel):
    """
    A subclass of QSortFilterProxyModel that does multi column filtering
    """

    def __init__(self):
        super(MultiColumnProxyModel, self).__init__()
        self._submission_status_filter = ''
        self._grading_status_filter = ''

    def set_submission_status_filter(self, submission_status_filter):
        self._submission_status_filter = submission_status_filter
        self.invalidateFilter()

    def set_grading_status_filter(self, grading_status_filter):
        self._grading_status_filter = grading_status_filter
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        submission_status = model.item(source_row, 3).text()
        grading_status = model.item(source_row, 5).text()

        return (self._grading_status_filter.lower() == grading_status.lower()
                or self._grading_status_filter.lower() == 'all') \
               and (self._submission_status_filter.lower() == submission_status.lower()
                    or self._submission_status_filter.lower() == 'all')

def make_session(username:str = None,password:str=None):
    # Sets up a requests session object to store all the cookies for authentication
    # Note that pypac is used here to try and autodetect proxy settings, the session object is essentially
    # a requests session
    s = pypac.PACSession()

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://www.acpsem.org.au',
        'Connection': 'keep-alive',
        'Referer': 'https://www.acpsem.org.au/Home',
        'Upgrade-Insecure-Requests': '1',
    }

    login_url = 'https://cometlms.medcast.com.au/auth/association_online/force_login.php'
    login_credentials = f'login={username}&password={password}'

    try:
        response = s.post(
            'https://www.acpsem.org.au/app/ws2/objects/sset-all.r?Mode=InLine&Action=GotoPage%7C35&TenID=ACPSEM',
            headers=headers, data=login_credentials, allow_redirects=False)

    except requests.exceptions.ProxyError as e:
        if e.args[0].reason.args[1].args[0] == 'Tunnel connection failed: 407 Proxy Authentication Required':
            loginDialog = ProxyLoginDialog()
            if loginDialog.exec() == QDialog.Accepted:
                s.proxy_auth = HTTPProxyAuth(loginDialog.username, loginDialog.password)
                s.get(login_url)
            else:
                msg_box = QMessageBox()
                msg_box.setWindowTitle('Error')
                msg_box.setText(f"Proxy error : {e}")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.exec()
                return None
        else:
            msg_box = QMessageBox()
            msg_box.setWindowTitle('Error')
            msg_box.setText(f"Proxy error : {e}")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            return None
    except requests.exceptions.ConnectionError as e:
        msg_box = QMessageBox()
        msg_box.setWindowTitle('Error')
        msg_box.setText(
            f"Connection error : {e}. This probably means either the website is down, or you have no internet connection. Ensure you can load both the ACPSEM website and COMET in a web browser and then try again.")
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.exec()
        return None

    try:
        regex = r'key=(.*?)&'
        key = re.findall(regex, response.headers['Location'])
        new_url = f'https://cometlms.medcast.com.au//auth//userkey//login.php?key={key}&wantsurl=https://www.acpsem.org.au/ccms.r?PageId=35&tenid=ACPSEM'
        resp = s.get(new_url)
        if resp.status_code != 200 or resp.url != 'https://www.acpsem.org.au/ccms.r?PageId=35':
            msg_box = QMessageBox()
            msg_box.setWindowTitle('Error')
            msg_box.setText("There was an error logging in to COMET. Are you sure you have the right username set?")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            return None
    except:
        msg_box = QMessageBox()
        msg_box.setWindowTitle('Error')
        msg_box.setText("There was an error connecting to COMET. Are you sure you have an internet connection?")
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.exec()
        return None
    return s


# Main application loop
if __name__ == '__main__':
    app = QApplication(sys.argv)
    GUI = MainWindow()
    sys.exit(app.exec())
