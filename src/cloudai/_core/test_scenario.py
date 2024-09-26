# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass, field
from typing import List, Optional

from .test import Test


class TestDependency:
    """
    Represents a dependency for a test.

    Attributes
        test (Test): The test object it depends on.
        time (int): Time in seconds after which this dependency is met.
    """

    __test__ = False

    def __init__(self, test_run: "TestRun", time: int) -> None:
        """
        Initialize a TestDependency instance.

        Args:
            test_run (TestRun): TestRun object it depends on.
            time (int): Time in seconds to meet the dependency.
        """
        self.test_run = test_run
        self.time = time


@dataclass
class TestRun:
    __test__ = False

    name: str
    test: Test
    num_nodes: int
    nodes: List[str]
    iterations: int = 1
    current_iteration: int = 0
    time_limit: Optional[str] = None
    dependencies: dict[str, TestDependency] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(
            self.name
            + self.test.name
            + str(self.num_nodes)
            + str(self.nodes)
            + str(self.iterations)
            + str(self.time_limit)
        )

    def has_more_iterations(self) -> bool:
        """
        Check if the test has more iterations to run.

        Returns
            bool: True if more iterations are pending, False otherwise.
        """
        return self.current_iteration < self.iterations


class TestScenario:
    """
    Represents a test scenario, comprising a set of tests.

    Attributes
        name (str): Unique name of the test scenario.
        tests (List[Test]): Tests in the scenario.
        job_status_check (bool): Flag indicating whether to check the job status or not.
    """

    __test__ = False

    def __init__(self, name: str, test_runs: List[TestRun], job_status_check: bool = True) -> None:
        """
        Initialize a TestScenario instance.

        Args:
            name (str): Name of the test scenario.
            test_runs (List[TestRun]): List of tests in the scenario with custom run options.
            job_status_check (bool): Flag indicating whether to check the job status or not.
        """
        self.name = name
        self.test_runs = test_runs
        self.job_status_check = job_status_check

    def __repr__(self) -> str:
        """
        Return a string representation of the TestScenario instance.

        Returns
            str: String representation of the test scenario.
        """
        test_names = ", ".join([tr.test.name for tr in self.test_runs])
        return f"TestScenario(name={self.name}, tests=[{test_names}])"

    def pretty_print(self) -> str:
        """Print each test in the scenario along with its section name, description, and visualized dependencies."""
        s = f"Test Scenario: {self.name}\n"
        for tr in self.test_runs:
            s += f"\nSection Name: {tr.name}\n"
            s += f"  Test Name: {tr.test.name}\n"
            s += f"  Description: {tr.test.description}\n"
            if tr.dependencies:
                for dep_type, dependency in tr.dependencies.items():
                    if dependency:
                        s += (
                            f"  {dep_type.replace('_', ' ').title()}: {dependency.test_run.name}, "
                            f"Time: {dependency.time} seconds"
                        )
            else:
                s += "  No dependencies"
        return s
