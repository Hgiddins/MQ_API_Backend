import requests
import time

flask_endpoint = "https://127.0.0.1:5000/"

# #
base_url = "https://13.87.80.195:9444"
username = "admin"
password = "passw0rd"


class MQSystemReport:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.post_client_config(url=base_url, qmgr=None, username=username, apikey=password)

    def post_client_config(self, url, qmgr, username, apikey):
        client_config = {
            "url": url,
            "qmgr": qmgr,
            "username": username,
            "apikey": apikey
        }
        self.request_json("clientconfig", method="POST", data=client_config)

    def request_json(self, url, method="GET", data=None):
        try:
            if method == "GET":
                response = requests.get(flask_endpoint + url,verify=False)
            elif method == "POST":
                response = requests.post(flask_endpoint + url, json=data,verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Failed to fetch data from {url}. Error: {e}")
            return None
        except ValueError:
            print(f"Invalid JSON response from {url}")
            return None

    def fetch_all_queue_managers(self):
        try:
            response = requests.get(flask_endpoint + "getallqueuemanagers",verify=False)  # The endpoint to fetch all queue managers
            response.raise_for_status()
            return response.json().get('All_Queue_Managers', [])
        except requests.RequestException as e:
            print(f"Failed to fetch queue managers. Error: {e}")
            return []

    def generate_reports(self):
        queue_managers = self.fetch_all_queue_managers()
        for qmgr in queue_managers:
            qmgr_name = qmgr.get('qmgr_name')
            print(f"\nGenerating report for queue manager: {qmgr_name}")
            qmgr_report = QMgrSystemReport(qmgr_name, self.base_url, self.username, self.password)
            measure_execution_time(qmgr_report.generate_report)


class QMgrSystemReport:
    def __init__(self, qmanager_name, base_url, username, password):
        self.qmanager_name = qmanager_name
        self.queues = []
        self.applications = []
        self.channels = []
        self.dependency_graph = {}
        self.post_client_config(base_url, qmanager_name, username, password)

    def post_client_config(self, url, qmgr, username, apikey):
        client_config = {
            "url": url,
            "qmgr": qmgr,
            "username": username,
            "apikey": apikey
        }
        self.request_json("clientconfig", method="POST", data=client_config)

    def request_json(self, url, method="GET", data=None):
        try:
            if method == "GET":
                response = requests.get(flask_endpoint + url,verify=False)
            elif method == "POST":
                response = requests.post(flask_endpoint + url, json=data,verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Failed to fetch data from {url}. Error: {e}")
            return None
        except ValueError:
            print(f"Invalid JSON response from {url}")
            return None

    def get_all_queues(self):
        response = self.request_json("getallqueues")
        if response:
            self.queues = response.get('All_Queues', [])
            print('Queues', self.queues)

    def get_all_applications(self):
        response = self.request_json("getallapplications")
        if response:
            self.applications = response.get('All_Applications', [])
            print('Applications', self.applications)

    def get_all_channels(self):
        response = self.request_json("getallchannels")
        if response:
            self.channels = response.get('All_Channels', [])
            print('Channels', self.channels)

    def get_dependency_graph(self):
        response = self.request_json("getdependencygraph")
        if response:
            self.dependency_graph = response.get('Dependency Graph', {})
            print('Dependency Graph', self.dependency_graph)

    def generate_report(self):
        self.get_all_queues()
        self.get_all_applications()
        self.get_all_channels()
        self.get_dependency_graph()

def measure_execution_time(func):
    import time
    start_time = time.time()
    func()
    end_time = time.time()
    execution_time = end_time - start_time
    print("Execution time: {:.2f} seconds".format(execution_time))


report_service = MQSystemReport(base_url, username, password)
report_service.generate_reports()