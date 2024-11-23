from abc import ABC, abstractmethod
from typing import Optional, Union

from zrb.task.any_task import AnyTask


class AnyGroup(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Group name"""
        pass

    @property
    @abstractmethod
    def banner(self) -> str:
        """Group banner"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Group description"""
        pass

    @property
    @abstractmethod
    def subtasks(self) -> dict[str, AnyTask]:
        """Group subtasks"""
        pass

    @property
    @abstractmethod
    def subgroups(self) -> dict[str, "AnyGroup"]:
        """Group subgroups"""
        pass

    @abstractmethod
    def add_group(self, group: Union["AnyGroup", str]) -> "AnyGroup":
        pass

    @abstractmethod
    def add_task(self, task: AnyTask, alias: str | None = None) -> AnyTask:
        pass

    @abstractmethod
    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        pass

    @abstractmethod
    def get_group_by_alias(self, name: str) -> Optional["AnyGroup"]:
        pass
