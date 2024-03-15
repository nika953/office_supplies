from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

import os
from googleapiclient.discovery import build
import httplib2
from oauth2client.service_account import ServiceAccountCredentials
from vault import vault

SPREADSHEET_ID = vault.retrieve_secret('SPREADSHEET_ID')


class GoogleSheetsManager:

    def __init__(self, creds_json_path, spreadsheet_id):
        self.creds_json_path = creds_json_path
        self.spreadsheet_id = spreadsheet_id

    def get_service_sacc(self):
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds_service = ServiceAccountCredentials.from_json_keyfile_name(self.creds_json_path, scopes).authorize(httplib2.Http())
        return build('sheets', 'v4', http=creds_service)

    def record_to_sheet(self, item_name: str, range_name: str = 'Лист1!B:B'):
        service = self.get_service_sacc()
        values = [[item_name]]
        body = {'values': values}
        
        result = service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='RAW', body=body, insertDataOption='INSERT_ROWS').execute()
        
        print(f"{result.get('updates').get('updatedCells')} cells appended.")

    @staticmethod
    def extract_missing_item(text: str, prefix: str = "У меня нет ") -> str:
        if text.startswith(prefix):
            return text[len(prefix):]
        return ""



class ActionRecordMissingItem(Action):
    def name(self) -> Text:
        return "action_record_need_item"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message_text = tracker.latest_message.get('text')
        print(tracker.latest_message['intent']['name'])
        print(tracker.get_slot('office_supplies'))

    
        creds_json_path = os.path.join(os.path.dirname(__file__),"..", "key.json")

        manager = GoogleSheetsManager(creds_json_path, SPREADSHEET_ID)
        missing_item = manager.extract_missing_item(message_text)
        print(missing_item)
        if missing_item:
            manager.record_to_sheet(missing_item)
            dispatcher.utter_message(text=f"Записал, что у вас нет {missing_item}. Что-нибудь еще?")
        else:
            dispatcher.utter_message(text="Я не понимаю, что вам не нужно. Можете уточнить?")
        
        return []