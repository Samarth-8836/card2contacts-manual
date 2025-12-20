import os

# Configuration: Folders and files to exclude
IGNORED_DIRS = {'.git', 'node_modules', '__pycache__', '.idea', '.vscode'}
IGNORED_FILES = {'.gitignore', '.DS_Store', 'aggregated_filecontents.txt', 'package-lock.json', 'yarn.lock', 'aggregator.py'}

# Extensions usually considered binary/non-text to skip content printing
BINARY_EXTENSIONS = {'.ico', '.png', '.jpg', '.jpeg', '.gif', '.exe', '.bin', '.pyc', '.zip', '.tar', '.gz', '.svg'}

OUTPUT_FILE = 'aggregated_filecontents.txt'

def is_text_file(file_path):
    """
    Check if a file is a text file. 
    1. Checks extension.
    2. Tries to read the first few bytes to check for null bytes.
    """
    _, ext = os.path.splitext(file_path)
    if ext.lower() in BINARY_EXTENSIONS:
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)
            return True
    except (UnicodeDecodeError,  IOError):
        return False

def generate_tree(startpath):
    """
    Generates a string representation of the file tree structure.
    """
    tree_str = f"{os.path.basename(os.path.abspath(startpath))}/\n"
    
    for root, dirs, files in os.walk(startpath):
        # Filter directories in-place to prevent os.walk from entering them
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = '│  ' * (level - 1) + '├─ ' if level > 0 else ''
        
        if level > 0:
            tree_str += f"{indent}{os.path.basename(root)}/\n"
            
        sub_indent = '│  ' * level + '├─ '
        
        for f in files:
            if f in IGNORED_FILES:
                continue
            tree_str += f"{sub_indent}{f}\n"
            
    return tree_str

def aggregate_files(startpath):
    """
    Walks the directory, reads files, and aggregates them into one output file.
    """
    # 1. Generate the Tree Structure first
    print("Generating tree structure...")
    tree_content = generate_tree(startpath)
    
    final_output = []
    final_output.append("="*50)
    final_output.append("PROJECT STRUCTURE")
    final_output.append("="*50)
    final_output.append(tree_content)
    final_output.append("\n" + "="*50)
    final_output.append("FILE CONTENTS")
    final_output.append("="*50 + "\n")

    # 2. Walk through files for content
    print("Reading file contents...")
    for root, dirs, files in os.walk(startpath):
        # Remove ignored directories from traversal
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        
        for file in files:
            if file in IGNORED_FILES:
                continue
                
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, startpath)
            
            # Check if text file before reading
            if is_text_file(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    final_output.append(f"START OF FILE: {relative_path}")
                    final_output.append("-" * 20)
                    final_output.append(content)
                    final_output.append("-" * 20)
                    final_output.append(f"END OF FILE: {relative_path}\n\n")
                    
                except Exception as e:
                    print(f"Skipping {relative_path}: {e}")
            else:
                final_output.append(f"START OF FILE: {relative_path}")
                final_output.append("[Binary or Non-text file excluded]")
                final_output.append(f"END OF FILE: {relative_path}\n\n")

    # 3. Write to the single output file
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(final_output))
        print(f"Success! All contents aggregated into '{OUTPUT_FILE}'")
    except IOError as e:
        print(f"Error writing output file: {e}")

if __name__ == "__main__":
    # Run in the current directory
    current_dir = os.getcwd()
    aggregate_files(current_dir)