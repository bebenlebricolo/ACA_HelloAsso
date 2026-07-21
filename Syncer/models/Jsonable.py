from dataclasses import dataclass, field
from typing import Any, Optional, Generic, TypeVar, Union, cast

# Pulled from VerticalBackend repository https://github.com/bebenlebricolo/VerticalBackend/blob/1f3e58e33d02c074860744bc562d079b6b4f03dc/Archived/VertiScraper/Sources/Models/Jsonable.py#L5

class Jsonable :
    T = TypeVar("T")
    def _read_prop(self, key : str, content : dict[str, T], default : T) -> T:
        if key in content :
            return content[key]
        return default

    def to_json(self) -> dict[str, Any] :
        return {}

    def from_json(self, content : dict[str, Any]) -> None :
        pass

T = TypeVar("T")

@dataclass
class JsonProperty(Generic[T]):
    value : T
    key : str = field(default_factory=str)

    def __init__(self, key : str = "", val : T = None) -> None:
        self.key = key
        self.value = val

    def get_node(self, content : dict[str, T]) -> Optional[Union[dict[str, T], T]] :
        if self.key in content :
            return content[self.key]
        return None

    def read(self, content : dict[str, T]) -> Optional[Union[dict[str, T], T]] :
        return self.get_node(content)

    def try_read(self, content : dict[str, T], default : T) -> T:
        """Tries to access input dictionary content using self._prop_key and returns what's inside.
            if input node does not yield exploitable data, return the default value instead.
            End user knows what's inside this JsonProperty object and can use this knowledge to manipulate the data accordingly (
            this object has not enough knowledge to perform this kind of tasks alone (...))"""
        node = self.get_node(content)
        if node:
           node = cast(T, node)
           return node
        return default

    def __eq__(self, other: object) -> bool:
        if type(self) != type(other) :
            return False
        other = cast(JsonProperty[T], other)
        self = cast(JsonProperty[T], self)
        return self.value == other.value

@dataclass
class JsonOptionalProperty(Generic[T]):
    value : Optional[T] = None
    key : str = field(default_factory=str)

    def __init__(self, key : str = "", val : Optional[T] = None) -> None:
        self.key = key
        self.value = val

    def get_node(self, content : dict[str, Any]) -> Optional[Union[dict[str, Any], str]] :
        if self.key in content :
            return content[self.key]
        return None

    def read(self, content : dict[str, Any]) -> Optional[Union[dict[str, Any], str]] :
        return self.get_node(content)

    def try_read(self, content : dict[str,Any], default : T) -> Union[dict[str, Any], str, T]:
        """Tries to access input dictionary content using self._prop_key and returns what's inside.
            if input node does not yield exploitable data, return the default value instead.
            End user knows what's inside this JsonProperty object and can use this knowledge to manipulate the data accordingly (
            this object has not enough knowledge to perform this kind of tasks alone (...))"""
        node = self.get_node(content)
        if node :
           return node
        return default

    def __eq__(self, other: object) -> bool:
        if type(self) != type(other) :
            return False
        other = cast(JsonOptionalProperty[T], other)
        self = cast(JsonOptionalProperty[T], self)
        return self.value == other.value