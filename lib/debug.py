def dump_object(obj, indent=0, seen=None):
    """Recursively dump an object's structure and content."""
    if seen is None:
        seen = set()
    
    # Avoid circular references
    obj_id = id(obj)
    if obj_id in seen:
        return " " * indent + "<circular reference>\n"
    seen.add(obj_id)
    
    output = ""
    
    if hasattr(obj, '__dict__'):
        # It's an object with attributes
        for attr in dir(obj):
            # Skip private attributes and methods
            if attr.startswith('_'):
                continue
            try:
                value = getattr(obj, attr)
                # Skip methods and callables
                if callable(value):
                    continue
                output += " " * indent + f"{attr}: "
                if hasattr(value, '__dict__') or isinstance(value, (list, dict)):
                    output += "\n" + dump_object(value, indent + 2, seen)
                else:
                    output += f"{value}\n"
            except Exception as e:
                output += f" <error accessing: {str(e)}>\n"
    elif isinstance(obj, (list, tuple)):
        # It's a list or tuple
        for i, item in enumerate(obj):
            output += " " * indent + f"[{i}]: "
            if hasattr(item, '__dict__') or isinstance(item, (list, dict)):
                output += "\n" + dump_object(item, indent + 2, seen)
            else:
                output += f"{item}\n"
    elif isinstance(obj, dict):
        # It's a dictionary
        for key, value in obj.items():
            output += " " * indent + f"{key}: "
            if hasattr(value, '__dict__') or isinstance(value, (list, dict)):
                output += "\n" + dump_object(value, indent + 2, seen)
            else:
                output += f"{value}\n"
    else:
        output += " " * indent + str(obj) + "\n"
    
    seen.remove(obj_id)
    return output
