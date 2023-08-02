from flask import Flask, request
from flask_restful import Api, Resource
from DependencyGraph import DependencyGraph
from flask_caching import Cache
import MQ



client = None
qmgr = None
# client = MQ.Client(url="https://13.87.80.195:9444", qmgr='QM2', username="admin", apikey = "passw0rd")


app = Flask(__name__)
api = Api(app)

cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 10})


class ClientConfig(Resource):

    def post(self):
        global qmgr
        data = request.get_json()

        # Update global client details
        global client

        # Ensure all necessary fields are in the posted data
        if not all(field in data for field in ["qmgr", "url", "username", "apikey"]):
            return {"message": "Missing required fields. Ensure 'url', 'username', and 'apikey' are provided."}, 400

        client = MQ.Client(url=data["url"], qmgr=data["qmgr"] if "qmgr" in data else None, username=data["username"], apikey=data["apikey"])

        qmgr = data["qmgr"]

        return {"message": "Client configuration updated successfully."}, 200



class GetAllQueueManagers(Resource):
    def get(self):
        qmgrs = cache.get('all_qmgrs')

        if qmgrs is None:
            qmgrs = client.get_all_queue_managers()
            cache.set('all_qmgrs', qmgrs)

        qmgrs_as_dicts = [qmgr.to_dict() for qmgr in qmgrs]
        return {'All_Queue_Managers': qmgrs_as_dicts}


class GetAllQueues(Resource):
    def get(self):
        queues = cache.get('all_queues')

        if queues is None:
            queues = client.get_all_queues()
            cache.set('all_queues', queues)

        queues_as_dicts = [queue.to_dict() for queue in queues]
        return {'All_Queues': queues_as_dicts}


class GetAllApplications(Resource):
    def get(self):
        applications = cache.get('all_applications')
        if applications is None:
            applications = client.get_all_applications()
            cache.set('all_applications', applications)

        apps_as_dicts = [app.to_dict() for app in applications]
        return {'All_Applications': apps_as_dicts}


class GetAllChannels(Resource):
    def get(self):
        channels = cache.get('all_channels')
        if channels is None:
            channels = client.get_all_channels()
            cache.set('all_channels', channels)

        chs_as_dicts = [ch.to_dict() if hasattr(ch, 'to_dict') else 'Not a channel instance' for ch in channels]
        return {'All_Channels': chs_as_dicts}


class GetDependencyGraph(Resource):
    def get(self):
        global qmgr
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


api.add_resource(ClientConfig, '/clientconfig')
api.add_resource(GetAllQueueManagers, '/getallqueuemanagers')
api.add_resource(GetAllQueues, '/getallqueues')
api.add_resource(GetAllApplications, '/getallapplications')
api.add_resource(GetAllChannels, '/getallchannels')
api.add_resource(GetDependencyGraph, '/getdependencygraph')



if __name__ == "__main__":
    # app.run(debug=True)
    app.run(debug=True, ssl_context=("cert.pem","key.pem"))