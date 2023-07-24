from DependencyGraph import DependencyGraph
import MQ
import timeit
import json
from PolicyConfiguration import *

client = MQ.Client(url="https://13.87.80.195:9443", qmgr="QM2", username="mqadmin", apikey = 'mqadmin')


def test():


    queues = client.get_all_queue_managers()
    # config = PolicyConfiguration( queue_name_max_length=5)
    for q in queues:
        print(q.to_dict())



    # print(queues.to_dict())



test()
# if __name__ == '__main__':
#     execution_time = timeit.timeit(Test, number=1)
#     print("Execution time: {:.2f} seconds".format(execution_time))

