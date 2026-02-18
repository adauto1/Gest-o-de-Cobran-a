import os

def update_references(directory, old_strs, new_str):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith((".py", ".html")):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    changed = False
                    new_content = content
                    for old_str in old_strs:
                        if old_str in new_content:
                            new_content = new_content.replace(old_str, new_str)
                            changed = True
                    
                    if changed:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        print(f"Updated: {path}")
                except Exception as e:
                    print(f"Error processing {path}: {e}")

if __name__ == "__main__":
    variants = ["app.core.utils", ".core.utils", "core.utils", "app.core.helpers", ".core.helpers"]
    # Actually, if I rename app.core.utils to app.core.helpers, then variants of that string
    # like 'from .core.utils' would become 'from .core.helpers' if I replace '.core.utils' with '.core.helpers'
    
    # Let's do a simple replace of 'utils' to 'helpers' in the context of 'core.utils'
    update_references("app", ["core.utils"], "core.helpers")
    print("Core references updated.")
