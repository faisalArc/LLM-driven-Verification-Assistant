import subprocess
import os

def run_linter(rtl_file: str) -> str:
    """
    Executes the Verilator linter on a given RTL file.
    Captures both standard output (stdout) and standard error (stderr) 
    and returns them as a single string.
    
    Args:
        rtl_file (str): The path to the SystemVerilog or Verilog file (e.g., 'alu.sv').
        
    Returns:
        str: The terminal output from the linter, or an error message.
    """
    # 1. Verify the file actually exists before trying to lint it
    if not os.path.exists(rtl_file):
        return f"Execution Error: The file '{rtl_file}' was not found in the current directory."

    # 2. Define the shell command as a list of arguments
    # This is safer than passing a single string with shell=True
    command = ["verilator", "--lint-only", rtl_file]

    try:
        # 3. Execute the command using subprocess.run
        # capture_output=True: Grabs both stdout and stderr so we can read them.
        # text=True: Automatically decodes the output from bytes to a Python string.
        # check=False: We DON'T want Python to crash if Verilator finds an RTL error 
        # (which returns a non-zero exit code). We want to capture that error!
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False 
        )

        # 4. Combine stdout and stderr. 
        # Note: Verilator typically prints warnings and errors to stderr.
        combined_output = result.stdout + result.stderr

        # 5. Format the output for the LLM based on the return code
        if result.returncode == 0:
            # Exit code 0 means success in Linux/Unix
            return f"Success: No linting errors found in {rtl_file}.\n{combined_output}"
        else:
            # Non-zero exit code means the linter found rule violations or syntax errors
            return f"Linting Failed: Errors detected in {rtl_file}.\n{combined_output}"

    except FileNotFoundError:
        # This exception triggers if the 'verilator' executable is missing from the system PATH
        return "System Error: 'verilator' command not found. Please ensure Verilator is installed on this machine."
    
    except Exception as e:
        # Catch-all for any other unexpected execution issues (e.g., permission denied)
        return f"System Error: An unexpected error occurred while running the linter: {str(e)}"

# ==========================================
# Example usage / Testing the tool locally
# ==========================================
if __name__ == "__main__":
    # To test this locally, create a dummy file named 'alu.sv' 
    # and run this python script directly.
    
    test_file = "alu.sv"
    
    # Optional: Create a temporary broken SV file for testing if it doesn't exist
    if not os.path.exists(test_file):
        with open(test_file, "w") as f:
            f.write("module alu(input clk, input d, output q);\n")
            f.write("  always @(posedge clk) q = d \n") # Missing semicolon and using blocking assignment
            f.write("endmodule\n")
            
    print(f"--- Running Linter on {test_file} ---")
    output = run_linter(test_file)
    print(output)