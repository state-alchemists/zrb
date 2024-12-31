import re


def get_os_from_user_agent(user_agent: str) -> str:
    os_patterns = [
        (r"Windows NT (\d+\.\d+)", "Windows"),
        (r"Mac OS X (\d+[_\.]\d+)", "MacOS"),
        (r"Android (\d+[\.\d]*)", "Android"),
        (r"iPhone OS (\d+[_\.]\d+)", "iOS"),
        (r"iPad.*OS (\d+[_\.]\d+)", "iPadOS"),
        (r"Linux", "Linux"),
    ]
    os = "Unknown OS"
    # Match OS
    for pattern, name in os_patterns:
        match = re.search(pattern, user_agent)
        if match:
            os = (
                f"{name} {match.group(1).replace('_', '.')}" if match.groups() else name
            )
            break
    return os


def get_browser_from_user_agent(user_agent: str) -> str:
    browser_patterns = [
        (r"Chrome/([\d\.]+)", "Chrome"),
        (r"Firefox/([\d\.]+)", "Firefox"),
        (r"Edg/([\d\.]+)", "Edge"),
        (r"Safari/([\d\.]+)", "Safari"),
    ]
    browser = "Unknown Browser"
    # Match Browser
    for pattern, name in browser_patterns:
        match = re.search(pattern, user_agent)
        if match:
            browser = f"{name} {match.group(1)}"
            break
    return browser


def get_device_from_user_agent(user_agent: str):
    device_patterns = [
        (r"iPhone", "iPhone"),
        (r"iPad", "iPad"),
        (r"Android.*Mobile", "Android Phone"),
        (r"Android", "Android Tablet"),
        (r"Macintosh", "Mac"),
        (r"Windows NT", "Windows PC"),
        (r"Linux", "Linux Device"),
    ]
    device = "Unknown Device"
    # Match Device
    for pattern, name in device_patterns:
        if re.search(pattern, user_agent):
            device = name
            break
    return device
