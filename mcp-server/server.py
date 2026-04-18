from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx
import json
import os

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:5000/api/v1")

server = Server("airline-mcp")

def get_token():
    resp = httpx.post(
        f"{GATEWAY_URL}/login",
        json={"username": "admin", "password": "1234"}
    )
    return resp.json().get("access_token")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_flight",
            description="Search available flights between airports on a given date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_from":        {"type": "string",  "description": "Departure datetime e.g. 2026-05-01T00:00:00"},
                    "airport_from":     {"type": "string",  "description": "IATA departure code e.g. IST"},
                    "airport_to":       {"type": "string",  "description": "IATA arrival code e.g. ESB"},
                    "number_of_people": {"type": "integer", "description": "Number of passengers"}
                },
                "required": ["date_from", "airport_from", "airport_to", "number_of_people"]
            }
        ),
        Tool(
            name="book_flight",
            description="Book flight tickets for one or more passengers.",
            inputSchema={
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
        ),
        Tool(
            name="check_in",
            description="Check in a passenger to their booked flight.",
            inputSchema={
                "type": "object",
                "properties": {
                    "flight_number":  {"type": "string", "description": "Flight number"},
                    "passenger_name": {"type": "string", "description": "Passenger full name"}
                },
                "required": ["flight_number", "passenger_name"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    if name == "query_flight":
        resp = httpx.get(
            f"{GATEWAY_URL}/flights/query",
            params=arguments
        )
    elif name == "book_flight":
        resp = httpx.post(
            f"{GATEWAY_URL}/tickets",
            json=arguments,
            headers=headers
        )
    elif name == "check_in":
        resp = httpx.post(
            f"{GATEWAY_URL}/checkin",
            json=arguments
        )
    else:
        return [TextContent(type="text", text="Unknown tool")]

    result = json.dumps(resp.json(), ensure_ascii=False)
    return [TextContent(type="text", text=result)]

async def main():
    async with stdio_server() as (read, write):
        await server.run(
            read, write,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())