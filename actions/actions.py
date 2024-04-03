from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from googleapiclient.discovery import build
import httplib2
from oauth2client.service_account import ServiceAccountCredentials
from vault import vault

import pymorphy2

SERVICE_ACCOUNT = vault.retrieve_secret_as_file('google_sheets_service_account')
SPREADSHEET_ID = vault.retrieve_secret('SPREADSHEET_ID')

morph = pymorphy2.MorphAnalyzer()

class ValidateOfficeSuppliesForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_office_supplies_form"

    async def validate_office_supplies(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        morph = pymorphy2.MorphAnalyzer()
        normalized_value = morph.parse(slot_value)[0].inflect({'sing', 'nomn'}).word

        if normalized_value:
            return {"office_supplies": normalized_value}
        else:
            dispatcher.utter_message(text=f"Извините, '{slot_value}' не доступен.")
            return {"office_supplies": None}

    async def required_slots(
            self, slots_mapped_in_domain: List[Text], dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: DomainDict) -> List[Text]:
        office_supplies = tracker.get_slot("office_supplies")
        
        if office_supplies == "ручка":
            return ["office_supplies", "color", "type", "quantity", "name"] 
        elif office_supplies == "карандаш":
            return ["office_supplies", "type", "quantity", "name"]  
        return ["office_supplies", "quantity", "name"] 
     
class GoogleSheetsManager:

    def __init__(self, service_account_json, spreadsheet_id):
        self.service_account_json = service_account_json
        self.spreadsheet_id = spreadsheet_id

    def get_service_sacc(self):
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds_service = ServiceAccountCredentials.from_json_keyfile_dict(self.service_account_json, scopes).authorize(httplib2.Http())
        return build('sheets', 'v4', http=creds_service)

    def record_to_sheet(self, user_name, item_name: str, description: str, quantity, status: str = 'Заявка принята', range_name: str = 'Лист1!A:C'):
        service = self.get_service_sacc()
        values = [[user_name, item_name, description, quantity, status]]
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

        missing_item = morph.parse(tracker.get_slot('office_supplies'))[0]
        color_item = tracker.get_slot('color')
        type_item = tracker.get_slot('type')
        user_name = tracker.get_slot('name')
        quantity = int(tracker.get_slot('quantity'))

        if not color_item:
            color_item = "" 
        else:
            color_item = f"Цвет: {morph.parse(color_item)[0].inflect({'masc', 'sing', 'nomn'}).word}"

        if not type_item:
            type_item = ""
        else:
            if missing_item.tag.gender == "masc":
                type_item = f"Вид: {morph.parse(type_item)[0].inflect({'masc', 'sing', 'nomn'}).word}"
            if missing_item.tag.gender == "femn":
                type_item = f"Вид: {morph.parse(type_item)[0].inflect({'femn', 'sing', 'nomn'}).word}"
            if missing_item.tag.gender == "neut":
                type_item = f"Вид: {morph.parse(type_item)[0].inflect({'neut', 'sing', 'nomn'}).word}"
        
        if color_item == "" and type_item == "":
            description_item =''
        else:
            description_item = f"{color_item}\n{type_item}"


        if missing_item:
            manager.record_to_sheet(user_name, missing_item.normal_form, description_item, quantity)
            dispatcher.utter_message(text=f"Записал, что у вас нет {missing_item.inflect({'sing', 'gent'}).word}. Что-нибудь еще?")
        else:
            dispatcher.utter_message(text="Я не понимаю, что вам не нужно. Можете уточнить?")
        
        return []
    



    