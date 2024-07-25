import os
import re
import boto3

PROMPTS = {
    "repo_url": {
        "prompt": "Enter the target repository's SSH URL (i.e. ssh://git-codecommit.us-west-2.amazonaws.com/v1/repos/datastore-dr-repo):",
        "default": None,
    },
    "repo_ssh_private_key": {
        "prompt": "Enter an SSH private key that has write permissions to the target repository (i.e. \n-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnN...em9uLmNvbQECAw==\n-----END OPENSSH PRIVATE KEY-----\n)",
        "default": None,
        "multiline": True,
    },
    "cloudwatch_log_group_name": {
        "prompt": "Enter the CloudWatch log group name for your existing application",
        "default": None,
    },
}

def prompt_user_for_multiline(prompt):
    """Prompt the user for a multiline text block."""
    print(prompt + " (Enter multiple lines. End with a blank line):")
    lines = []
    while True:
        line = input()
        if line:
            lines.append(line)
        else:
            break
    return "\n".join(lines) + "\n"

def get_repo_name(repo_url):
    # Define the regular expression to match the repository URL for CodeCommit
    pattern = re.compile(r'^ssh:\/\/git-codecommit\.[a-z0-9-]+\.amazonaws\.com\/v1\/repos\/([a-zA-Z0-9._-]+)$')
    match = pattern.search(repo_url)
    
    if match is None:
        raise ValueError(f"Regex did not match the repo URL: {repo_url}")
    
    # Extract and return the repository name from the regex match
    return match.group(1)

def sanitize_path(path):
    """Sanitize the path to ensure it's compatible with AWS SSM."""
    path = path.replace("\\", "/")
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith("/"):
        path += "/"
    return path

def run(prefix):
    """Prompt the user for variables and secrets which will be stored under an SSM Parameter Store prefix."""
    # Sanitize the prefix
    prefix = sanitize_path(prefix)
    
    # Dictionary to store the responses
    parameters = {}

    # Prompt the user for each value with a default
    for key, prompt_info in PROMPTS.items():
        if prompt_info.get("default"):
            default_text = f" [{prompt_info['default']}]"
        else:
            default_text = ""

        while True:
            if prompt_info.get("multiline"):
                user_input = prompt_user_for_multiline(prompt_info["prompt"])
            else:
                user_input = input(f"{prompt_info['prompt']}{default_text}: ")
            if user_input or prompt_info["default"] is not None:
                parameters[key] = user_input if user_input else prompt_info["default"]
                break

    # Extract the repo name from the repo URL
    repo_name = get_repo_name(parameters["repo_url"])
    parameters["repo_name"] = repo_name
    
    # Store the values in SSM Parameter Store
    ssm = boto3.client("ssm")
    for key, value in parameters.items():
        if not value:
            continue

        parameter_name = f"{prefix}{key}"
        try:
            print(f"Putting parameter {parameter_name}")
            ssm.put_parameter(
                Name=parameter_name,
                Value=value,
                Type="SecureString" if "key" in key else "String",
                Overwrite=True,
            )
        except Exception as e:
            print(f"Failed to put parameter {parameter_name}: {str(e)}")

    return parameters

if __name__ == "__main__":
    try:
        prefix = os.environ["PARAMETER_STORE_PREFIX"]
    except KeyError:
        print(
            "PARAMETER_STORE_PREFIX variable not defined. Export this value and run the command again (i.e. export PARAMETER_STORE_PREFIX=/self-healing-code/)"
        )
        exit(1)

    run(prefix)
