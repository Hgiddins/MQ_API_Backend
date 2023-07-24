


import requests
from requests.auth import HTTPBasicAuth

# replace with your appliance's IP address or domain name
address = "https://web-qm1-e79d.qm.eu-gb.mq.appdomain.cloud/ibmmq/rest/v1/admin"



# replace 'username' and 'password' with your actual username and password
auth = HTTPBasicAuth('ucabffc', 'F7Uy9QeB_cvv8kzrrhrvRBDrIASu-d0erIs4Se2Fj_-P')

# get list of available directories
response = requests.get(f'{address}/qmgr?attributes=*', auth=auth)
if response.status_code == 200:
    print(response.json())
else:
    print(f"Error: {response.status_code}, {response.text}")


#
# # get contents of a specific directory
# response = requests.get(f'{address}/mgmt/filestore/default/{directory}', auth=auth)
# print(response.json())
#
# # get contents of a specific file
# response = requests.get(f'{address}/mgmt/filestore/default/{directory}/{file}', auth=auth)
# print(response.json())
#
#
# # Get all users
# users = mgmt_client.get_all_users()
# print(users)


