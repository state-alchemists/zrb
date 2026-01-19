from prompt_toolkit.styles import Style


def create_style() -> Style:
    return Style.from_dict(
        {
            "frame.label": "bg:#000000 #ffff00",
            "thinking": "ansigreen italic",
            "faint": "#888888",
            "output_field": "bg:#000000 #eeeeee",
            "input_field": "bg:#000000 #eeeeee",
            "text": "#eeeeee",
            "status": "reverse",
            "bottom-toolbar": "bg:#333333 #aaaaaa",
        }
    )
