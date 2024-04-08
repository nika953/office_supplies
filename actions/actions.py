from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from googleapiclient.discovery import build
import httplib2
from oauth2client.service_account import ServiceAccountCredentials
from vault import vault

import pymorphy2
import re

SERVICE_ACCOUNT = vault.retrieve_secret_as_file('google_sheets_service_account')
SPREADSHEET_ID = vault.retrieve_secret('SPREADSHEET_ID')

morph = pymorphy2.MorphAnalyzer()


class ValidateOfficeSuppliesForm(FormValidationAction):
    """Handles form validation for office supplies order requests."""

    def name(self) -> Text:
        """Returns the name of this form action."""
        return "validate_office_supplies_form"

    async def validate_office_supplies(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """
        Validates the 'office_supplies' slot.
        Normalizes the office supply's name for consistency and checks availability. 
        Informs the user if the supply is unavailable.
        Args:
            slot_value: User-entered value for the office supplies order.
            dispatcher: Used to send messages to the user.
            tracker: Provides access to the user's messages and slots.
            domain: The current domain of Rasa.

        Returns:
            A dictionary with the 'office_supplies' slot set to normalized if available, otherwise None.
        """
        morph = pymorphy2.MorphAnalyzer()

        text = tracker.latest_message.get('text')
        pattern = r'\b(ручк[аиуеы]?|карандаш[аеи]?|ластик[аеиу]?)\b'
        
        normalized_value = re.search(pattern, text)

        if not normalized_value:
            dispatcher.utter_message(text=f"Извините, '{slot_value}' не доступен.\nМожет Вам нужно что-нибудь другое?\nУ нас есть: ручки, карандаши и ластики.")
            return {"office_supplies": None}

        else:
            normalized_value = morph.parse(normalized_value.group(0))[0].inflect({'sing', 'nomn'}).word 
            return {"office_supplies": normalized_value}

    async def required_slots(
        self,
        slots_mapped_in_domain: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker, domain: DomainDict
    ) -> List[Text]:
        """
        Determines additional slots required based on the office supply specified.
        Args:
            slots_mapped_in_domain: Slots currently mapped in the domain.
            dispatcher: Used to send messages back to the user.
            tracker: Provides access to the user's messages and slots.
            domain: The current Rasa domain.

        Returns:
            A list of required slots 
        """
        office_supplies = tracker.get_slot("office_supplies")

        if office_supplies == "ручка":
            return ["office_supplies", "color", "type", "quantity", "name"]
        elif office_supplies == "карандаш":
            return ["office_supplies", "type", "quantity", "name"]
        return ["office_supplies", "quantity", "name"]


class GoogleSheetsManager:

    def __init__(self, service_account_json, spreadsheet_id):
        """Initializes the GoogleSheetsManager with service account and spreadsheet details."""
        self.service_account_json = service_account_json
        self.spreadsheet_id = spreadsheet_id

    def get_service_sacc(self):
        """Authenticates and returns a Google Sheets API service object."""
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds_service = ServiceAccountCredentials.from_json_keyfile_dict(
            self.service_account_json, scopes).authorize(httplib2.Http())
        return build('sheets', 'v4', http=creds_service)

    def record_to_sheet(
        self, user_name,
        item_name: str, description: str,
        quantity, status: str = 'Заявка принята',
        range_name: str = 'Лист1!A:C'
    ) -> None:
        """Records a single office supply request to a specified Google Sheet."""
        service = self.get_service_sacc()
        values = [[user_name, item_name, description, quantity, status]]
        body = {'values': values}

        result = service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='RAW', body=body, insertDataOption='INSERT_ROWS').execute()

        print(f"{result.get('updates').get('updatedCells')} cells appended.")

    def aggregate_and_record_to_sheet(self, user_name, item_name, quantity) -> None:
        """Aggregates and records office supply requests, updating quantities if the item already exists."""
        service = self.get_service_sacc()
        range_name = 'Лист2!A:C'

        result = service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=range_name).execute()
        rows = result.get('values', [])

        for row in rows:
            if row[0] == user_name and row[1] == item_name:
                new_quantity = int(row[2]) + quantity
                service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id, range=f'Лист2!C{rows.index(row) + 1}',
                    valueInputOption='RAW', body={'values': [[new_quantity]]}).execute()
                print("Data aggregated and recorded on the second sheet.")
                return

        values = [[user_name, item_name, quantity]]
        service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='RAW', body={'values': values}, insertDataOption='INSERT_ROWS').execute()
        print("Data aggregated and recorded on the second sheet.")


class ActionRecordMissingItem(Action):
    """
    A custom action to record missing office supplies as specified by the user.
    Interacts with Google Sheets via GoogleSheetsManager to log and aggregate missing office supply requests.
    """

    def name(self) -> Text:
        """Returns the name of the action."""
        return "action_record_need_item"

    def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        """Executes the action to record and aggregate the missing office supply request.

        Args:
            dispatcher: Used to send messages back to the user.
            tracker: Provides access to user's messages and slots.
            domain: The current Rasa domain.

        Returns:
            An empty list, indicating no further actions are required.
        """
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
            description_item = ''
        else:
            description_item = f"{color_item}\n{type_item}"

        if missing_item:
            manager.record_to_sheet(
                user_name, missing_item.normal_form, description_item, quantity)
            manager.aggregate_and_record_to_sheet(
                user_name, missing_item.normal_form, quantity)
            dispatcher.utter_message(
                text=f"Записал, что у вас нет {missing_item.inflect({'sing', 'gent'}).word}. Что-нибудь еще?")
        else:
            dispatcher.utter_message(
                text="Я не понимаю, что вам не нужно. Можете уточнить?")

        return []
