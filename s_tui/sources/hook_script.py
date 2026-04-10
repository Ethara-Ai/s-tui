#!/usr/bin/env python
#
# Copyright (C) 2017-2025 Alex Manuskin, Gil Tsuker
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA

from __future__ import annotations

import os
import subprocess
from typing import Any

from s_tui.sources.hook import Hook


class ScriptHook:
    """
    Runs an arbitrary shell script stored in the filesystem when invoked
    """

    def __init__(self, path: str, timeout_milliseconds: int = 0) -> None:
        self.path = path
        self.hook = self._make_script_hook(path, timeout_milliseconds)

    def is_ready(self) -> bool:
        return self.hook.is_ready()

    def invoke(self) -> None:
        self.hook.invoke()

    def _run_script(self, *args: Any) -> None:
        # Run script in a shell subprocess asynchronously so
        # as to not block main thread (graphs)
        # if the script is a long-running task
        pass

    def _make_script_hook(self, path: str, timeout_milliseconds: int) -> Hook:
        pass
