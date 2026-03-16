"""
Run this once to create the custom contact properties in HubSpot
that enrich_and_score.py writes to.

Usage:
    python3 scripts/setup_hubspot_properties.py
"""

import os
from dotenv import load_dotenv
from hubspot import HubSpot
from hubspot.crm.properties import PropertyCreate, ApiException

load_dotenv()


CUSTOM_PROPERTIES = [
    {
        "name": "icp_score",
        "label": "ICP Score",
        "type": "number",
        "field_type": "number",
        "description": "Ideal Customer Profile score (1–10) assigned by Claude AI",
        "group_name": "contactinformation",
    },
    {
        "name": "icp_reasoning",
        "label": "ICP Reasoning",
        "type": "string",
        "field_type": "textarea",
        "description": "Claude AI explanation for the ICP score",
        "group_name": "contactinformation",
    },
    {
        "name": "icp_top_signals",
        "label": "ICP Top Signals",
        "type": "string",
        "field_type": "textarea",
        "description": "Key positive signals identified by Claude AI",
        "group_name": "contactinformation",
    },
    {
        "name": "icp_disqualifiers",
        "label": "ICP Disqualifiers",
        "type": "string",
        "field_type": "textarea",
        "description": "Disqualifying factors identified by Claude AI",
        "group_name": "contactinformation",
    },
]


def main():
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise ValueError("HUBSPOT_ACCESS_TOKEN not set in environment")

    client = HubSpot(access_token=token)

    # Fetch existing property names to avoid duplicates
    existing = client.crm.properties.core_api.get_all(object_type="contacts")
    existing_names = {p.name for p in existing.results}

    created, skipped = 0, 0
    for prop in CUSTOM_PROPERTIES:
        if prop["name"] in existing_names:
            print(f"  ↷ Already exists: {prop['name']}")
            skipped += 1
            continue
        try:
            client.crm.properties.core_api.create(
                object_type="contacts",
                property_create=PropertyCreate(
                    name=prop["name"],
                    label=prop["label"],
                    type=prop["type"],
                    field_type=prop["field_type"],
                    description=prop["description"],
                    group_name=prop["group_name"],
                ),
            )
            print(f"  ✓ Created: {prop['name']}")
            created += 1
        except ApiException as e:
            print(f"  ✗ Failed to create {prop['name']}: {e}")

    print(f"\nDone. {created} created, {skipped} skipped.")


if __name__ == "__main__":
    main()
