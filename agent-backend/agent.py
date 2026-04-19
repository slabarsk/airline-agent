from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
import httpx
import json
import re
import os
import asyncio

load_dotenv()

FRONTEND_BUILD = os.path.join(os.path.dirname(__file__), "../frontend/build")

app = Flask(
    __name__,
    static_folder=FRONTEND_BUILD,
    static_url_path=""
)
CORS(app)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    full_path = os.path.join(FRONTEND_BUILD, path)
    if path and os.path.exists(full_path) and not os.path.isdir(full_path):
        return send_from_directory(FRONTEND_BUILD, path)
    return send_from_directory(FRONTEND_BUILD, "index.html")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GATEWAY_URL  = os.environ.get("GATEWAY_URL", "http://127.0.0.1:5000/api/v1")
MCP_SERVER   = os.environ.get(
    "MCP_SERVER_PATH",
    os.path.join(os.path.dirname(__file__), "../mcp-server/server.py")
)

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY bulunamadı. .env dosyasını kontrol et.")

client = Groq(api_key=GROQ_API_KEY)

MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]

def get_active_model():
    for model in MODELS:
        try:
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=3
            )
            print(f"✅ Aktif model: {model}")
            return model
        except Exception as e:
            print(f"⚠️ {model} kullanılamıyor: {e}")
            continue
    print("⚠️ Hiçbir model kullanılabilir değil")
    return None

ACTIVE_MODEL = get_active_model()

def groq_create(**kwargs):
    global ACTIVE_MODEL
    for model in MODELS:
        try:
            kwargs["model"] = model
            result = client.chat.completions.create(**kwargs)
            ACTIVE_MODEL = model
            return result
        except Exception as e:
            err = str(e)
            if "rate_limit" in err or "429" in err or "decommissioned" in err:
                print(f"⚠️ {model} atlandı: {err[:80]}")
                continue
            raise e
    raise Exception("ALL_MODELS_BUSY")

def clean_reply(text):
    if not text:
        return ""
    # XML-style function tags
    text = re.sub(r'<function=\w+\(.*?\)>\s*\{.*?\}\s*</function>', '', text, flags=re.DOTALL)
    text = re.sub(r'<function=\w+>.*?</function>', '', text, flags=re.DOTALL)
    text = re.sub(r'<function=\w+\([^)]*\)>', '', text)
    text = re.sub(r'</?function[^>]*>', '', text)
    # assistant="query_flight"{...}
    text = re.sub(r'(assistant|tool)=["\']?\w+["\']?\s*\{.*?\}', '', text, flags=re.DOTALL)
    # Bare tool-name + JSON:  query_flight {...}   or   query_flight>{...}
    text = re.sub(
        r'\b(query_flight|book_flight|check_in)\s*>?\s*\{.*?\}',
        '', text, flags=re.DOTALL
    )
    # Standalone JSON objects (starts with { and has "quoted keys")
    text = re.sub(r'\{[^{}]*"(?:airport_from|airport_to|date_from|number_of_people|flight_number|passenger_name|passenger_names|flights)"[^{}]*\}', '', text, flags=re.DOTALL)
    # Code fences
    text = re.sub(r'```(?:json)?.*?```', '', text, flags=re.DOTALL)
    # Collapse multiple blank lines and stray whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def normalize_date(date_str):
    if not date_str:
        return date_str
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        if 'T' not in date_str:
            return date_str + "T00:00:00"
        return date_str
    match = re.search(r'\(=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\)', date_str)
    if match:
        return match.group(1)
    return date_str

def preprocess_messages(messages):
    month_map = {
        "ocak": "01", "şubat": "02", "mart": "03", "nisan": "04",
        "mayıs": "05", "haziran": "06", "temmuz": "07", "ağustos": "08",
        "eylül": "09", "ekim": "10", "kasım": "11", "aralık": "12"
    }
    result = []
    for m in messages:
        content = m.get("content") or ""
        for month_tr, month_num in month_map.items():
            pattern = rf'(\d{{1,2}})\s+{month_tr}(?:\s+(\d{{4}}))?'
            def replace_date(match, mn=month_num, mtr=month_tr):
                day  = match.group(1).zfill(2)
                year = match.group(2) or "2026"
                return f"{day} {mtr.capitalize()} {year} (={year}-{mn}-{day}T00:00:00)"
            content = re.sub(pattern, replace_date, content, flags=re.IGNORECASE)
        result.append({**m, "content": content})
    return result

def extract_route(messages):
    user_texts = [m.get("content", "") or "" for m in messages if m.get("role") == "user"]
    all_text = " ".join(user_texts[-3:]).lower()
    code_map = {
        "istanbul": "IST", "ist": "IST",
        "izmir": "ADB", "adb": "ADB",
        "ankara": "ESB", "esb": "ESB",
        "frankfurt": "FRA", "fra": "FRA",
        "antalya": "AYT", "ayt": "AYT",
    }
    clean_text = re.sub(
        r'(istanbul|izmir|ankara|frankfurt|antalya)[a-zışğüöç]*',
        lambda m: m.group(0)[:len(m.group(1))], all_text
    )
    words = clean_text.split()
    found = [code_map[w] for w in words if w in code_map]
    unique = list(dict.fromkeys(found))
    if len(unique) >= 2 and unique[0] != unique[1]:
        return {"from": unique[0], "to": unique[1]}
    return None

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_flight",
            "description": "Search available flights between airports on a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from":        {"type": "string",  "description": "Departure datetime ISO e.g. 2026-05-01T00:00:00"},
                    "airport_from":     {"type": "string",  "description": "IATA departure code e.g. IST"},
                    "airport_to":       {"type": "string",  "description": "IATA arrival code e.g. ESB"},
                    "number_of_people": {"type": "integer", "description": "Number of passengers"}
                },
                "required": ["date_from", "airport_from", "airport_to", "number_of_people"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_flight",
            "description": "Book flight tickets for one or more passengers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number":   {"type": "string", "description": "Flight number e.g. TK101"},
                    "passenger_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of passenger full names"
                    }
                },
                "required": ["flight_number", "passenger_names"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_in",
            "description": "Check in a passenger to their booked flight.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number":  {"type": "string", "description": "Flight number"},
                    "passenger_name": {"type": "string", "description": "Passenger full name"}
                },
                "required": ["flight_number", "passenger_name"]
            }
        }
    }
]

async def call_mcp_tool(tool_name: str, tool_args: dict) -> str:
    server_params = StdioServerParameters(
        command="python3",
        args=[MCP_SERVER],
        env={"GATEWAY_URL": GATEWAY_URL}
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_args)
            return result.content[0].text

def run_mcp_tool(tool_name: str, tool_args: dict) -> str:
    try:
        result = asyncio.run(call_mcp_tool(tool_name, tool_args))
        print(f"🔧 MCP {tool_name}: {result[:150]}")
        return result
    except Exception as e:
        print(f"❌ MCP error: {e}")
        return json.dumps({"error": str(e), "transaction_status": "Error"})

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are SLA Agent, a warm and professional airline assistant for SLA Airlines.\n"
        "If the user provides their name, always address them by name throughout the conversation.\n"
        "Your name is always 'SLA Agent' — never adopt the user's name as your own.\n\n"

        "LANGUAGE RULE:\n"
        "Detect the user's language from their very first message and respond ONLY in that language.\n"
        "Turkish input → Turkish output. English input → English output.\n"
        "NEVER mix languages. NEVER produce Hindi, Chinese, Arabic or any non-Latin characters.\n\n"

        "CITY & AIRPORT CODES:\n"
        "IST=İstanbul, ESB=Ankara, ADB=İzmir, FRA=Frankfurt, AYT=Antalya\n"
        "Always accept city names and convert them yourself. Never ask the user for IATA codes.\n"
        "Write city names correctly: İstanbul (never İstambul), İzmir, Ankara.\n\n"

        "DATE RULE:\n"
        "Current year is 2026. If user gives a date without a year, assume 2026.\n"
        "User messages may contain preprocessed dates like '20 Haziran 2026 (=2026-06-20T00:00:00)'.\n"
        "Always extract and use the ISO value inside the parentheses for tool calls.\n"
        "If user says a range like '20-25 Mayıs', search for the first available date in that range.\n\n"

        "AVAILABLE ROUTES (only these exist):\n"
        "IST↔ESB | IST↔ADB | IST↔FRA | IST↔AYT | ADB↔ESB\n"
        "Ticket availability: May–August 2026.\n"
        "For routes not listed: explain no direct flight, suggest connection via IST, offer to search each leg.\n\n"

        "CONNECTING FLIGHTS:\n"
        "If user requests a route not in the list, break it into legs.\n"
        "Call query_flight separately for each leg. Show only real tool results — never invent times or flight numbers.\n\n"

        "!! CRITICAL TOOL RULES — VIOLATION = SYSTEM FAILURE !!\n"
        "1. You have REAL tools. When you need data, call a tool via the tool_calls API field. "
        "NEVER write the tool name + JSON as plain text in your message. That is NOT a tool call.\n"
        "2. Your reply is ONLY natural language text. Nothing else. No braces. No JSON. No function tags. "
        "No 'query_flight {...}' patterns. No simulated outputs.\n"
        "3. NEVER invent flight numbers, times, or durations. If you haven't received a real tool result, "
        "you don't know. Say so and invoke the proper tool.\n"
        "4. If you want to search flights, the system will invoke query_flight for you automatically. "
        "Just write a natural reply that the user can read (e.g. 'Uçuşları arıyorum, bir saniye'). "
        "Then the tool runs behind the scenes. Do NOT pretend to show results until the tool actually returns.\n"
        "5. If the user asks for an unavailable date, state clearly the flight doesn't exist and offer alternatives. "
        "Do NOT fabricate a flight to fill the gap.\n\n"

        "SEARCH FLOW:\n"
        "1. Collect: departure city, arrival city, date, passenger count.\n"
        "2. Call query_flight immediately once you have all info.\n"
        "3. Show results: flight number, departure time, arrival time, duration.\n\n"

        "BOOKING FLOW — follow this exact order, never skip a step:\n"
        "STEP 1: Inform user of available routes:\n"
        "   'Mayıs–Ağustos 2026 arası şu güzergahlarda biletlerimiz mevcut:\n"
        "   ✈ İstanbul ↔ İzmir  ✈ İstanbul ↔ Ankara  ✈ İstanbul ↔ Frankfurt\n"
        "   ✈ İstanbul ↔ Antalya  ✈ İzmir ↔ Ankara\n"
        "   Hangi güzergahı tercih edersiniz?'\n"
        "STEP 2: Wait for user to pick route. Confirm it.\n"
        "STEP 3: Ask for TRAVEL DATE explicitly. Example: 'Hangi tarihte seyahat etmek istersiniz?'\n"
        "   NEVER assume a date. NEVER invent a date. NEVER skip this step.\n"
        "STEP 4: Ask for passenger count. Example: 'Kaç kişi için bilet almak istersiniz?'\n"
        "STEP 5: Call query_flight with (route + date + passenger count) and show real flights.\n"
        "STEP 6: Let user pick a flight by flight number.\n"
        "STEP 6.5: Once user picks a flight number, DO NOT call query_flight again. "
        "The flight is already chosen. Move directly to asking for passenger names.\n"
        "STEP 7: NOW ask for FULL NAME of each passenger. Never before STEP 6.\n"
        "STEP 8: Call book_flight with the picked flight_number and passenger_names.\n"
        "STEP 9: Show each passenger's name and ticket number clearly.\n"
        "If at any step required information is missing, ASK THE USER — never fabricate.\n\n"

        "CHECK-IN FLOW:\n"
        "1. Get flight number and passenger full name.\n"
        "2. Call check_in tool.\n"
        "3. Show the assigned seat number warmly.\n\n"

        "GENERAL RULES:\n"
        "— Keep responses concise and friendly.\n"
        "— Never ask for info you already have.\n"
        "— Never make up data. If tool returns no results, say so and offer alternatives.\n"
        "— If user already picked a flight number (e.g. 'TK411 uçuşuna bilet'), "
        "never search flights again. Just collect passenger names and call book_flight.\n"
        "— After completing an action, ask if there is anything else you can help with."
    )
}

DATE_KEYWORDS = [
    "hangi tarih", "ne zaman", "seyahat tarihi",
    "which date", "what date", "when do", "travel date"
]

@app.route("/dates", methods=["GET"])
def get_dates():
    airport_from = request.args.get("from", "")
    airport_to   = request.args.get("to", "")
    try:
        resp = httpx.get(
            f"{GATEWAY_URL}/flights/dates",
            params={"airport_from": airport_from, "airport_to": airport_to}
        )
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"dates": [], "error": str(e)})

@app.route("/chat", methods=["POST"])
def chat():
    data     = request.get_json()
    messages = data.get("messages", [])

    messages = preprocess_messages(messages)
    messages = messages[-12:]

    clean_messages = []
    for m in messages:
        role    = m.get("role", "user")
        content = m.get("content") or ""
        if role in ("user", "assistant"):
            clean_messages.append({"role": role, "content": content})

    full_messages = [SYSTEM_PROMPT] + clean_messages

  # If user already picked a flight (TK###) in recent messages,
    # don't allow the model to query_flight again.
    recent_user_text = " ".join([
        m.get("content", "") for m in clean_messages[-4:]
        if m.get("role") == "user"
    ])
    already_picked_flight = bool(re.search(r"TK\d+", recent_user_text, re.IGNORECASE))

    tools_to_use = TOOLS
    if already_picked_flight:
        # Only allow book_flight and check_in, not query_flight
        tools_to_use = [t for t in TOOLS if t["function"]["name"] != "query_flight"]

    try:
        response = groq_create(
            messages=full_messages,
            tools=tools_to_use,
            tool_choice="auto",
            max_tokens=800
        )
    except Exception:
        return jsonify({
            "reply": "⏳ Sistemimiz şu an yoğun. Lütfen birkaç dakika sonra tekrar deneyin.",
            "data": None, "action": None, "route": None
        })

    msg = response.choices[0].message

    if msg.tool_calls:
        tool_call   = msg.tool_calls[0]
        tool_name   = tool_call.function.name
        tool_args   = json.loads(tool_call.function.arguments)

        if "date_from" in tool_args:
            tool_args["date_from"] = normalize_date(tool_args["date_from"])

        tool_result = run_mcp_tool(tool_name, tool_args)

        try:
            tool_data = json.loads(tool_result)
        except json.JSONDecodeError:
            print(f"⚠️ Invalid JSON from MCP: {tool_result}")
            return jsonify({
                "reply": "Bir teknik sorun oluştu, lütfen tekrar deneyin.",
                "data": None, "action": None, "route": None
            })

        full_messages += [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": tool_call.function.arguments
                    }
                }]
            },
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            }
        ]

        strict_instruction = None
        if tool_name == "query_flight":
            flights = tool_data.get("available_flights", [])
            if not flights:
                strict_instruction = (
                    "The query_flight tool returned NO flights for this route/date. "
                    "You MUST tell the user clearly that no flights are available on this date. "
                    "DO NOT invent flight numbers. DO NOT list fake flights. "
                    "Offer to: (1) try another date, (2) search a connecting route via IST. "
                    "If offering connection, you must call query_flight again for each leg — "
                    "never list made-up flight numbers."
                )
            else:
                strict_instruction = (
                    f"The query_flight tool returned {len(flights)} real flights. "
                    "Present ONLY these exact flights. Do not invent any others. "
                    "Use the exact flight numbers from the tool result."
                )
        elif tool_name == "book_flight":
            if tool_data.get("transaction_status") == "Error":
                strict_instruction = (
                    f"Booking FAILED with error: {tool_data.get('message')}. "
                    "Tell the user honestly what went wrong. Do NOT pretend it succeeded. "
                    "If the flight number was invalid, suggest searching again with query_flight."
                )

        if strict_instruction:
            full_messages.append({
                "role": "system",
                "content": strict_instruction
            })

        try:
            final = groq_create(
                messages=full_messages,
                max_tokens=600
            )
            reply = clean_reply(final.choices[0].message.content)
        except Exception:
            reply = "İşlem tamamlandı ancak yanıt oluşturulamadı."

        return jsonify({
            "reply": reply,
            "data": {
                "type": tool_name,
                "args": tool_args,
                "result": tool_data
            },
            "action": None,
            "route": extract_route(messages)
        })

    reply = clean_reply(msg.content)
    needs_date = any(kw in reply.lower() for kw in DATE_KEYWORDS)
    route = extract_route(messages)

    return jsonify({
        "reply": reply,
        "data": None,
        "action": "show_date_picker" if needs_date else None,
        "route": route
    })

if __name__ == "__main__":
    app.run(port=8000, debug=True)
