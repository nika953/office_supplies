from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

import os
from googleapiclient.discovery import build
import httplib2
from oauth2client.service_account import ServiceAccountCredentials
from vault import vault

SERVICE_ACCOUNT = vault.retrieve_secret_as_file('google_sheets_service_account')
# print(SERVICE_ACCOUNT)
# print(type(SERVICE_ACCOUNT))
SPREADSHEET_ID = vault.retrieve_secret('SPREADSHEET_ID')


class GoogleSheetsManager:

    def __init__(self, service_account_json, spreadsheet_id):
        self.service_account_json = service_account_json
        self.spreadsheet_id = spreadsheet_id

    def get_service_sacc(self):
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds_service = ServiceAccountCredentials.from_json_keyfile_dict(self.service_account_json, scopes).authorize(httplib2.Http())
        return build('sheets', 'v4', http=creds_service)

    def record_to_sheet(self, user_name, item_name: str, description, range_name: str = 'Лист1!A:C'):
        service = self.get_service_sacc()
        values = [[user_name, item_name, description]]
        body = {'values': values}
        
        result = service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='RAW', body=body, insertDataOption='INSERT_ROWS').execute()
        
        print(f"{result.get('updates').get('updatedCells')} cells appended.")


class ActionRecordMissingItem(Action):
    def name(self) -> Text:
        return "action_record_need_item"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # print(tracker.latest_message['intent']['name'])
        # print(tracker.get_slot('office_supplies'))
        # print(tracker.get_slot('color'))
        # print(tracker.get_slot('kind'))
        # print(tracker.get_slot('name'))
    
        manager = GoogleSheetsManager(SERVICE_ACCOUNT, SPREADSHEET_ID)
        user_name = tracker.get_slot('name')
        missing_item = tracker.get_slot('office_supplies')
        description_item = f"{tracker.get_slot('color')}, {tracker.get_slot('kind')}"

        if missing_item:
            manager.record_to_sheet(user_name, missing_item, description_item)
            dispatcher.utter_message(text=f"Записал, что у вас нет {missing_item}. Что-нибудь еще?")
        else:
            dispatcher.utter_message(text="Я не понимаю, что вам не нужно. Можете уточнить?")
        
        return []
    