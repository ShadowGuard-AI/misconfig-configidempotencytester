import argparse
import hashlib
import logging
import os
import subprocess
import sys
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the misconfig-ConfigIdempotencyTester tool.
    """
    parser = argparse.ArgumentParser(description="Verifies configuration idempotency by applying configurations multiple times and comparing system states.")
    parser.add_argument("config_file", help="Path to the configuration file (YAML or JSON).")
    parser.add_argument("-n", "--num_iterations", type=int, default=2, help="Number of times to apply the configuration. Default is 2.")
    parser.add_argument("-t", "--temp_dir", default=None, help="Optional temporary directory to use. If not provided, a system temp dir is used.")
    parser.add_argument("-c", "--checksum_command", help="Command to calculate system state checksum (e.g., 'find /etc -type f -print0 | sort -z | xargs -0 sha256sum'). Provide full path.", required=True)
    parser.add_argument("-a", "--apply_command", help="Command to apply the configuration. Provide full path and placeholders for the config file.  Example: '/usr/bin/my_config_applier --config {config_file}'", required=True)
    parser.add_argument("-v", "--validate", action="store_true", help="Validate the configuration file before applying it (using yamllint or jsonlint).")

    return parser.parse_args()

def validate_config(config_file):
    """
    Validates the configuration file using yamllint or jsonlint based on the file extension.
    """
    try:
        if config_file.endswith((".yaml", ".yml")):
            result = subprocess.run(["yamllint", config_file], capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"YAML validation failed:\n{result.stderr}")
                return False
        elif config_file.endswith(".json"):
            result = subprocess.run(["jsonlint", "-q", config_file], capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"JSON validation failed:\n{result.stderr}")
                return False
        else:
            logging.warning("Unknown file type. Skipping validation.")
            return True #Allow unknown filetypes to pass validation
        logging.info(f"Configuration file {config_file} validated successfully.")
        return True
    except FileNotFoundError as e:
        logging.error(f"Validation tool not found: {e}")
        return False
    except Exception as e:
        logging.error(f"Error during validation: {e}")
        return False

def calculate_checksum(checksum_command):
    """
    Calculates the system state checksum using the provided command.
    """
    try:
        result = subprocess.run(checksum_command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Checksum command failed:\n{result.stderr}")
            return None
        checksum = result.stdout.strip()
        logging.info(f"Checksum calculated: {checksum}")
        return checksum
    except Exception as e:
        logging.error(f"Error calculating checksum: {e}")
        return None


def apply_configuration(config_file, apply_command):
    """
    Applies the configuration using the provided command.
    Replaces `{config_file}` placeholder in apply_command with the actual config_file path.
    """
    try:
        formatted_command = apply_command.format(config_file=config_file)
        logging.info(f"Applying configuration with command: {formatted_command}")
        result = subprocess.run(formatted_command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Configuration application failed:\n{result.stderr}")
            return False
        logging.info(f"Configuration applied successfully:\n{result.stdout}")
        return True
    except Exception as e:
        logging.error(f"Error applying configuration: {e}")
        return False


def main():
    """
    Main function to execute the configuration idempotency test.
    """
    args = setup_argparse()

    config_file = args.config_file
    num_iterations = args.num_iterations
    checksum_command = args.checksum_command
    apply_command = args.apply_command
    validate = args.validate
    temp_dir = args.temp_dir

    # Input validation
    if not os.path.exists(config_file):
        logging.error(f"Configuration file not found: {config_file}")
        sys.exit(1)

    if num_iterations < 2:
        logging.error("Number of iterations must be at least 2.")
        sys.exit(1)
    
    # Validate config file if requested
    if validate:
        if not validate_config(config_file):
            logging.error("Configuration validation failed. Exiting.")
            sys.exit(1)

    # Prepare temporary directory
    if temp_dir:
      try:
          os.makedirs(temp_dir, exist_ok=True)  # Create temp dir if it doesn't exist.
      except OSError as e:
          logging.error(f"Failed to create temporary directory {temp_dir}: {e}")
          sys.exit(1)
    else:
        temp_dir = tempfile.mkdtemp()  # Creates a temporary directory
        logging.info(f"Using temporary directory: {temp_dir}")
    
    initial_checksum = calculate_checksum(checksum_command)
    if initial_checksum is None:
        logging.error("Failed to calculate initial checksum. Exiting.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        sys.exit(1)
    
    checksums = [initial_checksum]

    for i in range(num_iterations):
        logging.info(f"Iteration {i + 1}: Applying configuration.")
        if not apply_configuration(config_file, apply_command):
            logging.error(f"Iteration {i+1}: Configuration application failed. Exiting.")
            shutil.rmtree(temp_dir, ignore_errors=True)
            sys.exit(1)
        
        current_checksum = calculate_checksum(checksum_command)
        if current_checksum is None:
            logging.error(f"Iteration {i + 1}: Failed to calculate checksum. Exiting.")
            shutil.rmtree(temp_dir, ignore_errors=True)
            sys.exit(1)
        checksums.append(current_checksum)

    idempotent = all(checksum == checksums[0] for checksum in checksums)

    if idempotent:
        logging.info("Configuration is idempotent.  System state remains consistent after multiple applications.")
    else:
        logging.warning("Configuration is NOT idempotent. System state changes after multiple applications.")
        logging.warning(f"Checksums: {checksums}") # Print all checksums for debugging

    shutil.rmtree(temp_dir, ignore_errors=True) # Clean up the temporary directory
    logging.info(f"Temporary directory {temp_dir} cleaned up.")

    if not idempotent:
        sys.exit(1) # Exit with error code if not idempotent

if __name__ == "__main__":
    main()