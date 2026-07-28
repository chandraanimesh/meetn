import os
import re

for root, _, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            # match: AppError(code="error", message="Session expired", status_code=401)
            # to: AppError(code="auth_error", message="Session expired", status_code=401)
            new_content = re.sub(
                r'AppError\(status_code=(\d+),\s*detail=f?\"([^\"]+)\"\)',
                r'AppError(code="error", message="\2", status_code=\1)',
                content
            )
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f'Updated {path}')
