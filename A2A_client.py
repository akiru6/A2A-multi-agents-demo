# A2A_client.py (Verbose Version)
import asyncio
import os
import sys # <-- NEW: Import sys to read command-line arguments
from a2a_utils import A2ASimpleClient

# --- Configuration ---
DLAI_LOCAL_URL = os.getenv("DLAI_LOCAL_URL", "http://127.0.0.1:{port}/")
ORCHESTRATOR_PORT = 10030
ORCHESTRATOR_URL = DLAI_LOCAL_URL.format(port=ORCHESTRATOR_PORT)


async def run_client():
    # --- NEW: Check for --verbose flag ---
    is_verbose = "--verbose" in sys.argv
    
    print("==================================================")
    print("    🚀 A2A Interactive Client Initialized 🚀")
    print(f"   Connecting to Orchestrator at {ORCHESTRATOR_URL}")
    if is_verbose:
        print("   (Verbose mode enabled)")
    print("==================================================")
    print("You can now enter prompts to interact with the agent system.")
    print("Type 'quit' or 'exit' to close the client.\n")

    # Pass the verbose flag to the client
    a2a_client = A2ASimpleClient(verbose=is_verbose)

    while True:
        try:
            user_prompt = input("▶️  Enter your prompt: ")

            if user_prompt.lower() in ["quit", "exit"]:
                print("👋  Exiting client. Goodbye!")
                break

            if not user_prompt:
                continue

            print("--------------------------------------------------")
            print(f"💬  Sending prompt to Orchestrator: '{user_prompt}'") # More descriptive
            print("⏳  Waiting for the multi-agent system to respond...")

            response = await a2a_client.create_task(
                agent_url=ORCHESTRATOR_URL,
                message=user_prompt
            )

            print("\n✅  Orchestrator responded!")
            print("----------------- [FINAL ANSWER] -----------------")
            print(response)
            print("--------------------------------------------------\n")

        except KeyboardInterrupt:
            print("\n👋  Exiting client. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            print("   Is the A2A_github_demo_simplified.py script still running?")
            break


if __name__ == "__main__":
    asyncio.run(run_client())