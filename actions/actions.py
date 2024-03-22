from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from googleapiclient.discovery import build
import httplib2
from oauth2client.service_account import ServiceAccountCredentials
from vault import vault

import pymorphy2

SERVICE_ACCOUNT = vault.retrieve_secret_as_file('google_sheets_service_account')
SPREADSHEET_ID = vault.retrieve_secret('SPREADSHEET_ID')

morph = pymorphy2.MorphAnalyzer()


class GoogleSheetsManager:

    def __init__(self, service_account_json, spreadsheet_id):
        self.service_account_json = service_account_json
        self.spreadsheet_id = spreadsheet_id

    def get_service_sacc(self):
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds_service = ServiceAccountCredentials.from_json_keyfile_dict(self.service_account_json, scopes).authorize(httplib2.Http())
        return build('sheets', 'v4', http=creds_service)

    def record_to_sheet(self, user_name, item_name: str, description: str, range_name: str = 'Лист1!A:C'):
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
        
        manager = GoogleSheetsManager(SERVICE_ACCOUNT, SPREADSHEET_ID)
        user_name = tracker.get_slot('name')
        missing_item = morph.parse(tracker.get_slot('office_supplies'))[0]
        color_item = morph.parse(tracker.get_slot('color'))[0]
        type_item = morph.parse(tracker.get_slot('type'))[0]

        if color_item == None:
            color_item = "" 

        if type_item == None:
            type_item = "" 

        description_item = f"Цвет чернил: {color_item.inflect({'masc', 'sing', 'nomn'}).word}\nВид: {type_item.inflect({'femn', 'sing', 'nomn'}).word}"


        if missing_item:
            manager.record_to_sheet(user_name, missing_item.normal_form, description_item)
            dispatcher.utter_message(text=f"Записал, что у вас нет {missing_item.inflect({'sing', 'gent'}).word}. Что-нибудь еще?")
        else:
            dispatcher.utter_message(text="Я не понимаю, что вам не нужно. Можете уточнить?")
        
        return []
    