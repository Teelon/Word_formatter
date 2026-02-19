
import subprocess
import json
import re

def get_models():
    try:
        # Run lms ls --json
        cmd = ["lms", "ls", "--json"]
        # capture_output=True captures stdout and stderr
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        output = result.stdout
        print(f"Raw output length: {len(output)}")
        
        # Try finding json structures
        # The output might be "Some text [ { JSON } ] some text"
        # Let's find the first '[' and last ']'
        start = output.find('[')
        end = output.rfind(']')
        
        if start != -1 and end != -1:
            json_str = output[start:end+1]
            try:
                models = json.loads(json_str)
                for m in models:
                    print(f"Found model: {m.get('modelKey')} (Type: {m.get('type')})")
            except json.JSONDecodeError:
                print("Failed to decode extracted JSON.")
        else:
            print("No JSON array found in output.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_models()
