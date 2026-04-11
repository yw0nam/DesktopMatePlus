"""Tests for ToolRegistry and builtin tool wrappers."""

from src.services.agent_service.tools.registry import ToolRegistry


class TestToolRegistryEmpty:
    def test_returns_empty_list_when_no_config(self):
        registry = ToolRegistry(tool_config=None)
        assert registry.get_enabled_tools() == []

    def test_returns_empty_list_when_builtin_missing(self):
        registry = ToolRegistry(tool_config={})
        assert registry.get_enabled_tools() == []

    def test_returns_empty_list_when_all_disabled(self):
        config = {
            "builtin": {
                "filesystem": {"enabled": False, "root_dir": "/tmp"},
                "shell": {"enabled": False, "allowed_commands": ["ls"]},
                "web_search": {"enabled": False},
            }
        }
        registry = ToolRegistry(tool_config=config)
        assert registry.get_enabled_tools() == []


class TestToolRegistryFilesystem:
    def test_returns_filesystem_tools_when_enabled(self):
        config = {
            "builtin": {
                "filesystem": {"enabled": True, "root_dir": "/tmp/agent-workspace"},
            }
        }
        registry = ToolRegistry(tool_config=config)
        tools = registry.get_enabled_tools()
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert any("file" in n or "directory" in n or "list" in n for n in tool_names)

    def test_filesystem_disabled_returns_empty(self):
        config = {
            "builtin": {
                "filesystem": {"enabled": False, "root_dir": "/tmp"},
            }
        }
        registry = ToolRegistry(tool_config=config)
        assert registry.get_enabled_tools() == []


class TestToolRegistryShell:
    def test_returns_shell_tool_when_enabled(self):
        config = {
            "builtin": {
                "shell": {
                    "enabled": True,
                    "allowed_commands": ["ls", "cat"],
                },
            }
        }
        registry = ToolRegistry(tool_config=config)
        tools = registry.get_enabled_tools()
        assert len(tools) == 1
        assert tools[0].name == "terminal"

    def test_shell_tool_blocks_disallowed_command(self):
        config = {
            "builtin": {
                "shell": {
                    "enabled": True,
                    "allowed_commands": ["ls"],
                },
            }
        }
        registry = ToolRegistry(tool_config=config)
        tools = registry.get_enabled_tools()
        shell_tool = tools[0]
        result = shell_tool._run("rm -rf /")
        assert "not allowed" in result.lower()

    def test_shell_tool_allows_whitelisted_command(self):
        config = {
            "builtin": {
                "shell": {
                    "enabled": True,
                    "allowed_commands": ["echo"],
                },
            }
        }
        registry = ToolRegistry(tool_config=config)
        tools = registry.get_enabled_tools()
        shell_tool = tools[0]
        result = shell_tool._run("echo hello")
        assert "hello" in result

    def test_shell_disabled_returns_empty(self):
        config = {
            "builtin": {
                "shell": {"enabled": False, "allowed_commands": ["ls"]},
            }
        }
        registry = ToolRegistry(tool_config=config)
        assert registry.get_enabled_tools() == []


class TestToolRegistryWebSearch:
    def test_returns_search_tool_when_enabled(self):
        config = {
            "builtin": {
                "web_search": {"enabled": True},
            }
        }
        registry = ToolRegistry(tool_config=config)
        tools = registry.get_enabled_tools()
        assert len(tools) == 1
        assert tools[0].name == "duckduckgo_search"

    def test_web_search_disabled_returns_empty(self):
        config = {
            "builtin": {
                "web_search": {"enabled": False},
            }
        }
        registry = ToolRegistry(tool_config=config)
        assert registry.get_enabled_tools() == []


class TestToolRegistryMultiple:
    def test_combines_all_enabled_tools(self):
        config = {
            "builtin": {
                "filesystem": {"enabled": True, "root_dir": "/tmp"},
                "shell": {"enabled": True, "allowed_commands": ["ls"]},
                "web_search": {"enabled": True},
            }
        }
        registry = ToolRegistry(tool_config=config)
        tools = registry.get_enabled_tools()
        # filesystem gives multiple tools, shell gives 1, web_search gives 1
        assert len(tools) >= 3
        tool_names = [t.name for t in tools]
        assert "terminal" in tool_names
        assert "duckduckgo_search" in tool_names
