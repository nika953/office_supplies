import hvac
import os
import json
from typing import Text

client = hvac.Client(
    url='http://127.0.0.1:8200',
    token='<YOUR_TOKEN>',
)


def create_secret(key: Text, value: Text) -> None:
    """
    Creates a secret (password) using the given key
    Args:
        key (Text): The key under which the secret is stored.
        value (Text): The secret (password) to store.
    """    
    client.secrets.kv.v2.create_or_update_secret(
        path=key,
        secret=dict(password=value),
    )

def retrieve_secret(key: Text) -> Text:
    """ 
    Reads the contents of the secret from the key value store by `key` and returns it as text
    Args:
        key (Text): Key to find the secret.

    Returns:
        Text: String
    """    
    read_response = client.secrets.kv.read_secret_version(path=key)
    return read_response['data']['data']['password']

def create_secret_from_file(key: Text, file_path: Text) -> None:
    """    
    Creates or updates a secret in key-value storage with the content of a specified file.
    Reads the content of a file from `file_path` and stores it in a secret at the given `key`.
    Args:
        key (Text): The key where the secret will be stored or updated.
        file_path (Text): The path to the file whose content will be stored in the secret.
    """    
    with open(file_path, 'r') as file:
        file_content = file.read()
    client.secrets.kv.v2.create_or_update_secret(
        path=key,
        secret=dict(file=file_content),
    ) 

def retrieve_secret_as_file(key: Text) -> dict:
    """    
    Retrieves the secret from the key value store the contents of the "file" in the secret data,
    and converts it from a JSON string to a dictionary.
    Args:
        key (Text): Key to find the secret.
    
    Returns:
        dict: Content of the 'file' as a dictionary.
    """    
    read_response = client.secrets.kv.read_secret_version(path=key)
    file_content = read_response['data']['data']['file']
    return json.loads(file_content)

if __name__ == '__main__':
    create_secret('SPREADSHEET_ID', '<YOUR_SPREADSHEET_ID>')
    creds_json_path = os.path.join(os.path.dirname(__file__), "..", "key.json")
    create_secret_from_file('google_sheets_service_account', creds_json_path)
