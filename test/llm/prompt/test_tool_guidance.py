from zrb.llm.prompt.tool_guidance import get_tool_guidance_prompt


def test_empty_catalogue_returns_empty_string():
    assert get_tool_guidance_prompt(None, {}, []) == ""


def test_empty_groups_returns_empty_string():
    catalogue = {"MyTool": ("Does stuff", "Always do X first.")}
    assert get_tool_guidance_prompt(None, catalogue, []) == ""


def test_all_tools_shown_when_tool_names_is_none():
    catalogue = {
        "ToolA": ("Does A", "Rule for A."),
        "ToolB": ("Does B", None),
    }
    groups = [("My Group", ["ToolA", "ToolB"])]
    result = get_tool_guidance_prompt(None, catalogue, groups)
    assert "ToolA" in result
    assert "Does A" in result
    assert "Rule for A." in result
    assert "ToolB" in result
    assert "Does B" in result


def test_filtering_by_tool_names():
    catalogue = {
        "ToolA": ("Does A", "Rule for A."),
        "ToolB": ("Does B", "Rule for B."),
    }
    groups = [("My Group", ["ToolA", "ToolB"])]
    result = get_tool_guidance_prompt({"ToolA"}, catalogue, groups)
    assert "ToolA" in result
    assert "ToolB" not in result


def test_empty_tool_names_set_returns_empty_string():
    catalogue = {"ToolA": ("Does A", "Rule.")}
    groups = [("Group", ["ToolA"])]
    result = get_tool_guidance_prompt(set(), catalogue, groups)
    assert result == ""


def test_group_omitted_when_no_matching_tools():
    catalogue = {"ToolA": ("Does A", None)}
    groups = [("Group1", ["ToolA"]), ("Group2", ["ToolB"])]
    result = get_tool_guidance_prompt(None, catalogue, groups)
    assert "Group1" in result
    assert "Group2" not in result  # ToolB not in catalogue


def test_key_rule_none_omits_rule_suffix():
    catalogue = {"ToolA": ("Does A", None)}
    groups = [("Group", ["ToolA"])]
    result = get_tool_guidance_prompt(None, catalogue, groups)
    assert "ToolA" in result
    assert "Does A" in result
    assert " — *" not in result


def test_key_rule_present_adds_rule_suffix():
    catalogue = {"ToolA": ("Does A", "Always do X.")}
    groups = [("Group", ["ToolA"])]
    result = get_tool_guidance_prompt(None, catalogue, groups)
    assert "ToolA" in result
    assert "Always do X." in result
    assert "  * " in result  # key_rule indented with asterisk


def test_multiple_groups_rendered_in_order():
    catalogue = {
        "ToolA": ("Does A", None),
        "ToolB": ("Does B", None),
    }
    groups = [("Group1", ["ToolA"]), ("Group2", ["ToolB"])]
    result = get_tool_guidance_prompt(None, catalogue, groups)
    assert result.index("Group1") < result.index("Group2")


def test_tool_in_group_but_missing_from_catalogue_is_skipped():
    catalogue = {"ToolA": ("Does A", None)}
    groups = [("Group", ["ToolA", "Ghost"])]
    result = get_tool_guidance_prompt(None, catalogue, groups)
    assert "ToolA" in result
    assert "Ghost" not in result


def test_header_present_when_entries_exist():
    catalogue = {"ToolA": ("Does A", None)}
    groups = [("Group", ["ToolA"])]
    result = get_tool_guidance_prompt(None, catalogue, groups)
    assert "# Tool Usage Guide" in result


def test_header_absent_when_no_entries_pass_filter():
    catalogue = {"ToolA": ("Does A", None)}
    groups = [("Group", ["ToolA"])]
    result = get_tool_guidance_prompt({"Unrelated"}, catalogue, groups)
    assert result == ""
