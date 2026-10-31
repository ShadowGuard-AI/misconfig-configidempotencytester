import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import shutil

try:
    import yaml
except ImportError:
    yaml = None


def read_and_check_config(config_file):
    """
    Read the configuration the tool is about to certify. An empty or
    unparseable file gets no verdict: the run exits before any
    application. Returns True only for a file that parsed to content.
    """
    try:
        with open(config_file, "r") as f:
            raw = f.read()
    except OSError as e:
        logging.error(f"Could not read configuration file {config_file}: {e}")
        return False
    if raw.strip() == "":
        logging.error(f"Configuration file {config_file} is empty; no idempotency verdict can be given.")
        return False
    lower = config_file.lower()
    try:
        if lower.endswith(".json"):
            data = json.loads(raw)
        elif lower.endswith((".yaml", ".yml")):
            if yaml is None:
                return True  # Non-empty text; no parser available here.
            data = yaml.safe_load(raw)
        else:
            return True  # Content present; type honesty is validate_config's job.
    except Exception as e:
        logging.error(f"Configuration file {config_file} could not be parsed: {e}")
        return False
    if data is None or data == {} or data == []:
        logging.error(f"Configuration file {config_file} parses to nothing; no idempotency verdict can be given.")
        return False
    return True

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
            logging.error("Unknown file type. Validation cannot check this file, so it does not pass.")
            return False
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
        # Substitute only the one placeholder. Formatting the whole
        # string would break on any other braces in the operator's
        # command (shell, awk, find, and JSON shaped arguments all
        # use braces of their own).
        formatted_command = apply_command.replace("{config_file}", config_file)
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

    # The tool certifies this configuration, so it reads it first.
    if not read_and_check_config(config_file):
        sys.exit(1)

    # Validate config file if requested
    if validate:
        if not validate_config(config_file):
            logging.error("Configuration validation failed. Exiting.")
            sys.exit(1)

    # Prepare temporary directory. Cleanup may only remove a
    # directory this run created with mkdtemp. An operator named
    # directory is never a deletion target, on any exit path: the
    # tool puts nothing in it, and deleting it would remove only the
    # operator's own files.
    created_by_tool = False
    if temp_dir:
      try:
          os.makedirs(temp_dir, exist_ok=True)
      except OSError as e:
          logging.error(f"Failed to create temporary directory {temp_dir}: {e}")
          sys.exit(1)
    else:
        temp_dir = tempfile.mkdtemp()
        created_by_tool = True
        logging.info(f"Using temporary directory: {temp_dir}")

    def cleanup_temp_dir():
        if created_by_tool:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logging.info(f"Temporary directory {temp_dir} cleaned up.")
        else:
            logging.info(f"Temporary directory {temp_dir} was named by the operator and is left in place.")

    initial_checksum = calculate_checksum(checksum_command)
    if initial_checksum is None:
        logging.error("Failed to calculate initial checksum. Exiting.")
        cleanup_temp_dir()
        sys.exit(1)
    
    # The pre-application checksum is recorded for the log only. It
    # is not part of the verdict: a first application that does its
    # job is supposed to change the state.
    checksums = []

    for i in range(num_iterations):
        logging.info(f"Iteration {i + 1}: Applying configuration.")
        if not apply_configuration(config_file, apply_command):
            logging.error(f"Iteration {i+1}: Configuration application failed. Exiting.")
            cleanup_temp_dir()
            sys.exit(1)
        
        current_checksum = calculate_checksum(checksum_command)
        if current_checksum is None:
            logging.error(f"Iteration {i + 1}: Failed to calculate checksum. Exiting.")
            cleanup_temp_dir()
            sys.exit(1)
        checksums.append(current_checksum)

    # Idempotent means the post-application checksums agree with
    # each other: after the first application, applying again
    # changes nothing.
    if checksums and checksums[0] != initial_checksum:
        logging.info("The first application changed the system state, as an application may. The verdict compares the post-application checksums with each other.")
    idempotent = len(checksums) >= 2 and all(checksum == checksums[0] for checksum in checksums)

    if idempotent:
        logging.info("Configuration is idempotent.  System state remains consistent after multiple applications.")
    else:
        logging.warning("Configuration is NOT idempotent. System state changes after multiple applications.")
        logging.warning(f"Checksums: {checksums}") # Print all checksums for debugging

    cleanup_temp_dir()

    if not idempotent:
        sys.exit(1) # Exit with error code if not idempotent

if __name__ == "__main__":
    main()