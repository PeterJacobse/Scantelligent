def put_kwargs_in_dict(dictionary: dict = {}, kwargs_dict: dict[str, tuple[object, object]] = {}) -> None:
    """
    Helper function to put parameters provided as kwargs into a dictionary.
    The kwargs_dict is structured as {parameter_name: (value, allowed types)} (e.g. {"name": passed_name, str}).
    This method works in place.

    Args:
        dictionary (dict, optional): Input dictionary. Defaults to {}.
        kwargs_dict (dict[str, tuple[object, object]], optional): Dictionary of replacements. Defaults to {}.
    """        
    for key, value in kwargs_dict.items():
        if isinstance(value, tuple) and len(value) > 1:
            if isinstance(value[0], value[1]): dictionary.update({key: value[0]})
    return None

def get_parameters_from_tags(parameters: dict, tags: list = [[]]) -> list:
    if len(tags) < 1: return []
    if not isinstance(tags[0], list): tags = [tags]
    if not isinstance(tags[0][0], str):
        print("Invalid tags provided to get_parameters_from_tags")
        return []
    
    output_parameters = []
    for tag_list in tags:
        lowercase_list = [tag.lower() for tag in tag_list]
        parameter_value = next((value for key, value in parameters.items() if key.lower() in lowercase_list), None)
        output_parameters.append(parameter_value)

    return output_parameters