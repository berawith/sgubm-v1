import os
import ast

def audit_routes(directory):
    missing_auth = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith('.py'):
                continue
                
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
                
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    is_route = False
                    has_auth = False
                    
                    for decorator in node.decorator_list:
                        # Check if it's a route
                        if isinstance(decorator, ast.Call) and hasattr(decorator.func, 'attr') and decorator.func.attr == 'route':
                            is_route = True
                        
                        # Check auth decorators
                        if isinstance(decorator, ast.Name):
                            if decorator.id in ['login_required', 'admin_required', 'jwt_required']:
                                has_auth = True
                        elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                            if decorator.func.id in ['login_required', 'admin_required', 'jwt_required', 'require_permission']:
                                has_auth = True
                    
                    if is_route and not has_auth:
                        missing_auth.append(f"{file} -> {node.name}")

    return missing_auth

if __name__ == '__main__':
    api_dir = 'src/presentation/api'
    print(f"Auditing API routes in {api_dir}...")
    vulnerabilities = audit_routes(api_dir)
    
    if vulnerabilities:
        print("\n⚠️ WARNING: The following routes are missing authentication decorators:")
        for v in vulnerabilities:
            print(f"  - {v}")
    else:
        print("\n✅ All routes have an authentication decorator.")
