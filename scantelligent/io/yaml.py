import yaml as pyyaml



def save(data: object, path: str = "") -> bool:
    try:
        with open(path, "w") as file:
            pyyaml.safe_dump(data, file)
        return True
    except Exception as e:
        print(f"Error saving data to YAML: {e}")
        return False

def load(path: str = "") -> object:
    try:
        with open(path, "r") as file:
            yaml_data = pyyaml.safe_load(file)
    except FileNotFoundError:
        print(f"No file found at {path}")
    except Exception as e:
        print(f"Error retrieving data from YAML file: {e}")
    return yaml_data
