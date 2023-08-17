from flask import Flask, request, jsonify
from flask_restful import Api, Resource
from MQ_REST_API.DependencyGraph import DependencyGraph
from flask_caching import Cache
import MQ_REST_API.MQ
from ChatBot.MainChatBot import boot_chatbot, get_issue_message_chatbot_response, get_general_chatbot_response
import urllib3
from IssueLogging import ThreadsafeIssueList, QueueThresholdsConfig


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

# Insantiating threadsafe queue threshold configuration
queueThresholdManager = QueueThresholdsConfig.QueueThresholdManager()

# Logging of issues - threadsafe
issueList = ThreadsafeIssueList.ThreadSafeIssueList()

# global client, must first be posted to for MQ_REST_API to work
client = None

# Chat Bot connection and instantiation
retrieval_chain, conversation_chain = boot_chatbot()


############################################################################################################
#                                           MQ REST API LOGIN                                              #
############################################################################################################

class ClientConfig(Resource):

    def post(self):
        global qmgr
        data = request.get_json()

        # Update global client details
        global client

        # Ensure all necessary fields are in the posted data
        required_fields = ["qmgr", "url", "username", "password"]

        # Check if all fields are present and they are not None or empty string
        if not all(field in data and data[field] not in [None, ""] for field in required_fields):
            return {
                "message": "Missing or invalid required fields. Ensure Url, Queue Manager, Username, and Password are all provided and not empty."}
        try:
            client = MQ_REST_API.MQ.Client(url=data["url"], qmgr=data["qmgr"], username=data["username"],
                                       password=data["password"])
        except Exception as e:
            # Check if the exception message indicates a timeout
            if "timed out" in str(e):
                return {"message": "Connection timeout; check URL"}
            else:
                return {"message": f"Login failed, incorrect login details. Check Username and Password "}


        cache.set('qmgr', data["qmgr"])

        try:
            qmgr_state = client.get_qmgr().state

            if qmgr_state == "running":
                return {"message": "Login successful."}
            else:
                return {"message": "Login failed, queue manager is not running."}

        except Exception as e:
            # catch the exception related to qmgr not existing.
            return {"message": f"Login failed, no queue manager named {data['qmgr']}."}


############################################################################################################
#                                           Issue Handling                                                 #
############################################################################################################

class IssueListResource(Resource):

    # Step 2: Implement the `get` method for this resource to fetch all issues
    def get(self):
        issues = issueList.get_issues()

        # Step 3: After fetching, clear the issues from the issue list
        issueList.clear_issues()

        return {"issues": issues}


    # TODO This is still in test:
    def post(self):
        issues = request.get_json()

        if not isinstance(issues, list):
            return {"message": "Expecting a list of issues."}, 400

        for data in issues:
            # Check if required fields are present in each issue
            if not all(field in data for field in ["object_type", "object_name"]):
                return {"message": "Missing required fields. Ensure each issue has 'object_type' and 'object_name'."}, 400

            # Depending on the object type, search in the appropriate cache and add object details to data
            if data['object_type'] == 'application':
                applications = cache.get('all_applications')
                for app in applications:
                    if app['conn'] == data['object_name']:
                        data['object_details'] = app.to_dict()
                        break
            elif data['object_type'] == 'channel':
                channels = cache.get('all_channels')
                for channel in channels:
                    if channel['channel_name'] == data['object_name']:
                        data['object_details'] = channel.to_dict()
                        break
            elif data['object_type'] == 'queue':
                queues = cache.get('all_queues')
                for queue in queues:
                    if queue['queue_name'] == data['object_name']:
                        data['object_details'] = queue.to_dict()
                        break

            # append the issue to the issue list
            issueList.add_issue(data)

        return {"message": f"{len(issues)} issues added successfully!"}


class QueueThresholdConfig(Resource):
    def get(self):
        with queueThresholdManager._lock:
            thresholds = queueThresholdManager._thresholds.copy() # Copy to ensure thread-safety while reading
        return jsonify(thresholds)

    def post(self):
        data = request.get_json(force=True)  # This will ensure it doesn't fail even if content-type is not set

        if not data:
            return {"message": "No data provided."}  # Return with bad request status

        if not all(isinstance(data[key], (int, float)) for key in data):
            return {
                "message": "Invalid threshold data. Ensure you provide a valid threshold (float) and queue name."
            }  # Return with bad request status

        queueThresholdManager.update(data)  # Update the thresholds using the manager

        return {"message": "Thresholds updated successfully."}


############################################################################################################
#                                               ChatBot                                                    #
############################################################################################################

class ChatBotQuery(Resource):

    def post(self):
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

        if indicator == "systemMessage":
            response = get_issue_message_chatbot_response(retrieval_chain, conversation_chain, question)
            cache.delete('query')  # Clear the cache after processing the query
            return {"chatbotresponse": response}

        elif indicator == "userMessage":
            response = get_general_chatbot_response(retrieval_chain, conversation_chain, question)
            cache.delete('query')  # Clear the cache after processing the query
            return {"chatbotresponse": response}

        else:
            return {"message": "Invalid indicator value."}


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

            # Checking for custom queue threshold using the manager
            if queueThresholdManager.contains(queue.queue_name):
                currentQueueThreshold = queueThresholdManager.get(queue.queue_name)
            else:
                currentQueueThreshold = queueThresholdManager.defaultThreshold
                queueThresholdManager.update({queue.queue_name: currentQueueThreshold})

            issue_msg = queueThresholdManager.thresholdWarning(queue, currentQueueThreshold)  # Call the thresholdWarning method of the Queue object
            if issue_msg:
                issueList.add_issue(issue_msg)  # Directly add the issue message to the global issueLog
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
api.add_resource(QueueThresholdConfig, '/queueThresholdManager')
api.add_resource(IssueListResource, '/getissues')


############################################################################################################
#                                       Run, Certificate, Threading                                        #
############################################################################################################
if __name__ == "__main__":
    # app.run(debug=True)
    app.run(debug=True, ssl_context=("cert.pem", "key.pem"), threaded = True)