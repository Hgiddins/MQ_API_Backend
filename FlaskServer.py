import atexit
import signal
import json
import os
import requests
import sys
import threading
from flask import Flask, request, jsonify
from flask_restful import Api, Resource
from MQ_REST_API.DependencyGraph import DependencyGraph
from flask_caching import Cache
import MQ_REST_API.MQ
from ChatBot.MainChatBot import boot_chatbot, get_issue_message_chatbot_response, get_general_chatbot_response, ThreadSafeChatbot
import urllib3
from IssueLogging import ThreadsafeIssueList, QueueThresholdsConfig
from JavaApp.BootJava import start_spring_app_with_properties


#############################
#      INITIALISATION       #
#############################

# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# setting up server
app = Flask(__name__)
api = Api(app)

# cache for constantly updated MQ objects
cache = Cache(app, config={'CACHE_TYPE': 'simple'})


resolved_issues = Cache(app, config={
    'CACHE_TYPE': 'simple'
})


# Insantiating threadsafe queue threshold configuration
queueThresholdManager = QueueThresholdsConfig.QueueThresholdManager()

# Logging of issues - threadsafe
issue_list = ThreadsafeIssueList.ThreadSafeIssueList()

# global client, must first be posted to for MQ_REST_API to work
client = None

# Chat Bot connection and instantiation
# retrieval_chain, conversation_chain = None, None
chatbot = ThreadSafeChatbot()

# Java Application Subprocess and Event
process = None
java_app_start_event = threading.Event()
java_login_event = threading.Event()
java_login_message = None
java_config = None


#############################
#      Java Utilities       #
#############################
def terminate_spring_app():
    if process:
        process.terminate()
        print("Java process terminated")
    else:
        print("No process to terminate")

def wait_and_terminate():
    java_app_start_event.wait()  # Wait until the Java app is started
    terminate_spring_app()

if not os.environ.get('WERKZEUG_RUN_MAIN'):
    atexit.register(wait_and_terminate)


def signal_handler(signum, frame):
    terminate_spring_app()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

############################################################################################################
#                                           MQ REST API LOGIN                                              #
############################################################################################################

class ClientConfig(Resource):

    def post(self):
        global qmgr, process, client, java_login_message
        data = request.get_json()

        # clear caches
        resolved_issues.clear()
        cache.clear()

        #shutoff maven app if it is running
        terminate_spring_app()

        # Ensure all necessary fields are in the posted data
        required_fields = ["qmgr", "address", "username", "password", "admin_port", "admin_channel", "app_port"]

        # Check if all fields are present and they are not None or empty string
        if not all(field in data and data[field] not in [None, ""] for field in required_fields):
            return {
                "message": "Missing or invalid required fields. Ensure all fields provided and not empty."}
        try:

            address = data["address"]
            admin_port = data["admin_port"]
            admin_channel = data["admin_channel"]
            app_port = data["app_port"]
            qmgr = data["qmgr"]
            username = data["username"]
            password = data["password"]

            url = "https://" + address + ":" + admin_port

            client = MQ_REST_API.MQ.Client(url=url, qmgr=qmgr, username=username, password=password)
        except Exception as e:
            # Check if the exception message indicates a timeout
            if "timed out" in str(e):
                return {"message": "Connection timeout; check Address and Admin Port"}
            else:
                return {"message": f"Login failed, incorrect login details. Check Username and Password "}


        cache.set('qmgr', data["qmgr"])

        try:
            print("Qmgr is " + client.get_qmgr().state)
            qmgr_state = client.get_qmgr().state

            if qmgr_state == "running":
                # SUCCESFULL LOG IN
                print("Login successful")

                # Boot a new chatbot with a fresh memory
                print("Booting new chatbot")
                chatbot.boot()

                # Boot Java Spring application
                print('Booting Java application')
                process = start_spring_app_with_properties(
                    queue_manager=qmgr,
                    channel= admin_channel,
                    conn_name=address + "(" + app_port + ")",
                    user=username,
                    password=password,
                    listener_auto_startup="false",
                    event = java_app_start_event
                )
                # return {"message": "Login successful."}
                # Wait for the Java application to set the login message.
                print('waiting on java login event')
                java_login_event.wait(timeout=30)  # Here, timeout is 60 seconds.
                print('got past login event')

                response_message = java_login_message  # Store the message in a variable

                java_login_message = None  # Reset the global variable for future use

                java_login_event.clear()  # Reset the event for future use

                if response_message == "Login successful":
                    return {"message": "Login successful."}
                else:
                    terminate_spring_app()
                    return {"message": 'Spring login failed. Check channel and app port. System Message: '+ response_message}
            else:
                return {"message": "Login failed, queue manager is not running."}

        except Exception as e:
            print(e)
            # catch the exception related to qmgr not existing.
            return {"message": f"Login failed, no queue manager named {data['qmgr']}."}


############################################################################################################
#                                          Java Login Feedback                                             #
############################################################################################################

class JavaLoginFeedback(Resource):

    def post(self):
        global java_login_message

        data = request.get_json()

        # Extract the message from the posted data
        message = data.get('message')

        if not message:
            return {"error": "No message provided."}

        java_login_message = message
        print(message)

        # trigger the java login event
        java_login_event.set()


        if message == "Login successful":
            print("Java application reported a successful login.")
            return {"message": "Received successfully."}
        else:
            print(f"Java application reported an issue: {message}")
            return {"message": "Received successfully."}


############################################################################################################
#                                             Logout Handling                                              #
############################################################################################################

class Logout(Resource):

    def post(self):
        global client, login_flag, java_login_message

        # Wipe data that might be sensitive or user-specific
        client = None  # Reset the MQ_REST_API client object
        cache.clear()  # Clear the cache
        issue_list.clear_issues()  # Clear the list of issues
        resolved_issues.clear()
        java_login_message = None
        wait_and_terminate() #terminate java app

        return {"message": "Logged out successfully."}


############################################################################################################
#                                           Issue Handling                                                 #
############################################################################################################

class IssueListResource(Resource):

    def get(self):
        issues = issue_list.get_issues()

        # After fetching, clear the issues from the issue list
        issue_list.clear_issues()

        # Filter out issues that are in the 'resolved_issues' cache.
        unresolved_issues = []
        for issue in issues:
            cache_key = (issue['mqobjectName'], issue['issueCode'])
            if not resolved_issues.get(cache_key):
                unresolved_issues.append(issue)


        return {"issues": unresolved_issues}


    def post(self):
        issues = request.get_json()

        if not isinstance(issues, list):
            return {"message": "Expecting a list of issues."}

        for data in issues:
            # Check if required fields are present in each issue
            if not all(field in data for field in ["mqobjectType", "mqobjectName"]):
                return {"message": "Missing required fields. Ensure each issue has 'mqobjectType' and 'mqobjectName'."}

            data['object_details'] = 'N/A'

            # Depending on the object type, search in the appropriate cache and add object details to data
            if data['mqobjectType'] == 'application':
                applications = cache.get('all_applications')
                for app in applications:
                    if app.conn == data['mqobjectName']:
                        data['object_details'] = app.to_dict()
                        break
            elif data['mqobjectType'] == 'channel':
                channels = cache.get('all_channels')
                for channel in channels:
                    if channel.channel_name == data['mqobjectName']:
                        data['object_details'] = channel.to_dict()
                        break
            elif data['mqobjectType'] == 'queue':
                queues = cache.get('all_queues')
                for queue in queues:
                    if queue.queue_name == data['mqobjectName']:
                        data['object_details'] = queue.to_dict()
                        break

            # append the issue to the issue list
            issue_list.add_issue(data)

        return {"message": f"{len(issues)} issues added successfully!"}


class QueueThresholdConfig(Resource):
    def get(self):
        global java_config

        with queueThresholdManager._lock:
            thresholds = queueThresholdManager._thresholds.copy()  # Copy to ensure thread-safety while reading

        if java_config == None:
            java_config = requests.get("https://localhost:8080/configurations", verify=False).text
            print('Received config via Java.get/configurations:', java_config)

        if isinstance(java_config, str):
            java_config = json.loads(java_config)

        activity_thresholds = java_config.get('queues', {}).get('queueActivityThresholds', {})

        queue_thresholds = {}
        for queue, depth in thresholds.items():
            queue_thresholds[queue] = {
                "depth": depth,
                "activity": activity_thresholds.get(queue, 200)
            }

        java_config['queues']['queueThresholds'] = queue_thresholds
        if 'queueActivityThresholds' in java_config['queues']:
            del java_config['queues']['queueActivityThresholds']

        return java_config

    def post(self):
        global java_config
        whole_config = request.get_json(force=True)

        if not whole_config:
            return {"message": "No data provided."}

        # Index into the queue depth thresholds and set them equal to data
        data = whole_config.get('queues', {}).get('queueDepthThresholds', {})

        # Delete the queueDepthThresholds in the whole_config
        if 'queues' in whole_config and 'queueDepthThresholds' in whole_config['queues']:
            del whole_config['queues']['queueDepthThresholds']

        java_config = whole_config

        # Check for the validity of the data (as you have already provided)
        if not all(isinstance(data[key], (int, float)) for key in data):
            return {
                "message": "Invalid threshold data. Ensure you provide a valid threshold (float) and queue name."
            }

        if not all(0 <= value <= 100 for value in data.values()):
            return {"message": "Invalid threshold values. All thresholds should be between 0 and 100."}

        queueThresholdManager.update(data)  # Update the thresholds using the manager

        print('posting config to Java')
        response = requests.post("https://127.0.0.1:8080/updateAppConfig", data=json.dumps(java_config),
                                 headers={"Content-Type": "application/json"}, verify=False)
        print('Java says:', response.text)

        return {"message": "Configuration updated successfully."}


class ResolveIssue(Resource):
    def post(self):
        data = request.get_json(force=True)
        mqobject_name = data.get('mqobjectName')
        issue_code = data.get('issueCode')

        if not mqobject_name or not issue_code:
            return {"message": "Both 'mqobjectName' and 'issueCode' are required."}, 200

        # Create a unique key for this combination of mqobjectName and issueCode
        cache_key = (mqobject_name, issue_code)
        resolved_issues.set(cache_key, 'resolved', timeout=60)

        return {"message": "(mqobjectName, issueCode) pair added to resolved issues."}, 200

    def get(self):
        mqobject_name = request.args.get('mqobjectName')
        issue_code = request.args.get('issueCode')

        if not mqobject_name or not issue_code:
            return {"message": "Both 'mqobjectName' and 'issueCode' are required."}, 200

        cache_key = (mqobject_name, issue_code)
        if resolved_issues.get(cache_key):
            return {"status": "resolved", "mqobjectName": mqobject_name, "issueCode": issue_code}, 200
        else:
            return {"status": "unresolved", "mqobjectName": mqobject_name, "issueCode": issue_code}, 200



############################################################################################################
#                                               ChatBot                                                    #
############################################################################################################

class ChatBotQuery(Resource):

    def post(self):

        existing_query = cache.get('query')
        if existing_query:
            return {"message": "Please wait, one question at a time..."}

        data = request.get_json()

        # Check if required fields are present
        if not all(field in data for field in ["question", "indicator"]):
            return {"message": "Missing required fields. Ensure 'question' and 'indicator' are provided."}

        # Store the query details in the cache
        cache.set('query', [data["question"], data["indicator"]])

        return {"message": "Query stored successfully."}

    def get(self):

        query_details = cache.get('query')
        if not query_details:
            return {"message": "No query found in cache."}

        question, indicator = query_details
        response = chatbot.get_response(indicator, question)

        cache.delete('query')  # Clear the cache after processing the query
        return {"message": response}


############################################################################################################
#                                               MQ Objects                                                 #
############################################################################################################

class GetAllQueueManagers(Resource):
    def get(self):
        qmgrs = client.get_all_queue_managers()
        cache.set('all_qmgrs', qmgrs)


        qmgrs_as_dicts = [qmgr.to_dict() for qmgr in qmgrs]
        return {'All_Queue_Managers': qmgrs_as_dicts}


class GetAllQueues(Resource):
    def get(self):
        queues = client.get_all_queues()
        cache.set('all_queues', queues)

        queues_as_dicts = []

        for queue in queues:

            if queue.type_name == 'Local' or queue.type_name == 'Transmission':
                # Checking for custom queue threshold using the manager
                if queueThresholdManager.contains(queue.queue_name):
                    currentQueueThreshold = queueThresholdManager.get(queue.queue_name)
                else:
                    currentQueueThreshold = queueThresholdManager.defaultThreshold
                    queueThresholdManager.update({queue.queue_name: currentQueueThreshold})

                issue_msg = queueThresholdManager.thresholdWarning(queue, currentQueueThreshold)  # Call the thresholdWarning method of the Queue object
                if issue_msg:
                    issue_list.add_issue(issue_msg)  # Directly add the issue message to the global issueLog
            queues_as_dicts.append(queue.to_dict())

        # No need to interact with issueCache. Just return the list of queues.
        return {'All_Queues': queues_as_dicts}


class GetAllApplications(Resource):
    def get(self):
        applications = client.get_all_applications()
        cache.set('all_applications', applications)

        apps_as_dicts = [app.to_dict() for app in applications]
        return {'All_Applications': apps_as_dicts}


class GetAllChannels(Resource):
    def get(self):
        channels = client.get_all_channels()
        cache.set('all_channels', channels)

        chs_as_dicts = [ch.to_dict() if hasattr(ch, 'to_dict') else 'Not a channel instance' for ch in channels]
        return {'All_Channels': chs_as_dicts}


class GetDependencyGraph(Resource):
    def get(self):
        qmgr = cache.get('qmgr')
        channels = cache.get('all_channels')
        if channels is None:
            channels = client.get_all_channels()
            cache.set('all_channels', channels)

        applications = cache.get('all_applications')
        if applications is None:
            applications = client.get_all_applications()
            cache.set('all_applications', applications)

        queues = cache.get('all_queues')
        if queues is None:
            queues = client.get_all_queues()
            cache.set('all_queues', queues)

        graph = DependencyGraph()
        graph.create_dependency_graph(queues, channels, applications, qmgr)
        graph_as_dicts = graph.to_dict()
        return {'Dependency Graph': graph_as_dicts}


############################################################################################################
#                                           ADDING API RESOURCES                                           #
############################################################################################################

api.add_resource(ClientConfig, '/clientconfig')
api.add_resource(GetAllQueueManagers, '/getallqueuemanagers')
api.add_resource(GetAllQueues, '/getallqueues')
api.add_resource(GetAllApplications, '/getallapplications')
api.add_resource(GetAllChannels, '/getallchannels')
api.add_resource(GetDependencyGraph, '/getdependencygraph')
api.add_resource(ChatBotQuery, '/chatbotquery')
api.add_resource(QueueThresholdConfig, '/queuethresholdmanager')
api.add_resource(IssueListResource, '/issues')
api.add_resource(Logout, "/logout")
api.add_resource(ResolveIssue, '/resolve', '/check')
api.add_resource(JavaLoginFeedback, '/javaloginfeedback') # This will map the '/java-login-feedback' endpoint to the JavaLoginFeedback class



############################################################################################################
#                                       Run, Certificate, Threading                                        #
############################################################################################################



if __name__ == "__main__":
    # app.run(debug=True)
    app.run(debug=True, ssl_context=("cert.pem", "key.pem"), threaded = True)