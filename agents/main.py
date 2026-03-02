import os
import asyncio
from dotenv import load_dotenv

# AutoGen Architecture Imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.anthropic import AnthropicChatCompletionClient

# Import your custom tools
from tool_scripts.linter_tool import run_linter
from tool_scripts.simulator_tool import run_simulation
from tool_scripts.vcd_parser_tool import parse_vcd_to_text

# Import your specialized agents
from agents.reference_model_agent import create_reference_model_agent
from agents.debug_agent import create_debug_agent

# ==========================================
# MODULE 1: File I/O Tools for Agents
# ==========================================
def write_file(filepath: str, content: str) -> str:
    """Allows agents to write code or reports to the disk."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        return f"Success: Wrote file to {filepath}"
    except Exception as e:
        return f"Error writing file: {str(e)}"
# SUMMARY: This function acts as the "hands" for the agents, allowing them to save RTL code, testbenches, and reports to the file system.

def read_file(filepath: str) -> str:
    """Allows agents to read existing files from the disk."""
    try:
        with open(filepath, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"
# SUMMARY: This function allows agents (like the Debug Agent or Supervisor) to ingest existing RTL code, specs, or logs from the file system.

# ==========================================
# MODULE 2: Core Agent Definitions
# ==========================================
def create_supervisor_agent(model_client: AnthropicChatCompletionClient) -> AssistantAgent:
    """
    Creates the Supervisor Agent.
    Role: Analyzes the initial human prompt, sets the verification plan, and delegates tasks.
    """
    supervisor_system_message = """
    You are the Lead VLSI Supervisor.
    Your job is to read the user's initial Design Specification and RTL file.
    
    Process:
    1. Output a high-level Verification Plan.
    2. Instruct the 'Reference_Model_Agent' to build the Python golden model.
    3. Instruct the 'Verification_Agent' to write the testbench and begin linting/simulation.
    Do NOT write the code yourself; delegate to your team.
    """
    return AssistantAgent(
        name="Supervisor_Agent",
        model_client=model_client,
        system_message=supervisor_system_message,
        tools=[read_file]
    )
# SUMMARY: Initializes the Supervisor Agent, which acts as the project manager, reading specs and ordering the other agents to begin their specific tasks.

def create_verification_agent(model_client: AnthropicChatCompletionClient) -> AssistantAgent:
    """
    Creates the Verification Agent.
    Role: Writes Testbenches, runs Linters, runs Simulators, and fixes RTL bugs.
    """
    verification_system_message = """
    You are the Verification & RTL Fixer Agent.
    
    Process:
    1. Wait for the Supervisor to provide the plan.
    2. Write the SystemVerilog Testbench using the `write_file` tool.
    3. Run `run_linter` on the RTL. Fix any syntax errors using `write_file`.
    4. Run `run_simulation`. 
    5. If simulation FAILS: Call the `parse_vcd_to_text` tool to get the waveform, then ask the 'Debug_Agent' to analyze the failure.
    6. Once Debug_Agent provides a fix, rewrite the RTL and simulate again.
    7. If simulation PASSES, reply with exactly "TERMINATE".
    """
    return AssistantAgent(
        name="Verification_Agent",
        model_client=model_client,
        system_message=verification_system_message,
        tools=[write_file, read_file, run_linter, run_simulation, parse_vcd_to_text]
    )
# SUMMARY: Initializes the Verification Agent, which is the "workhorse" of the loop. It holds all the EDA tools, runs simulations, applies code fixes, and determines when the project is successfully finished.

# ==========================================
# MODULE 3: Orchestration & Workflow Setup
# ==========================================
async def main():
    """Main Orchestrator function that initializes the environment and runs the Multi-Agent loop."""
    load_dotenv()
    
    # Setup working directory and dummy inputs for testing
    os.makedirs("work", exist_ok=True)
    initial_spec = "Design a simple ALU that acts as a D-Flip Flop (q <= d on posedge clk)."
    
    # Setup the LLM Client
    model_client = AnthropicChatCompletionClient(
        model="claude-3-5-sonnet-20240620",
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )

    # Instantiate all agents
    supervisor = create_supervisor_agent(model_client)
    ref_model_agent = create_reference_model_agent(model_client)
    verification_agent = create_verification_agent(model_client)
    debug_agent = create_debug_agent(model_client)

    # Define Termination Conditions (Stop on success or after 30 interactions to save tokens)
    termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(30)

    # Create the SelectorGroupChat (The Conference Room)
    # The SelectorGroupChat uses an LLM behind the scenes to decide who should speak next
    # based on the conversation history (e.g., if Sim fails, it knows to route to the Debug Agent).
    team = SelectorGroupChat(
        participants=[supervisor, ref_model_agent, verification_agent, debug_agent],
        model_client=model_client,
        termination_condition=termination,
    )
    
    # The starting prompt from the Human Lead
    human_task = f"""
    HUMAN LEAD INPUT:
    Here is the Design Spec: {initial_spec}
    The initial broken RTL is located at 'work/alu.sv'.
    Supervisor_Agent, please review this and kick off the verification process!
    """
    
    print("==================================================")
    print("Starting Multi-Agent VLSI Verification Loop...")
    print("==================================================\n")
    
    # Run the team and stream the thought process to the console
    await Console(team.run_stream(task=human_task))
# SUMMARY: The main asynchronous loop that creates the LLM client, instantiates the team of 4 agents, configures the intelligent routing (SelectorGroupChat), and kicks off the process with the human's initial spec.

if __name__ == "__main__":
    asyncio.run(main())