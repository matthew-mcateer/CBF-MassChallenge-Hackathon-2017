import json
import sys
import time
from datetime import datetime
import requests

from watson_developer_cloud import ConversationV1

class UndergroundBot():

    def __init__(self, user_store, dialog_store, conversation_username, conversation_password, conversation_workspace_id, weather_id, weather_password):
        """
        Creates a new instance of UndergroundBot.
        Parameters
        ----------
        user_store - Instance of CloudantUserStore used to store and retrieve users from Cloudant
        dialog_store - Instance of CloudantDialogStore used to store conversation history
        conversation_username - The Watson Conversation username
        conversation_password - The Watson Converation password
        conversation_workspace_id - The Watson Conversation workspace ID
        weather_id - the Watson Weather ID
        weather_password - the Watson Weather Password
        """
        self.user_store = user_store
        self.dialog_store = dialog_store
        self.dialog_queue = {}
        self.conversation_client = ConversationV1(
            username=conversation_username,
            password=conversation_password,
            version='2016-07-11'
        )
        self.conversation_workspace_id = conversation_workspace_id
        self.weather_id = weather_id
        self.weather_password = weather_password

    def init(self):
        """
        Initializes the bot, including the required datastores.
        """
        self.user_store.init()
        self.dialog_store.init()


    def process_message(self, message_sender, message):
        """
        Process the message entered by the user.  HEEEEERRRRRRREEEEE
        Parameters
        ----------
        message_sender - The User ID from the messaging platform (Slack ID, or unique ID associated with the WebSocket client) 
        message - The message entered by the user
        """
        conversation_response = None
        try:
            user = self.get_or_create_user(message_sender)
            conversation_response = self.send_request_to_watson_conversation(message, user['conversation_context'])
            reply = self.handle_response_from_watson_conversation(message, user, conversation_response)
            self.update_user_with_watson_conversation_context(user, conversation_response['context'])
            return {'conversation_response': conversation_response, 'text': reply}
        except Exception:
            print(sys.exc_info())
            # clear state and set response
            reply = "Sorry, something went wrong!"
            return {'conversation_response': conversation_response, 'text': reply}

    def send_request_to_watson_conversation(self, message, conversation_context):
        """
        Sends the message entered by the user to Watson Conversation
        along with the active Watson Conversation context that is used to keep track of the conversation.
        Parameters
        ----------
        message - The message entered by the user
        conversation_context - The active Watson Conversation context
        """
        return self.conversation_client.message(
            workspace_id=self.conversation_workspace_id,
            message_input={'text': message},
            context=conversation_context
        )

    def handle_response_from_watson_conversation(self, message, user, conversation_response):
        """ 
        Takes the response from Watson Conversation, performs any additional steps
        that may be required, and returns the reply that should be sent to the user.
        Parameters
        ----------
        message - The message sent by the user
        user - The active user stored in Cloudant
        conversation_response - The response from Watson Conversation
        """
        conversation_doc_id = self.get_or_create_active_conversation_id(user, conversation_response)
            
        if 'context' in conversation_response.keys() and 'action' in conversation_response['context'].keys():
            action = conversation_response['context']['action']
        else:
            action = None
        conversation_response['context']['action'] = None
        if action == "findWeather":

            reply = self.handle_find_weather_forecast(conversation_response)
        else:
            reply = self.handle_default_message(conversation_response)

        # Finally, we log every action performed as part of the active conversation
        # in our Cloudant dialog database and return the reply to be sent to the user.
        if conversation_doc_id is not None and action is not None:
            self.log_dialog(conversation_doc_id, action, message, reply)
        
        # return reply to be sent to the user
        return reply

    def handle_default_message(self, conversation_response):
        """
        The default handler for any message from Watson Conversation that requires no additional steps.
        Returns the reply that was configured in the Watson Conversation dialog.
        Parameters
        ----------
        conversation_response - The response from Watson Conversation
        """
        reply = ''
        for text in conversation_response['output']['text']:
            reply += text + "\n"
        return reply

    def handle_find_weather_forecast(self, conversation_response):
        """
        Handles a weather request.
        Returns a reply based on the date and location provided by the user input.
        Parameters
        __________
        conversation_response - The response from Watson Conversation
        """

        #Calculate days in between the given and today's date
        date_format = "%Y-%m-%d"
        today = datetime.now().strftime(date_format)
        given_date = conversation_response['context']['date']
        a = datetime.strptime(today, date_format)
        b = datetime.strptime(given_date, date_format)
        delta = b - a
        days = delta.days

        #Check if date is valid. Weather forecast is for 10 days and cannot predict past.
        if days < 0 :
            reply = "I see you already went. Hope you had a great trip!\n\n"
            reply = reply + "Would you like to enter another location?"
            return reply
        elif days > 9 :
            reply = "Unfortunately, I cannot provide weather forecasts more than 9 days ahead. Sorry for any inconvenience.\n\n"
            reply = reply + "Would you like to enter another location?"
            return reply

        #Url for location services
        watson_location_url = 'https://{}:{}@twcservice.mybluemix.net:443/api/weather/v3/location/search?query={}&language=en-US'.format(self.weather_id, self.weather_password, conversation_response['context']['location'])

        try:
            #Search the location
            location = requests.get(watson_location_url, auth=(self.weather_id, self.weather_password))

            #Convert location to json
            location = json.loads(location.text)

            #Get latitude and longitude and address
            latitude = str(location['location']['latitude'][0])
            longitude = str(location['location']['longitude'][0])
            address = location['location']['address'][0]

            #URL for 10 day weather forecast. Convert the forecast to json.
            watson_weather_url = 'https://{}:{}@twcservice.mybluemix.net:443/api/weather/v1/geocode/{}/{}/forecast/daily/10day.json'.format(self.weather_id, self.weather_password, latitude, longitude)
            weather = requests.get(watson_weather_url, auth=(self.weather_id, self.weather_password))
            weather = json.loads(weather.text)
            
            #Get day and forecast
            day_of_week = weather["forecasts"][days]["day"]["daypart_name"]
            forecast = weather["forecasts"][days]["narrative"]

            #Lowercase for words today and tomorrow
            if (days <= 1) :
                day_of_week = day_of_week.lower()

            #Set reply
            reply = "Let me gather the weather forecast in {} for you.\n\n".format(address)
            reply = reply + "The forecast for {} says :\n{}\n\n".format(day_of_week, forecast)
            reply = reply + "Would you like to enter another location?"
            return reply
        except:
            return "Sorry, I couldn't find the weather forecast for {}\n\nWould you like to enter another location?".format(conversation_response['context']['location'])


    def get_or_create_user(self, message_sender):
        """
        Retrieves the user doc stored in the Cloudant database associated with the current user interacting with the bot.
        First checks if the user is stored in Cloudant. If not, a new user is created in Cloudant.
        Parameters
        ----------
        message_sender - The User ID from the messaging platform (Slack ID, or unique ID associated with the WebSocket client) 
        """
        return self.user_store.add_user(message_sender)

    def update_user_with_watson_conversation_context(self, user, conversation_context):
        """
        Updates the user doc in Cloudant with the latest Watson Conversation context.
        Parameters
        ----------
        user - The user doc associated with the active user
        conversation_context - The Watson Conversation context
        """
        return self.user_store.update_user(user, conversation_context)

    def get_or_create_active_conversation_id(self, user, conversation_response):
        """
        Retrieves the ID of the active conversation doc in the Cloudant conversation log database for the current user.
        If this is the start of a new converation then a new document is created in Cloudant,
        and the ID of the document is associated with the Watson Conversation context.
        Parameters
        ----------
        user - The user doc associated with the active user
        conversation_response - The response from Watson Conversation
        """
        if 'newConversation' in conversation_response['context'].keys():
            new_conversation = conversation_response['context']['newConversation']
        else:
            new_conversation = False
        if new_conversation == True:
            conversation_response['context']['newConversation'] = False
            converation_doc = self.dialog_store.add_conversation(user['_id'])
            conversation_response['context']['conversationDocId'] = converation_doc['_id']
            return converation_doc['_id']
        elif 'conversationDocId' in conversation_response['context'].keys():
            return conversation_response['context']['conversationDocId']
        else:
            return None

    def log_dialog(self, conversation_doc_id, name, message, reply):
        """
        Logs the dialog traversed in Watson Conversation by the current user to the Cloudant log database.
        Parameters
        ----------
        conversation_doc_id - The ID of the active conversation doc in Cloudant 
        name - The name of the dialog (action)
        message - The message sent by the user
        reply - The reply sent to the user
        """
        dialog_doc = {
            'name': name,
            'message': message,
            'reply': reply,
            'date': int(time.time()*1000)
        }
        self.dialog_store.add_dialog(conversation_doc_id, dialog_doc)
