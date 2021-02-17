# PyQt is GPL v3 licenced
from PyQt5 import QtWidgets
from collections import defaultdict
from PyQt5.QtWidgets import QMessageBox, QProgressBar, QLabel, QPushButton, QSpacerItem
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from bs4 import BeautifulSoup
# Python standard library is PSF licenced
import time
import requests
from urllib import parse
from datetime import datetime


class GetDataFromCometThread(QThread):
    """
    This class is a QThread derived thread for getting all the required data off COMET and parsing it.
    There is a lot of HTML parsing done here to find the required data in the pages
    """

    def __init__(self, session: requests.Session, delay_between_requests=10):
        super(GetDataFromCometThread, self).__init__()
        self.session = session
        self.delay_between_requests = delay_between_requests

    def run(self):
        try:
            # As far as I can tell, the IDs for the 8 modules
            status_ids = ['325', '326', '327', '332', '333', '328', '330', '329']

            comp_data = {'competencies': [], 'profile_data': {},
                         'points': {'modules': defaultdict(dict), 'summary': defaultdict(dict)}}

            self.items_to_process.emit(len(status_ids) + 2)  # The ids + overview + status
            self.current_item.emit(1)
            self.new_step.emit('Getting generic data (Step 1 of 2)')

            overview_page = 'https://cometlms.medcast.com.au/totara/dashboard/index.php'

            resp = self.try_and_get(overview_page)
            soup = BeautifulSoup(resp.text, 'html.parser')
            tag = soup.find(lambda tag: tag.name == "a" and "Profile" in tag.text)
            profile_url = tag['href']
            user_id = parse.parse_qs(parse.urlparse(profile_url).query)['id'][0]

            comp_data['profile_data']['user_id'] = user_id

            time.sleep(self.delay_between_requests)
            self.current_item.emit(2)
            resp = self.try_and_get(profile_url)

            soup = BeautifulSoup(resp.text, 'html.parser')

            name = soup.find("div", class_="page-header-headings").text
            start_date = datetime.strptime(soup.find('dt', text='Program Start').parent.find('dd').text, "%d %B %Y")
            end_date = datetime.strptime(soup.find('dt', text='Expected Program End Date').parent.find('dd').text,
                                         "%d %B %Y")
            program_length = round((end_date - start_date).days / 365)

            comp_data['profile_data']['name'] = name
            comp_data['profile_data']['start_date'] = start_date
            comp_data['profile_data']['program_length'] = program_length

            time.sleep(self.delay_between_requests)

            for index, id in enumerate(status_ids):
                url = f'https://cometlms.medcast.com.au/grade/report/user/index.php?id={id}&userid={user_id}'
                resp = self.try_and_get(url)

                soup = BeautifulSoup(resp.text, 'html.parser')

                table = soup.find_all("table")[0].find_all('tbody')[0]

                comp_total = 0
                for line in table.find_all('tr'):
                    line_txt: str = line.text.replace('<span class="sr-only">Assignment</span>', '').strip()
                    if line_txt.startswith('Assignment'):
                        url = line.find_all('a')[0]['href']
                        line_txt = line_txt.replace('Assignment', 'Assignment ', 1)
                        data = line_txt.split('Assignment')[1].split('\n')
                        comp = data[0].strip()
                        score = 0 if data[1] == '-' else float(data[1])
                        if len(data) > 2:
                            feedback = data[2]
                        else:
                            feedback = 'N/A'

                        comp_data['competencies'].append(
                            {'name': comp, 'score': score, 'feedback': feedback, 'url': url})
                    else:

                        if line_txt.startswith('Mean of grades'):
                            line_txt = line_txt.replace('Mean of grades', '')
                            data = line_txt.split('\n')
                            module = data[0].split('.')[0]
                            category = '.'.join(data[0].split('.')[0:2]).replace(' total', '')
                            score = 0 if data[1] == '-' else float(data[1])
                            comp_data['points']['modules'][module][category] = score
                        elif line_txt.startswith('Weighted mean of grades'):
                            line_txt = line_txt.replace('Weighted mean of grades', '').replace(
                                '. Include empty grades.', '')
                            data = line_txt.split('\n')
                            category = data[0].replace('Competency ', '')
                            module = category.split('.')[0]
                            score = 0 if data[1] == '-' else float(data[1])
                            comp_data['points']['summary'][module][category] = score
                        elif line_txt.startswith('NaturalCourse'):
                            data = line_txt.split('\n')
                            score = 0 if data[1] == '-' else float(data[1])
                            comp_total += score

                self.current_item.emit(index + 3)

                # We don't want to sleep if we are done
                if index + 1 != len(status_ids):
                    time.sleep(self.delay_between_requests)

            self.items_to_process.emit(len(comp_data['competencies']))
            self.current_item.emit(0)
            self.new_step.emit('Getting specific competency data (Step 2 of 2)')

            for index, competency in enumerate(comp_data['competencies']):
                specific_comp_page = competency['url']
                response = self.try_and_get(specific_comp_page)

                soup = BeautifulSoup(response.text, 'html.parser')

                # These competencies  text rather than a table for the description, need to manually change which index we use
                try:
                    if competency['name'].startswith('6'):
                        table = soup.find_all("table")[0].find_all('tbody')[0]
                    else:
                        table = soup.find_all("table")[1].find_all('tbody')[0]

                    lines = table.find_all('tr')
                    if 'Attempt number' in str(lines[0]):
                        line_offset = 1
                    else:
                        line_offset = 0
                    submission_status = lines[0 + line_offset].text.strip().split('\n')[1]
                    grading_status = lines[1 + line_offset].text.strip().split('\n')[1]
                    time_str = lines[2 + line_offset].text.strip().split('\n')[1]
                    if time_str == '-':
                        last_modify_date = None
                    else:
                        last_modify_date = datetime.strptime(time_str, '%A, %d %B %Y, %I:%M %p')
                    competency['submission_status'] = submission_status
                    competency['grading_status'] = grading_status
                    competency['last_modify_date'] = last_modify_date
                except:
                    competency['submission_status'] = 'Invalid'
                    competency['grading_status'] = 'Invalid'
                    competency['last_modify_date'] = None

                try:
                    if competency['name'].startswith('6'):
                        table = soup.find_all("table")[1].find_all('tbody')[0]
                    else:
                        table = soup.find_all("table")[2].find_all('tbody')[0]

                    lines = table.find_all('tr')
                    # grade = float(lines[0].text.strip().split('\n')[1].split('/')[0].strip())
                    time_str = lines[1].text.strip().split('\n')[1]
                    if time_str == '-':
                        grade_date = None
                    else:
                        grade_date = datetime.strptime(time_str, '%A, %d %B %Y, %I:%M %p')
                    assessor = lines[2].text.strip().split('\n')[1]
                    competency['grade_date'] = grade_date

                    # Catch competencies signed off without evidence
                    if grade_date is not None and competency['last_modify_date'] is not None and grade_date < \
                            competency['last_modify_date']:
                        competency['last_modify_date'] = grade_date
                    if grade_date is not None and competency['last_modify_date'] is None:
                        competency['last_modify_date'] = grade_date
                        competency['submission_status'] = 'Submitted'

                    competency['assessor'] = assessor
                except IndexError:
                    competency['grade_date'] = None
                    competency['assessor'] = None

                if index + 1 != len(comp_data['competencies']):
                    time.sleep(self.delay_between_requests)

                self.current_item.emit(index + 1)

            self.finished.emit(comp_data)
        except Exception as e:
            self.finished.emit(None)

    def try_and_get(self, url, retry_delay=30):
        current_attempt_number = 0
        self.current_url.emit(url)
        while True:
            try:
                result = self.session.get(url)
                if result.status_code == 200:
                    self.new_status.emit('')
                    return result
                else:
                    raise Exception(f'code {result.status_code}, reason {result.reason}')
            except Exception as e:
                new_delay = min(retry_delay + current_attempt_number * 15, 300)
                self.new_status.emit(
                    f'There was an issue with the request, waiting {new_delay} seconds and retrying. Error {str(e)}')
                time.sleep(new_delay)
                current_attempt_number += 1

    items_to_process = pyqtSignal(int, name='items_to_process')
    new_status = pyqtSignal(str)
    new_step = pyqtSignal(str)
    current_item = pyqtSignal(int, name='current_item')
    finished = pyqtSignal(object, name='finished')
    current_url = pyqtSignal(str, name='current_url')


class GetDataFromCometWindow(QtWidgets.QDialog):
    def __init__(self, session: requests.Session, parent=None):
        super(GetDataFromCometWindow, self).__init__(parent)
        self.progressBar = QProgressBar()
        self.progressBar.setFormat(' %v/%m (%p%)')
        self.labelStep = QLabel('')
        self.labelStatus = QLabel('')
        self.labelStatus.setWordWrap(True)
        self.labelStatus.setMinimumHeight(200)
        self.labelUrl = QLabel('')
        self.labelUrl.setOpenExternalLinks(True)
        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.labelStep, alignment=Qt.AlignVCenter)
        self.layout.addWidget(self.progressBar, alignment=Qt.AlignVCenter)
        self.layout.addWidget(self.labelStatus, alignment=Qt.AlignVCenter)
        self.layout.addWidget(self.labelUrl, alignment=Qt.AlignVCenter)
        self.layout.addWidget(self.cancel_button, alignment=Qt.AlignVCenter)
        self.setLayout(self.layout)
        self.setWindowTitle('Getting data from Comet')
        #self.setMinimumHeight(500)
        self.competency_data = None

        self.resize(450, 150)

        self.setModal(True)
        self.show()

        self.workerThread = GetDataFromCometThread(session)
        self.workerThread.items_to_process.connect(lambda num_of_items: self.progressBar.setMaximum(num_of_items))
        self.workerThread.new_step.connect(lambda new_step: self.labelStep.setText(new_step))
        self.workerThread.current_item.connect(lambda item: self.progressBar.setValue(item))
        self.workerThread.new_status.connect(lambda new_status: self.labelStatus.setText(new_status))
        self.workerThread.current_url.connect(
            lambda new_url: self.labelUrl.setText(f'Getting data from <a href="{new_url}">{new_url}</a>'))
        self.workerThread.start()
        self.workerThread.finished.connect(self.handle_finished)

    def handle_finished(self, competency_data):
        if competency_data is None:
            msg_box = QMessageBox()
            msg_box.setWindowTitle('Error')
            msg_box.setText("There was an error getting data from Comet. Try again in an hour, or report this as a bug")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec()
            return
        self.competency_data = competency_data
        self.accept()
