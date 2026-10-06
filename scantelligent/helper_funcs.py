import inspect
from types import UnionType
from typing import Any, List, Union, get_origin



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
        if not isinstance(value, tuple) or len(value) < 2: continue
        if isinstance(value[1], UnionType) or get_origin(value[1]) is Union or inspect.isclass(value[1]):
            if isinstance(value[0], value[1]): dictionary.update({key: value[0]})
    return

def get_parameters_from_tags(parameters: dict[str, object], tags: Union[List[str], List[List[str]]] | None = None) -> List[Any]:
    """
    Extracts values from a dictionary using prioritized or grouped tags.
    Handles case-insensitive keys instantly.
    """
    output_parameters = []
    if tags is None: return output_parameters

    if tags and isinstance(tags[0], str): tag_groups: List[List[str]] = [tags]  # type: ignore
    else: tag_groups = tags  # type: ignore

    lowercase_params = {key.lower(): value for key, value in parameters.items()}

    for group in tag_groups:
        if not group: continue
        
        matched_value = next((lowercase_params[tag.lower()] for tag in group if tag.lower() in lowercase_params), None)
        output_parameters.append(matched_value)

    return output_parameters
