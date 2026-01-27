"""Template parameter rendering utilities."""
import re
from typing import Any


def render_template_for_message(
    template_components: list[dict],
    parameters: list[str] | None = None,
) -> str:
    """
    Render a WhatsApp template by replacing placeholders with actual values.

    Combines HEADER, BODY, and FOOTER components into a single message text.
    Replaces {{1}}, {{2}}, etc. placeholders with provided parameters.

    Args:
        template_components: Template components from Meta API (stored in Template.components)
        parameters: List of parameter values in order (0-indexed list for 1-indexed placeholders)
                   e.g., ["John", "New York"] for {{1}} and {{2}}

    Returns:
        Fully rendered message text with all components combined

    Example:
        >>> components = [
        ...     {"type": "HEADER", "format": "TEXT", "text": "Hello {{1}}!"},
        ...     {"type": "BODY", "text": "Welcome to {{2}}. Thanks for joining!"},
        ...     {"type": "FOOTER", "text": "Reply STOP to unsubscribe"}
        ... ]
        >>> render_template_for_message(components, ["John", "NYC"])
        'Hello John!\\n\\nWelcome to NYC. Thanks for joining!\\n\\nReply STOP to unsubscribe'
    """
    parts = []

    for component in template_components:
        component_type = component.get("type", "").upper()

        if component_type == "HEADER":
            # Handle text headers
            if component.get("format") == "TEXT":
                header_text = component.get("text", "")
                if header_text:
                    rendered = _replace_placeholders(header_text, parameters)
                    parts.append(f"*{rendered}*")

        elif component_type == "BODY":
            body_text = component.get("text", "")
            if body_text:
                rendered = _replace_placeholders(body_text, parameters)
                parts.append(rendered)

        elif component_type == "FOOTER":
            footer_text = component.get("text", "")
            if footer_text:
                parts.append(f"_{footer_text}_")  # Footers don't have parameters

        elif component_type == "BUTTONS":
            # Skip buttons - they're interactive elements not part of message text
            pass

    # Join parts with double newline for clear separation
    return "\n\n".join(parts)


def _replace_placeholders(text: str, parameters: list[str] | None) -> str:
    """
    Replace {{1}}, {{2}}, etc. placeholders with actual parameter values.

    WhatsApp uses 1-indexed placeholders, so {{1}} maps to parameters[0].

    Args:
        text: Text containing {{N}} placeholders
        parameters: List of values (0-indexed)

    Returns:
        Text with placeholders replaced, or original placeholders if param missing
    """
    if not parameters:
        return text

    def replacer(match: re.Match) -> str:
        # Get the placeholder number (1-indexed)
        placeholder_num = int(match.group(1))
        # Convert to 0-indexed array access
        param_index = placeholder_num - 1

        # Return parameter value if available, otherwise keep placeholder
        if 0 <= param_index < len(parameters):
            return str(parameters[param_index])
        return match.group(0)  # Keep original {{N}} if no param

    # Find and replace all {{N}} patterns
    return re.sub(r'\{\{(\d+)\}\}', replacer, text)


def extract_template_variables(template_components: list[dict]) -> list[int]:
    """
    Extract all variable placeholder numbers from a template.

    Useful for validation and debugging.

    Args:
        template_components: Template components from Meta API

    Returns:
        Sorted list of placeholder numbers found (e.g., [1, 2, 3])

    Example:
        >>> components = [
        ...     {"type": "HEADER", "format": "TEXT", "text": "Hello {{1}}!"},
        ...     {"type": "BODY", "text": "You have {{2}} items in {{3}}"}
        ... ]
        >>> extract_template_variables(components)
        [1, 2, 3]
    """
    variables = set()

    for component in template_components:
        component_type = component.get("type", "").upper()
        text = None

        if component_type == "HEADER" and component.get("format") == "TEXT":
            text = component.get("text")
        elif component_type == "BODY":
            text = component.get("text")

        if text:
            matches = re.findall(r'\{\{(\d+)\}\}', text)
            variables.update(int(m) for m in matches)

    return sorted(variables)


def count_template_parameters(template_components: list[dict]) -> int:
    """
    Count the number of parameters in a template body component.

    Args:
        template_components: Template components from Meta API

    Returns:
        Number of parameters expected by the template
    """
    for component in template_components:
        if component.get("type") == "BODY":
            # Count {{N}} placeholders in the text
            text = component.get("text", "")
            # Find all {{1}}, {{2}}, etc.
            import re
            matches = re.findall(r'\{\{(\d+)\}\}', text)
            if matches:
                # Return the highest number (template expects 1, 2, 3, ...)
                return max(int(m) for m in matches)
    return 0


def render_template_params(
    variable_mapping: dict[str, str] | None,
    contact_data: dict,
) -> list[dict]:
    """
    Render template parameters by replacing variables with contact data.

    Args:
        variable_mapping: Dict mapping variable indices to contact field names
                         e.g., {"1": "name", "2": "custom_data.city"}
        contact_data: Contact data including name, phone_number, and custom_data

    Returns:
        List of template parameters in Meta API format
        [{"type": "text", "text": "John"}, {"type": "text", "text": "New York"}]

    Raises:
        ValueError: If required contact data is missing
    """
    if not variable_mapping:
        return []

    # Sort by variable index to maintain order
    sorted_vars = sorted(variable_mapping.items(), key=lambda x: int(x[0]))

    params = []
    missing_fields = []

    for var_index, field_path in sorted_vars:
        # Get value from contact data
        value = get_nested_value(contact_data, field_path)

        # Check if value is missing or empty
        if value is None or value == "":
            missing_fields.append(field_path)
            continue

        params.append({
            "type": "text",
            "text": str(value),
        })

    # Raise error if any required fields are missing
    if missing_fields:
        contact_identifier = contact_data.get(
            "phone_number") or contact_data.get("name") or "Unknown"
        raise ValueError(
            f"Contact {contact_identifier} is missing required data: {', '.join(missing_fields)}"
        )

    return params


def get_nested_value(data: dict, field_path: str) -> str | None:
    """
    Get value from nested dict using dot notation.

    Examples:
        - "name" -> data["name"]
        - "custom_data.city" -> data["custom_data"]["city"]

    Args:
        data: Source data dictionary
        field_path: Dot-separated path to the field

    Returns:
        Field value or None if not found
    """
    from typing import Any

    keys = field_path.split(".")
    value: Any = data

    try:
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return None
            else:
                return None
        return value
    except (KeyError, TypeError, AttributeError):
        return None
