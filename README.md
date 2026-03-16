# Lead Enrichment + ICP Scorer

Pulls contacts from HubSpot, scores them against your Ideal Customer Profile using Claude AI, and writes scores back to HubSpot.

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/mariewebster/lead-enrichment-scorer.git
cd lead-enrichment-scorer

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Credentials

| Variable | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot → Settings → Integrations → Private Apps |

## Usage

### 1. Create custom HubSpot properties (run once)
```bash
python3 scripts/setup_hubspot_properties.py
```

### 2. Enrich and score your leads
```bash
python3 scripts/enrich_and_score.py
```

Results are printed to the console and saved to `data/scored_leads.json`.

To write scores back to HubSpot, set `WRITE_SCORES_TO_HUBSPOT=true` in your `.env`.

## Sample Data

`data/sample/contacts.json` contains 5 example contacts for testing the scoring logic without a live HubSpot connection.

## Project Structure

```
lead-enrichment-scorer/
├── scripts/
│   ├── enrich_and_score.py        # Main pipeline
│   └── setup_hubspot_properties.py # One-time HubSpot setup
├── data/
│   └── sample/
│       └── contacts.json          # Sample leads for testing
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```
