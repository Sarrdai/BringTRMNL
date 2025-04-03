import os
import sys
import asyncio
import aiohttp
import logging
import requests
import json
from bring_api import Bring

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_bring_list():
    """
    Asynchronously fetch items from Bring list

    Returns:
    - List of items from Bring
    """
    # Retrieve credentials from environment variables
    email = os.environ.get('BRING_EMAIL')
    password = os.environ.get('BRING_PASSWORD')

    # Validate credentials
    if not all([email, password]):
        raise ValueError("Missing Bring credentials. Set BRING_EMAIL and BRING_PASSWORD environment variables.")

    # Create aiohttp client session
    async with aiohttp.ClientSession() as session:
        # Initialize Bring API
        bring = Bring(session, email, password)

        try:
            # Login to Bring
            await bring.login()

            # Get available lists
            lists = (await bring.load_lists()).lists

            # Validate lists exist
            if not lists:
                raise ValueError("No lists found in Bring account")

            # Get items from the first list (or use BRING_LIST_UUID if specified)
            list_uuid = os.environ.get('LIST_UUID')

            # Fetch list items
            items = await bring.get_list(list_uuid)

            return items.items.purchase

        except Exception as e:
            logger.error(f"Error fetching Bring list: {e}")
            raise


def limit_payload_size(items, max_size_bytes=2048):
    """
    Limit payload size to specified max size

    Args:
    - items: List of items to send
    - max_size_bytes: Maximum payload size in bytes

    Returns:
    - List of items that fit within the size limit
    """
    # Start with all items
    limited_items = items.copy()

    while True:
        # Prepare payload
        payload = {
            'merge_variables': {
                "collection": [
                    {
                        "title": item.itemId,
                        "description": item.specification
                    }
                    for item in limited_items
                ]
            }
        }

        # Convert payload to JSON and check size
        payload_json = json.dumps(payload)

        if len(payload_json.encode('utf-8')) <= max_size_bytes:
            return payload

        # Remove the last item if payload is too large
        if limited_items:
            limited_items.pop()
        else:
            # If we can't reduce further, return an empty list
            return {}

def send_to_trmnl_webhook(items, max_size_bytes=2048):
    """
    Send items to TRMNL webhook

    Args:
    - items: List of items to send
    """
    # Retrieve TRMNL webhook URL and Plugin UUID from environment variables
    webhook_url = os.environ.get('WEBHOOK_URL')

    # Validate webhook configuration
    if not webhook_url:
        raise ValueError(
            "Missing TRMNL webhook configuration. Set TRMNL_WEBHOOK_URL.")

    # Prepare collection payload
    limited_items = items.copy()

    data = limit_payload_size(items)

    try:
        # Send POST request to TRMNL webhook
        response = requests.post(
            f"{webhook_url}",
            json=data,
            headers={"Content-Type": "application/json"}
        )

        # Check response
        if response.status_code == 200:
            logger.info("Successfully sent items to TRMNL webhook")
        else:
            logger.error(f"Failed to send items. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")

    except Exception as e:
        logger.error(f"Error sending to TRMNL webhook: {e}")


async def main():
    """
    Main async function to fetch Bring list and send to TRMNL
    """
    try:
        # Fetch items from Bring list
        items = await fetch_bring_list()

        # Print items to console
        logger.info("Items in Bring list:")
        for item in items:
            logger.info(f"- {item.itemId} ({item.specification})")

        # Send items to TRMNL webhook
        send_to_trmnl_webhook(items)

    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == '__main__':
    # Run the async main function
    asyncio.run(main())

# Prerequisites:
# 1. Install required libraries:
#    pip install aiohttp requests bring-api
#
# 2. Set environment variables:
#    export BRING_EMAIL='your_email@example.com'
#    export BRING_PASSWORD='your_password'
#    export BRING_LIST_UUID='optional_specific_list_uuid'
#    export TRMNL_WEBHOOK_URL='your_webhook_url'
#    export TRMNL_PLUGIN_UUID='your_plugin_uuid'
#
# 3. Run the script:
#    python script_name.py