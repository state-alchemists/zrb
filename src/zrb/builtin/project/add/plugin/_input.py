import os

from zrb.helper.accessories.name import get_random_name
from zrb.task_input.str_input import StrInput

SYSTEM_USER = os.getenv("USER", "incognito")

package_name_input = StrInput(
    name="package-name",
    shortcut="p",
    description="Package name",
    prompt="Package name",
    default=get_random_name(),
)

package_description_input = StrInput(
    name="package-description",
    description="Package description",
    prompt="Package description",
    default="Just another package",
)

package_homepage_input = StrInput(
    name="package-homepage",
    description="Package homepage",
    prompt="Package homepage",
    default="".join(
        [
            "https://github.com/",
            SYSTEM_USER,
            "/{{util.to_kebab_case(input.package_name)}}",
        ]
    ),
)

package_repository_input = StrInput(
    name="package-repository",
    description="Package repository",
    prompt="Package repository",
    default="".join(
        [
            "https://github.com/",
            SYSTEM_USER,
            "/{{util.to_kebab_case(input.package_name)}}",
        ]
    ),
)

package_documentation_input = StrInput(
    name="package-documentation",
    description="Package documentation",
    prompt="Package documentation",
    default="".join(
        [
            "https://github.com/",
            SYSTEM_USER,
            "/{{util.to_kebab_case(input.package_name)}}",
        ]
    ),
)

package_author_name_input = StrInput(
    name="package-author-name",
    prompt="Package author name",
    description="Package author name",
    default=SYSTEM_USER,
)

package_author_email_input = StrInput(
    name="package-author-email",
    prompt="Package author email",
    description="Package author email",
    default=f"{SYSTEM_USER}@gmail.com",
)
