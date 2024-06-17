# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
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

import logging
import os
import shutil
import subprocess
import tempfile


class PrerequisiteCheckResult:
    """
    Class representing the result of a prerequisite check.

    Attributes
        success (bool): Indicates whether the prerequisite check was successful.
        message (str): A message providing additional information about the result.
    """

    def __init__(self, success: bool, message: str = "") -> None:
        """
        Initialize the PrerequisiteCheckResult.

        Args:
            success (bool): Indicates whether the prerequisite check was successful.
            message (str): A message providing additional information about the result.
        """
        self.success = success
        self.message = message

    def __bool__(self):
        """
        Return the success status as a boolean.

        Returns
            bool: True if the check was successful, False otherwise.
        """
        return self.success

    def __str__(self):
        """
        Return the message as a string.

        Returns
            str: The message providing additional information about the result.
        """
        return self.message


class DockerImageCacheResult:
    """
    Class representing the result of a Docker image caching operation.

    Attributes
        success (bool): Indicates whether the operation was successful.
        docker_image_path (str): The path to the Docker image.
        message (str): A message providing additional information about the result.
    """

    def __init__(self, success: bool, docker_image_path: str = "", message: str = "") -> None:
        """
        Initialize the DockerImageCacheResult.

        Args:
            success (bool): Indicates whether the operation was successful.
            docker_image_path (str): The path to the Docker image.
            message (str): A message providing additional information about the result.
        """
        self.success = success
        self.docker_image_path = docker_image_path
        self.message = message

    def __bool__(self):
        """
        Return the success status as a boolean.

        Returns
            bool: True if the operation was successful, False otherwise.
        """
        return self.success

    def __str__(self):
        """
        Return the message as a string.

        Returns
            str: The message providing additional information about the result.
        """
        return self.message


class DockerImageCacheManager:
    """
    Manages the caching of Docker images for installation strategies.

    Attributes
        install_path (str): The base installation path.
        cache_docker_images_locally (bool): Whether to cache Docker image files locally.
        partition_name (str): The partition name to use in the srun command.
    """

    def __init__(self, install_path: str, cache_docker_images_locally: bool, partition_name: str) -> None:
        self.install_path = install_path
        self.cache_docker_images_locally = cache_docker_images_locally
        self.partition_name = partition_name

    def ensure_docker_image(
        self, docker_image_url: str, subdir_name: str, docker_image_filename: str
    ) -> DockerImageCacheResult:
        """
        Ensure the Docker image exists by checking and optionally caching it.

        Args:
            docker_image_url (str): URL or file path of the Docker image.
            subdir_name (str): Subdirectory name within the installation path.
            docker_image_filename (str): Docker image filename.

        Returns:
            DockerImageCacheResult: Result of ensuring the Docker image exists.
        """
        image_check_result = self.check_docker_image_exists(docker_image_url, subdir_name, docker_image_filename)
        if image_check_result.success:
            return image_check_result

        if self.cache_docker_images_locally:
            return self.cache_docker_image(docker_image_url, subdir_name, docker_image_filename)

        return image_check_result

    def check_docker_image_exists(
        self, docker_image_url: str, subdir_name: str, docker_image_filename: str
    ) -> DockerImageCacheResult:
        """
        Check if the Docker image exists without caching it.

        Args:
            docker_image_url (str): URL or file path of the Docker image.
            subdir_name (str): Subdirectory name within the installation path.
            docker_image_filename (str): Docker image filename.

        Returns:
            DockerImageCacheResult: Result of the Docker image existence check.
        """
        logging.debug(
            f"Checking if Docker image exists: {docker_image_url=}, {subdir_name=}, {docker_image_filename=} "
            f"{self.cache_docker_images_locally=}"
        )

        # If not caching locally, check URL accessibility
        if not self.cache_docker_images_locally:
            accessibility_check = self._check_docker_image_accessibility(docker_image_url)
            if accessibility_check.success:
                return DockerImageCacheResult(True, docker_image_url, accessibility_check.message)
            return DockerImageCacheResult(False, "", accessibility_check.message)

        # Check if docker_image_url is a file path and exists
        if os.path.isfile(docker_image_url) and os.path.exists(docker_image_url):
            return DockerImageCacheResult(True, docker_image_url, "Docker image file path is valid.")

        # Check if the cache file exists
        if not os.path.exists(self.install_path):
            return DockerImageCacheResult(False, "", f"Install path {self.install_path} does not exist.")

        subdir_path = os.path.join(self.install_path, subdir_name)
        if not os.path.exists(subdir_path):
            return DockerImageCacheResult(False, "", f"Subdirectory path {subdir_path} does not exist.")

        docker_image_path = os.path.join(subdir_path, docker_image_filename)
        if os.path.isfile(docker_image_path) and os.path.exists(docker_image_path):
            return DockerImageCacheResult(True, docker_image_path, "Cached Docker image already exists.")

        return DockerImageCacheResult(
            False, "", f"Docker image does not exist at the specified path: {docker_image_path}."
        )

    def cache_docker_image(
        self, docker_image_url: str, subdir_name: str, docker_image_filename: str
    ) -> DockerImageCacheResult:
        """
        Cache the Docker image locally using enroot import.

        Args:
            docker_image_url (str): URL of the Docker image.
            subdir_name (str): Subdirectory name within the installation path.
            docker_image_filename (str): Docker image filename.

        Returns:
            DockerImageCacheResult: Result of the Docker image caching operation.
        """
        subdir_path = os.path.join(self.install_path, subdir_name)
        docker_image_path = os.path.join(subdir_path, docker_image_filename)

        if os.path.isfile(docker_image_path):
            return DockerImageCacheResult(True, docker_image_path, "Cached Docker image already exists.")

        prerequisite_check = self._check_prerequisites(docker_image_url)
        if not prerequisite_check:
            return DockerImageCacheResult(False, "", prerequisite_check.message)

        if not os.path.exists(self.install_path):
            return DockerImageCacheResult(False, "", f"Install path {self.install_path} does not exist.")

        if not os.access(self.install_path, os.W_OK):
            return DockerImageCacheResult(False, "", f"No permission to write in install path {self.install_path}.")

        if not os.path.exists(subdir_path):
            try:
                os.makedirs(subdir_path)
            except OSError as e:
                return DockerImageCacheResult(False, "", f"Failed to create subdirectory {subdir_path}. Error: {e}")

        enroot_import_cmd = (
            f"srun --export=ALL --partition={self.partition_name} "
            f"enroot import -o {docker_image_path} docker://{docker_image_url}"
        )
        logging.debug(f"Importing Docker image: {enroot_import_cmd}")

        try:
            subprocess.run(enroot_import_cmd, shell=True, check=True)
            return DockerImageCacheResult(True, docker_image_path, "Docker image cached successfully.")
        except subprocess.CalledProcessError as e:
            return DockerImageCacheResult(
                False,
                "",
                (
                    f"Failed to import Docker image from {docker_image_url}. "
                    f"Command: {enroot_import_cmd}. "
                    f"Error: {e}. Please check the Docker image URL and ensure that it is accessible and set up with "
                    f"valid credentials."
                ),
            )

    def _check_prerequisites(self, docker_image_url: str) -> PrerequisiteCheckResult:
        """
        Check prerequisites for caching Docker image.

        Args:
            docker_image_url (str): URL of the Docker image.

        Returns:
            PrerequisiteCheckResult: Result of the prerequisite check.
        """
        required_binaries = ["enroot", "srun"]
        missing_binaries = [binary for binary in required_binaries if not shutil.which(binary)]

        if missing_binaries:
            return PrerequisiteCheckResult(
                False, f"{', '.join(missing_binaries)} are required for caching Docker images but are not installed."
            )

        docker_accessible = self._check_docker_image_accessibility(docker_image_url)
        if not docker_accessible.success:
            return docker_accessible

        return PrerequisiteCheckResult(True, "All prerequisites are met.")

    def _check_docker_image_accessibility(self, docker_image_url: str) -> PrerequisiteCheckResult:
        """
        Check if the Docker image URL is accessible.

        Args:
            docker_image_url (str): URL of the Docker image.

        Returns:
            PrerequisiteCheckResult: Result of the Docker image accessibility check.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            docker_image_path = os.path.join(temp_dir, "docker_image.sqsh")
            enroot_import_cmd = f"enroot import -o {docker_image_path} docker://{docker_image_url}"

            logging.debug(f"Checking Docker image accessibility: {enroot_import_cmd}")

            process = subprocess.Popen(enroot_import_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                while True:
                    error_output = process.stderr.readline() if process.stderr else None
                    error_output = error_output.decode() if error_output else ""

                    if error_output:
                        if "Downloading" in error_output or "Found all layers in cache" in error_output:
                            logging.debug(f"Docker image URL, {docker_image_url}, is accessible.")
                            process.terminate()
                            return PrerequisiteCheckResult(
                                True, f"Docker image URL, {docker_image_url}, is accessible."
                            )
                        if "[ERROR]" in error_output:
                            logging.debug(
                                f"Failed to access Docker image URL, {docker_image_url}. Error: {error_output}"
                            )
                            process.terminate()
                            if "401 Unauthorized" in error_output:
                                detailed_message = (
                                    f"Failed to access Docker image URL: {docker_image_url}. Error: {error_output}\n"
                                    "This error indicates that access to the Docker image URL is unauthorized. "
                                    "Please ensure you have the necessary permissions and have followed the "
                                    "instructions in the README for setting up your credentials correctly."
                                )
                                return PrerequisiteCheckResult(False, detailed_message)
                            return PrerequisiteCheckResult(
                                False, f"Failed to access Docker image URL: {docker_image_url}. Error: {error_output}"
                            )
                    if process.poll() is not None:
                        break

                logging.debug(f"Failed to access Docker image URL: {docker_image_url}. Unknown error.")
                return PrerequisiteCheckResult(
                    False, f"Failed to access Docker image URL: {docker_image_url}. Unknown error."
                )
            finally:
                # Ensure the temporary docker image file is removed
                if os.path.exists(docker_image_path):
                    try:
                        os.remove(docker_image_path)
                        logging.debug(f"Temporary Docker image file removed: {docker_image_path}")
                    except OSError as e:
                        logging.error(f"Failed to remove temporary Docker image file {docker_image_path}. Error: {e}")

    def uninstall_cached_image(self, subdir_name: str, docker_image_filename: str) -> DockerImageCacheResult:
        """
        Uninstall the cached Docker image and remove the subdirectory if empty.

        Args:
            subdir_name (str): Subdirectory name within the installation path.
            docker_image_filename (str): Docker image filename.

        Returns:
            DockerImageCacheResult: Result of the uninstallation operation.
        """
        result = self.remove_cached_image(subdir_name, docker_image_filename)
        if not result.success:
            return result

        subdir_path = os.path.join(self.install_path, subdir_name)
        if os.path.isdir(subdir_path):
            try:
                if not os.listdir(subdir_path):
                    os.rmdir(subdir_path)
                    return DockerImageCacheResult(True, subdir_path, "Subdirectory removed successfully.")
            except OSError as e:
                return DockerImageCacheResult(
                    False, subdir_path, f"Failed to remove subdirectory {subdir_path}. Error: {e}"
                )
        return DockerImageCacheResult(True, subdir_path, "Cached Docker image uninstalled successfully.")

    def remove_cached_image(self, subdir_name: str, docker_image_filename: str) -> DockerImageCacheResult:
        """
        Remove an existing cached Docker image.

        Args:
            subdir_name (str): Subdirectory name within the installation path.
            docker_image_filename (str): Docker image filename.

        Returns:
            DockerImageCacheResult: Result of the removal operation.
        """
        docker_image_path = os.path.join(self.install_path, subdir_name, docker_image_filename)
        if os.path.isfile(docker_image_path):
            try:
                os.remove(docker_image_path)
                return DockerImageCacheResult(True, docker_image_path, "Cached Docker image removed successfully.")
            except OSError as e:
                return DockerImageCacheResult(
                    False, docker_image_path, f"Failed to remove cached Docker image at {docker_image_path}. Error: {e}"
                )
        return DockerImageCacheResult(True, docker_image_path, "No cached Docker image found to remove.")
