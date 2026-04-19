# SLA Airlines — AI Agent

**SE 4458 Assignment 2** — Sıla Barışık

An AI-powered chat application that lets users search flights, book tickets, and check in through natural conversation. The agent is built on top of the Flask Airline API from the airline api project.

## Links

- **🚀 Live demo:** https://sila-agent-ckd5a2cuach5gnb8.francecentral-01.azurewebsites.net
- **Agent repo (this one):** https://github.com/slabarsk/airline-agent
- **Airline API repo:** https://github.com/slabarsk/sla-airline-api
- **API gateway (public):** https://sila-api-air-gsh6hgdxgwcedub0.francecentral-01.azurewebsites.net
- **Demo video:** _coming soon_

## Try it

The whole stack is deployed on Azure. Click the live demo link, pick a route like İstanbul–İzmir, select a date from the calendar, choose a flight card, and book a ticket. The conversation is in Turkish by default but the agent switches to English if you open in English.

## Architecture

```
┌──────────────┐   HTTP    ┌──────────────┐   stdio   ┌────────────┐   HTTPS    ┌─────────────┐   SQL    ┌───────────────┐
│   React UI   │ ───────▶  │ Agent (Flask │ ───────▶  │ MCP Server │ ────────▶  │  API Gateway│ ──────▶  │ PostgreSQL DB │
│   (Azure)    │           │  + LLM)      │           │   (Python) │            │    (Azure)  │          │   (managed)   │
└──────────────┘           └──────────────┘           └────────────┘            └─────────────┘          └───────────────┘
                                   │                                                    │
                                   │                                                    │
                                   └────────  tool calling (JSON schema)  ──────────────┘
```

Each arrow corresponds to a real network boundary. The user types a message in the React UI; the agent backend forwards it to an open-source LLM via Groq along with the tool schemas; the LLM decides which tool to call; the MCP server translates that tool call into an HTTP request to the gateway; the gateway enforces rate limiting and proxies the call to the Flask API; the Flask API talks to the managed PostgreSQL instance and returns the data back up the chain.

The React UI and the agent backend live in the same Azure App Service (`sila-agent`) so the frontend makes same-origin requests and no CORS setup is needed. The gateway and the Flask API live in a second App Service (`sila-api-air`) as a separate public endpoint — this is the split the airline api project was missing.

## Components

| Component       | Path                  | Deployment           | Responsibility                                                              |
| --------------- | --------------------- | -------------------- | --------------------------------------------------------------------------- |
| Frontend        | `frontend/`           | Azure App Service 1  | React chat UI with inline date picker, flight cards, booking confirmation   |
| Agent backend   | `agent-backend/`      | Azure App Service 1  | Flask app that connects the UI, the LLM, and the MCP client                 |
| MCP server      | `mcp-server/`         | subprocess (stdio)   | Exposes three tools (`query_flight`, `book_flight`, `check_in`) to the LLM  |
| API gateway     | `sla-airline-api` repo| Azure App Service 2  | Public entry point; rate limits and forwards to the Flask API               |
| Flask API       | `sla-airline-api` repo| Azure App Service 2  | Business logic, JWT auth, database access                                   |

## Tools exposed to the LLM

The MCP server implements the three tools required by the assignment:

1. `query_flight(date_from, airport_from, airport_to, number_of_people)` — searches available flights
2. `book_flight(flight_number, passenger_names)` — creates tickets for one or more passengers
3. `check_in(flight_number, passenger_name)` — assigns a seat number to a booked passenger

The LLM receives the JSON schema for each tool at the start of every conversation and chooses when to invoke them. The UI silently collects the structured tool results and renders them as flight cards, booking confirmations, and check-in receipts instead of dumping raw JSON into the chat.

## Running locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Groq API key (free tier is enough): https://console.groq.com/keys
- A PostgreSQL database URL (local Postgres or any managed provider)

### 1. Flask API (airline api repo)

```bash
git clone https://github.com/slabarsk/sla-airline-api.git
cd sla-airline-api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# create .env
cp .env.example .env
# edit .env and set DATABASE_URL and JWT_SECRET_KEY

# seed the database (one time)
python3 seed.py

# start the API and the gateway
python3 run.py       # starts on port 5000
python3 gateway.py   # starts on port 8080 (in another terminal)
```

### 2. Agent backend + frontend

```bash
git clone https://github.com/slabarsk/airline-agent.git
cd airline-agent

# Agent backend
cd agent-backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set GROQ_API_KEY, GATEWAY_URL, MCP_SERVER_PATH

# Build the React frontend
cd ../frontend
npm install
npm run build

# Start the agent (it serves the built React app too)
cd ../agent-backend
python3 agent.py
```

Open http://localhost:8000 in a browser. The agent serves both the chat API and the frontend on the same port.

## Design decisions and assumptions

**MCP over direct HTTP from the agent.** The LLM could have been wired directly to the gateway, but the assignment asks for an MCP server and it cleanly separates _tool description_ from _tool execution_. The LLM only sees the MCP schema; the MCP server is the only component that knows the real HTTP endpoints.

**Tool results shaped for the UI, not only the LLM.** When `query_flight` returns, the agent sends both the natural-language reply _and_ the raw tool result to the frontend. The frontend renders the structured data as flight cards with a "Book this flight" button, so the user rarely has to type a flight number manually. This keeps the conversation short and removes a whole class of typos.

**Inline date picker.** Once the user names a route, the frontend fetches the list of available dates for that route from the gateway and renders a compact calendar inside the chat. The LLM never has to ask "which date?" if the user has already picked one visually. This also sidesteps the ambiguity of parsing dates like "20 Mayıs" vs "May 20" in Turkish.

**Frontend served by the agent.** Rather than deploying the React app to a separate static host, the agent's Flask app serves `frontend/build/` at the root and routes `/chat` and `/dates` to its own handlers. One App Service, one URL, no CORS to configure.

**Conversation-history cap.** The agent only forwards the last twelve messages to the LLM. Earlier turns are dropped. This prevents token bloat on long bookings and also prevents the LLM from "remembering" stale tool results and re-using them when a user starts a new flow.

**Single hard-coded API user.** The assignment allows assuming a constant user for the chat. The agent uses `admin / 1234` internally when the gateway needs a JWT; end users never see or provide credentials.

**Language detection.** The system prompt pins the reply language to whichever language the user opens the conversation in. Turkish users get Turkish replies; English users get English. The city-to-IATA mapping is Turkish-friendly (İstanbul → IST, İzmir → ADB, etc.) so the user never has to know airport codes.

**Rate limit on the gateway.** The gateway enforces a per-IP daily cap (default 1000) to prevent a broken agent loop from hammering the API. The limit is exposed through a `DAILY_LIMIT` environment variable.

## Airline api feedback addressed

Two issues were flagged in the airline api and have been resolved for this assignment:

1. **SQLite → managed PostgreSQL.** The airline api used a local SQLite file, which was called out as insufficient for a real deployment. The API now connects to a managed PostgreSQL instance over SSL, configured via `DATABASE_URL`. The seed script loads 386 flights across the served routes on first run.
2. **Gateway deployed as a separate public service.** The airline api had a working gateway locally but it was never deployed; the graded deployment served the Flask API directly. For Assignment 2 the gateway has been deployed to Azure App Service as the single public entry point. All agent traffic — including every MCP tool call — goes through `/api/v1/...` on the gateway, which then forwards internally to the Flask API. The gateway's `/health` endpoint can be used to verify that both processes are alive.

## Issues encountered

**Paginated date filtering.** The airline api's `query_flights` loaded the first ten flights for a route and then filtered by date _in Python_. Any flight matching the date but sitting on page two of the pagination would silently disappear. I moved the date filter into the SQLAlchemy query so the database returns only that day's flights and pagination works on the filtered set.

**LLM fabricating flight numbers.** Under rate pressure on the primary 70B model, Groq falls back to smaller models that are less disciplined about tool use. Those models would occasionally write `query_flight { ... }` as plain text in the reply and invent flight numbers rather than actually invoking the tool. I addressed this two ways: (a) the system prompt now has explicit "never invent, never simulate a tool call" rules, and (b) after every tool result the agent injects a strict reminder into the message list ("these are the exact flights returned — present only these"). The `clean_reply` regex strips any leaked tool-call syntax before the reply reaches the UI as a last line of defense.

**Gateway URL double-prefix.** The gateway was originally configured with `API_URL=http://127.0.0.1:5000/api/v1`. Every forward then produced `/api/v1/api/v1/...` because the incoming path already included `/api/v1`. Fixed by dropping the prefix from `API_URL` and letting the path catch-all carry it.

**Azure stdout swallowing gunicorn logs.** On first deploy the logs were empty because gunicorn was writing to its own log files inside the container. Adding `--access-logfile - --error-logfile -` to the gunicorn command made the logs visible in the Azure log stream, which turned debugging from guesswork into a five-minute exercise.

**Azure extracting the app to a temp directory.** Oryx (Azure's build engine) unpacks the deployment artifact to `/tmp/<hash>/` rather than the intuitive `/home/site/wwwroot/`. The first version of `startup.sh` had the wrong absolute paths and couldn't find the frontend build. Fixed by resolving paths relative to `$(dirname "${BASH_SOURCE[0]}")` so the script works wherever Azure lands it.

## Tech stack

- **Frontend:** React 18
- **Agent backend:** Flask, open-source LLM via Groq
- **MCP:** Python `mcp` SDK
- **API & gateway:** Flask, gunicorn
- **Database:** managed PostgreSQL
- **Hosting:** Azure App Service (two separate services), CI/CD via GitHub Actions