from __future__ import annotations

import asyncio
import platform
import subprocess
from pathlib import Path
from typing import Type

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from config import get_settings


BLOCKED_PATTERNS = (
    "rm -rf /",
    "shutdown",
    "reboot",
    "mkfs",
    "format ",
    ":(){:|:&};:",
)


class TerminalToolInput(BaseModel):
    command: str = Field(..., description="Shell command to execute inside the project root")


class TerminalTool(BaseTool):
    name: str = "terminal"
    description: str = (
        "Execute shell commands inside the project root. Use this for quick inspection, "
        "building, or local commands. Dangerous system-destructive commands are blocked."
    )
    args_schema: Type[BaseModel] = TerminalToolInput
    model_config = ConfigDict(arbitrary_types_allowed=True)
    _root_dir: Path = PrivateAttr()

    def __init__(self, root_dir: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._root_dir = root_dir

    def _run(
        self,
        command: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        lowered = command.lower()
        if any(pattern in lowered for pattern in BLOCKED_PATTERNS):
            return "Blocked: command matches the terminal blacklist."

        settings = get_settings()
        is_windows = platform.system().lower().startswith("win")
        if is_windows:
            # Force PowerShell to emit UTF-8 stdout/stderr instead of the
            # zh-CN system codepage (GBK/CP936). The prelude survives across
            # Out-* calls within the same `-Command` block.
            ps_prelude = (
                "$OutputEncoding = [System.Text.UTF8Encoding]::new();"
                "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new();"
                "$PSDefaultParameterValues['Out-File:Encoding']='utf8';"
                "chcp 65001 > $null;"
            )
            shell_command = ["powershell", "-NoProfile", "-Command", ps_prelude + command]
        else:
            shell_command = ["bash", "-lc", command]
        try:
            completed = subprocess.run(
                shell_command,
                cwd=self._root_dir,
                capture_output=True,
                # On Windows, Python's text=True decodes with the locale codec
                # (GBK), which dies on UTF-8 bytes in non-Chinese content
                # (curly quotes, em-dash, etc.). Read raw bytes and decode
                # manually with errors="replace" to be safe.
                text=False,
                timeout=settings.terminal_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "Timed out after 30 seconds."

        stdout = (completed.stdout or b"").decode("utf-8", errors="replace")
        stderr = (completed.stderr or b"").decode("utf-8", errors="replace")
        combined = (stdout + stderr).strip() or "[no output]"
        return combined[:5000]

    async def _arun(
        self,
        command: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, command, None)
