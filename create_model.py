#!/usr/bin/env python
import subprocess
import os
import argparse
import sys

def generate_pydantic_model_from_json(json_file_path: str, output_python_file: str, class_name: str):
    """
    Generates Pydantic models from a JSON file using datamodel-code-generator.

    This function is memory-efficient and suitable for large JSON files.

    Args:
        json_file_path (str): The full path to the source JSON file.
        output_python_file (str): The name of the Python file to be created,
                                  which will contain the Pydantic models.
        class_name (str): The name for the top-level (root) Pydantic model.
    """
    print(f"Starting model generation from '{json_file_path}'...")

    # Ensure the input file exists before proceeding.
    if not os.path.exists(json_file_path):
        print(f"Error: The input file '{json_file_path}' was not found.", file=sys.stderr)
        sys.exit(1)

    # This command invokes the datamodel-code-generator.
    # --input: Specifies the source JSON file.
    # --output: Defines the file where the generated Python code will be saved.
    # --class-name: Sets the name for the top-level Pydantic model.
    command = [
        "datamodel-codegen",
        "--input", json_file_path,
        "--input-file-type", "json",
        "--output", output_python_file,
        "--class-name", class_name,
    ]

    try:
        # Execute the command to generate the model.
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Successfully generated Pydantic models in '{output_python_file}'.")
    except subprocess.CalledProcessError as e:
        # If the tool returns a non-zero exit code, it indicates an error.
        print("An error occurred during model generation.", file=sys.stderr)
        print("Error details:", e.stderr, file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        # This error occurs if the datamodel-codegen command itself isn't found.
        print("Error: 'datamodel-codegen' command not found.", file=sys.stderr)
        print("Please ensure you have installed it by running:", file=sys.stderr)
        print("pip install \"datamodel-code-generator[pydantic]\"", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    # Set up the command-line argument parser.
    parser = argparse.ArgumentParser(
        description="Automatically generate Pydantic models from a JSON file."
    )

    # Add the 'input_file' argument.
    parser.add_argument(
        "input_file",
        type=str,
        help="The path to the source large JSON file."
    )

    # Add the 'output_file' argument.
    parser.add_argument(
        "output_file",
        type=str,
        help="The path to the destination Python file for the generated models."
    )

    # Add an optional argument for the root class name.
    parser.add_argument(
        "--class-name",
        type=str,
        default="GeneratedModel",
        help="The name for the top-level (root) Pydantic model. Defaults to 'GeneratedModel'."
    )

    # Parse the arguments provided by the user.
    args = parser.parse_args()

    # Call the main function with the parsed arguments.
    generate_pydantic_model_from_json(args.input_file, args.output_file, args.class_name)