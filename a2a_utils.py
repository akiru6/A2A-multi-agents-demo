# a2a_utils.py (Verbose Version)
import httpx
import json
import uuid
from typing import Any
from a2a.client import A2AClient
from a2a.types import AgentCard, MessageSendParams, SendMessageRequest
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH


class A2ASimpleClient:
    def __init__(self, default_timeout: float = 300.0, verbose: bool = False):
        self._agent_info_cache: dict[str, Any | None] = {}
        self.default_timeout = default_timeout
        self.verbose = verbose # <-- NEW: Add verbose flag

    async def create_task(self, agent_url: str, message: str) -> str:
        timeout_config = httpx.Timeout(self.default_timeout)
        async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
            agent_card_data = None

            try:
                card_url = agent_url.strip('/') + AGENT_CARD_WELL_KNOWN_PATH
                print(f"   (Client is fetching Agent Card from: {card_url})")
                agent_card_response = await httpx_client.get(card_url)
                agent_card_response.raise_for_status()
                agent_card_data = agent_card_response.json()
                self._agent_info_cache[agent_url] = agent_card_data
            
            except httpx.HTTPStatusError as e:
                return f"❌ HTTP Error from agent server: {e.response.status_code}\n   URL: {e.request.url}"
            except httpx.RequestError as e:
                return f"❌ Network Error trying to contact agent: {e.__class__.__name__}\n   URL: {e.request.url}"

            agent_card = AgentCard(**agent_card_data)
            client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)
            
            request = SendMessageRequest(
                id=str(uuid.uuid4()),
                params=MessageSendParams(
                    message={
                        "messageId": uuid.uuid4().hex,
                        "role": "user",
                        "parts": [{"kind": "text", "text": message}],
                    }
                ),
            )

            # --- NEW: Verbose Logging ---
            if self.verbose:
                print("\n" + "="*20 + " [REQUEST SENT] " + "="*20)
                # Use model_dump for a clean dictionary representation
                print(json.dumps(request.model_dump(mode="json"), indent=2))
                print("="*58 + "\n")

            response = await client.send_message(request)

            # --- NEW: Verbose Logging ---
            response_dict = response.model_dump(mode="json", exclude_none=True)
            if self.verbose:
                print("\n" + "="*20 + " [RAW RESPONSE RECEIVED] " + "="*15)
                print(json.dumps(response_dict, indent=2))
                print("="*58 + "\n")

            # The rest of the parsing logic remains the same
            try:
                if "error" in response_dict:
                    error_info = response_dict["error"]
                    error_message = error_info.get("message", "Unknown error")
                    error_code = error_info.get("code", "N/A")
                    return f"❌ Agent returned an error!\n   Code: {error_code}\n   Message: {error_message}"

                if "result" in response_dict and "artifacts" in response_dict["result"]:
                    full_content = []
                    for artifact in response_dict["result"]["artifacts"]:
                        for part in artifact.get("parts", []):
                            if "text" in part:
                                full_content.append(part["text"])
                    
                    if full_content:
                        return "\n\n".join(full_content)

                return json.dumps(response_dict, indent=2)

            except Exception as e:
                return f"Error parsing response: {e}\nRaw response: {str(response)}"