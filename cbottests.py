from ChatBot.ChatBot import boot_chatbot, get_error_message_chatbot_response


query = 'can you explain what a 2035 error is?'

error_msg = """
{
    "event": {
        "type": "PCF",
        "header": {
            "type": 7,
            "strucLength": 36,
            "version": 1,
            "command": 44,
            "msgSeqNumber": 1,
            "control": 1,
            "compCode": 1,
            "reason": 2035,
            "parameterCount": 7
        },
        "queueManager": "QM1",
        "reasonQualifier": 2,
        "queueName": "INACCESSIBLE.QUEUE",
        "openOptions": 14352,
        "userIdentifier": "app",
        "applicationType": 6,
        "applicationName": "IBM MQ_REST_API"
    }
}
"""
retrieval_chain, conversation_chain = boot_chatbot()
print(get_error_message_chatbot_response(retrieval_chain, conversation_chain, error_msg))