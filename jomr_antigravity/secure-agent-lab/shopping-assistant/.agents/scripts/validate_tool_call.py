import json
import re
import sys


def main():
    try:
        # Read the tool call payload from stdin
        input_data = sys.stdin.read().strip()
        if not input_data:
            print("No tool call data received on stdin.", file=sys.stderr)
            sys.exit(0)  # Allow by default if empty

        try:
            payload = json.loads(input_data)
        except json.JSONDecodeError:
            # Fallback to scanning raw string if it is not valid JSON
            payload = {"CommandLine": input_data}

        # Extract the command line from common payload schemas
        command_line = ""
        if isinstance(payload, dict):
            command_line = payload.get(
                "CommandLine", payload.get("command", payload.get("args", ""))
            )
            if isinstance(command_line, list):
                command_line = " ".join(map(str, command_line))
            elif isinstance(command_line, dict):
                command_line = json.dumps(command_line)
        else:
            command_line = str(payload)

        print(f"Validating command: {command_line}", file=sys.stderr)

        # Destructive command patterns to block
        destructive_patterns = [
            r"rm\s+-rf\s+/",
            r"rm\s+-f\s+-r\s+/",
            r"rm\s+-r\s+-f\s+/",
            r"rmdir\s+/s\s+/q\s+C:\\",
            r"rmdir\s+/s\s+/q\s+c:\\",
        ]

        for pattern in destructive_patterns:
            if re.search(pattern, command_line):
                print(
                    f"SECURITY BLOCK: Destructive command detected ('{command_line}'). Hook blocked execution.",
                    file=sys.stderr,
                )
                sys.exit(1)  # Non-zero exit code blocks the tool execution

        print("Command validation passed.", file=sys.stderr)
        sys.exit(0)  # Exit code 0 allows the tool execution

    except Exception as e:
        print(f"Error validating tool call: {e}", file=sys.stderr)
        sys.exit(1)  # Safe default: block execution if validation crashes


if __name__ == "__main__":
    main()
