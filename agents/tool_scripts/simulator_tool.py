import subprocess
import os

def run_simulation(tb_file: str, rtl_file: str) -> str:
    """
    Compiles and simulates a SystemVerilog/Verilog testbench and RTL file.
    Captures the simulation logs (stdout/stderr) to return to the LLM.
    
    Args:
        tb_file (str): Path to the testbench file (e.g., 'tb_alu.sv').
        rtl_file (str): Path to the RTL design file (e.g., 'alu.sv').
        
    Returns:
        str: The compilation and simulation log, or an error message.
    """
    if not os.path.exists(tb_file):
        return f"Execution Error: Testbench file '{tb_file}' not found."
    if not os.path.exists(rtl_file):
        return f"Execution Error: RTL file '{rtl_file}' not found."

    # --- Step 1: Compilation ---
    # Defaulting to Icarus Verilog (iverilog). 
    # If using VCS, change this to: command_compile = ["vcs", "-sverilog", rtl_file, tb_file]
    # If using ModelSim, change to: command_compile = ["vlog", rtl_file, tb_file]
    compiled_out = "sim.out"
    command_compile = ["iverilog", "-g2012", "-o", compiled_out, tb_file, rtl_file]

    try:
        compile_result = subprocess.run(
            command_compile, capture_output=True, text=True, check=False
        )
        
        if compile_result.returncode != 0:
            return f"Compilation Failed:\n{compile_result.stdout}\n{compile_result.stderr}"

    except FileNotFoundError:
        return "System Error: 'iverilog' compiler not found. Please check your EDA tool installation."
    except Exception as e:
        return f"System Error during compilation: {str(e)}"

    # --- Step 2: Simulation ---
    # Defaulting to Icarus Verilog runtime (vvp).
    # If using VCS, change this to: command_sim = ["./simv"]
    # If using ModelSim, change to: command_sim = ["vsim", "-c", "-do", "run -all; quit", "work.tb_top"]
    command_sim = ["vvp", compiled_out]

    try:
        sim_result = subprocess.run(
            command_sim, capture_output=True, text=True, check=False
        )
        
        # Combine the output and errors
        sim_logs = sim_result.stdout + sim_result.stderr
        
        # Clean up the compiled binary (optional)
        if os.path.exists(compiled_out):
            os.remove(compiled_out)

        return f"Simulation Completed Successfully.\nLogs:\n{sim_logs}"

    except Exception as e:
        return f"System Error during simulation execution: {str(e)}"

# ==========================================
# Example usage / Testing the tool locally
# ==========================================
if __name__ == "__main__":
    # To test this, you would need a dummy ALU and a dummy Testbench
    print("Testing Simulator Tool...")
    # output = run_simulation("work/tb_alu.sv", "work/alu.sv")
    # print(output)