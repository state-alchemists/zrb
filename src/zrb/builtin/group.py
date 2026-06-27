from zrb.config.config import CFG
from zrb.group.group import Group
from zrb.runner.cli import cli


def _maybe_add_group(group: Group):
    if CFG.LOAD_BUILTIN:
        cli.add_group(group)
    return group


base64_group = _maybe_add_group(
    Group(name="base64", description="📄 Base64 operations")
)
uuid_group = _maybe_add_group(Group(name="uuid", description="🆔 UUID operations"))
uuid_v1_group = uuid_group.add_group(Group(name="v1", description="UUID V1 operations"))
uuid_v3_group = uuid_group.add_group(Group(name="v3", description="UUID V3 operations"))
uuid_v4_group = uuid_group.add_group(Group(name="v4", description="UUID V4 operations"))
uuid_v5_group = uuid_group.add_group(Group(name="v5", description="UUID V5 operations"))
ulid_group = _maybe_add_group(Group(name="ulid", description="🆔 ULID operations"))
jwt_group = _maybe_add_group(Group(name="jwt", description="🔒 JWT encode/decode"))
http_group = _maybe_add_group(
    Group(name="http", description="🌐 HTTP request operations")
)

hash_group = _maybe_add_group(
    Group(name="hash", description="🧩 Hash & HMAC operations")
)
time_group = _maybe_add_group(
    Group(name="time", description="🕒 Time & epoch operations")
)
url_group = _maybe_add_group(
    Group(name="url", description="🔗 URL encode/decode/parse")
)
json_group = _maybe_add_group(Group(name="json", description="📦 JSON operations"))
case_group = _maybe_add_group(
    Group(name="case", description="🔤 String case operations")
)
cron_group = _maybe_add_group(Group(name="cron", description="📅 Cron operations"))
hex_group = _maybe_add_group(Group(name="hex", description="🔣 Hexadecimal operations"))
number_group = _maybe_add_group(
    Group(name="number", description="🔢 Number base operations")
)

random_group = _maybe_add_group(Group(name="random", description="🔀 Random operation"))
git_group = _maybe_add_group(Group(name="git", description="🌱 Git related commands"))
git_branch_group = git_group.add_group(
    Group(name="branch", description="🌿 Git branch related commands")
)
git_subtree_group = git_group.add_group(
    Group(name="subtree", description="🌳 Git subtree related commands")
)
git_changelog_group = git_group.add_group(
    Group(name="changelog", description="📝 Git changelog related commands")
)
llm_group = _maybe_add_group(Group(name="llm", description="🤖 LLM operations"))
md5_group = _maybe_add_group(Group(name="md5", description="🔢 Md5 operations"))
python_group = _maybe_add_group(
    Group(name="python", description="🐍 Python related commands")
)
todo_group = _maybe_add_group(Group(name="todo", description="✅ Todo management"))

shell_group = _maybe_add_group(
    Group(name="shell", description="💬 Shell related commands")
)
shell_autocomplete_group = shell_group.add_group(
    Group(name="autocomplete", description="⌨️ Shell autocomplete related commands")
)

setup_group = _maybe_add_group(Group(name="setup", description="🔧 Setup"))
setup_latex_group = setup_group.add_group(
    Group(name="latex", description="✍️ Setup LaTeX")
)

searxng_group = _maybe_add_group(
    Group(name="searxng", description="🔎 Searxng related command")
)
config_group = _maybe_add_group(Group(name="config", description="⚙️ Configuration"))
