from flask import Flask, request
from flask_restful import Api, Resource
from MQ_REST_API.DependencyGraph import DependencyGraph
from flask_caching import Cache
import MQ_REST_API.MQ
from ChatBot.ChatBot import boot_chatbot, get_error_message_chatbot_response, get_general_chatbot_response
import urllib3
from ErrorLogging import ThreadsafeErrorList, QueueThresholdsConfig


# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# setting up server
app = Flask(__name__)
api = Api(app)

# cache for constantly updated MQ objects
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Insantiating threadsafe queue threshold configuration
queueThresholds = QueueThresholdsConfig.QueueThresholdManager()

# Logging of errors - threadsafe
errorList = ThreadsafeErrorList.ThreadSafeErrorList()

# global client, must first be posted to for MQ_REST_API to work
client = None


# Chat Bot connection and instantiation
retrieval_chain, conversation_chain = boot_chatbot()



class ClientConfig(Resource):

    def post(self):
        global qmgr
        data = request.get_json()

        # Update global client details
        global client

        # Ensure all necessary fields are in the posted data
        if not all(field in data for field in ["qmgr", "url", "username", "apikey"]):
            return {"message": "Missing required fields. Ensure 'url', 'username', and 'apikey' are provided."}, 400

        client = MQ_REST_API.MQ.Client(url=data["url"], qmgr=data["qmgr"], username=data["username"],
                                       apikey=data["apikey"])

        cache.set('qmgr', data["qmgr"], timeout=10)

        try:
            qmgr_state = client.get_qmgr().state

            if qmgr_state == "running":
                return {"message": "Login successful."}, 200
            else:
                return {"message": "Login failed, queue manager is not running."}, 400

        except Exception as e:
            # catch the exception related to qmgr not existing.
            return {"message": f"Login failed, no queue manager named {data['qmgr']}."}, 400


class ErrorListResource(Resource):

    # Step 2: Implement the `get` method for this resource to fetch all errors
    def get(self):
        errors = errorList.get_errors()

        # Step 3: After fetching, clear the errors from the error list
        errorList.clear_errors()

        return {"errors": errors}


class QueueThresholdConfig(Resource):
    def post(self):
        data = request.get_json()

        # Ensure the data is valid (contains queue names and their thresholds)
        if not all(isinstance(data[key], (int, float)) for key in data):
            return {
                "message": "Invalid threshold data. Ensure you provide a valid threshold (float) for each queue name."}, 400

        queueThresholds.update(data)  # Update the thresholds using the manager

        return {"message": "Thresholds updated successfully."}, 200


class ChatBotQuery(Resource):

    def post(self):
        data = request.get_json()

        # Check if required fields are present
        if not all(field in data for field in ["question", "objects", "indicator"]):
            return {"message": "Missing required fields. Ensure 'question', 'objects' and 'indicator' are provided."}, 400

        # Store the query details in the cache
        cache.set('query', [data["question"], data["objects"], data["indicator"]])

        return {"message": "Query stored successfully."}, 200

    def get(self):
        query_details = cache.get('query')
        if not query_details:
            return {"message": "No query found in cache."}, 404

        question, objects, indicator = query_details

        if indicator == "systemMessage":
            response = get_error_message_chatbot_response(retrieval_chain, conversation_chain, question, objects)
            cache.delete('query')  # Clear the cache after processing the query
            return response

        elif indicator == "userMessage":
            response = get_general_chatbot_response(retrieval_chain, conversation_chain, question)
            cache.delete('query')  # Clear the cache after processing the query
            return response

        else:
            return {"message": "Invalid indicator value."}, 400


class GetAllQueueManagers(Resource):
    def get(self):
        qmgrs = cache.get('all_qmgrs')

        if qmgrs is None:
            qmgrs = client.get_all_queue_managers()
            cache.set('all_qmgrs', qmgrs, timeout=10)

        qmgrs_as_dicts = [qmgr.to_dict() for qmgr in qmgrs]
        return {'All_Queue_Managers': qmgrs_as_dicts}


class GetAllQueues(Resource):
    def get(self):
        queues = cache.get('all_queues')

        if queues is None:
            queues = client.get_all_queues()
            cache.set('all_queues', queues, timeout=10)

        queues_as_dicts = []

        for queue in queues:
            # Checking for custom queue threshold using the manager
            if queueThresholds.contains(queue.queue_name):
                queue.threshold_limit = queueThresholds.get(queue.queue_name)
            error_msg = queue.thresholdWarning()  # Call the thresholdWarning method of the Queue object
            if error_msg:
                errorList.add_error(error_msg)  # Directly add the error message to the global errorLog
            queues_as_dicts.append(queue.to_dict())

        # No need to interact with errorCache. Just return the list of queues.
        return {'All_Queues': queues_as_dicts}



class GetAllApplications(Resource):
    def get(self):
        applications = cache.get('all_applications')
        if applications is None:
            applications = client.get_all_applications()
            cache.set('all_applications', applications, timeout=10)

        apps_as_dicts = [app.to_dict() for app in applications]
        return {'All_Applications': apps_as_dicts}


class GetAllChannels(Resource):
    def get(self):
        channels = cache.get('all_channels')
        if channels is None:
            channels = client.get_all_channels()
            cache.set('all_channels', channels, timeout=10)

        chs_as_dicts = [ch.to_dict() if hasattr(ch, 'to_dict') else 'Not a channel instance' for ch in channels]
        return {'All_Channels': chs_as_dicts}


class GetDependencyGraph(Resource):
    def get(self):
        qmgr = cache.get('qmgr')
        channels = cache.get('all_channels')
        if channels is None:
            channels = client.get_all_channels()
            cache.set('all_channels', channels, timeout=10)

        applications = cache.get('all_applications')
        if applications is None:
            applications = client.get_all_applications()
            cache.set('all_applications', applications, timeout=10)

        queues = cache.get('all_queues')
        if queues is None:
            queues = client.get_all_queues()
            cache.set('all_queues', queues, timeout=10)

        graph = DependencyGraph()
        graph.create_dependency_graph(queues, channels, applications, qmgr)
        graph_as_dicts = graph.to_dict()
        return {'Dependency Graph': graph_as_dicts}


api.add_resource(ClientConfig, '/clientconfig')
api.add_resource(GetAllQueueManagers, '/getallqueuemanagers')
api.add_resource(GetAllQueues, '/getallqueues')
api.add_resource(GetAllApplications, '/getallapplications')
api.add_resource(GetAllChannels, '/getallchannels')
api.add_resource(GetDependencyGraph, '/getdependencygraph')
api.add_resource(ChatBotQuery, '/chatbotquery')
api.add_resource(QueueThresholdConfig, '/queuethresholds')
api.add_resource(ErrorListResource, '/geterrors')

if __name__ == "__main__":
    # app.run(debug=True)
    app.run(debug=True, ssl_context=("cert.pem", "key.pem"), threaded = True)