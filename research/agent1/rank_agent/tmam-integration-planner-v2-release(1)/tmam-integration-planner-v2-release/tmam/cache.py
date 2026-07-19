from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Generic, Hashable, Iterator, TypeVar

from .contracts import FamilyContext, Progress

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True)
class GoalCacheKey:
    target_canonical_id: str
    progress: tuple[int, ...]
    family_context: tuple[str, tuple[tuple[str, Hashable], ...]]
    registry_generation: int

    @classmethod
    def build(
        cls,
        target_canonical_id: str,
        progress: Progress,
        family_context: FamilyContext,
        registry_generation: int,
    ) -> "GoalCacheKey":
        return cls(
            target_canonical_id,
            progress.components,
            family_context.cache_key,
            registry_generation,
        )


@dataclass(frozen=True)
class ProviderCacheKey:
    goal: GoalCacheKey
    provider_id: str
    provider_revision: str


@dataclass(frozen=True)
class CandidateCacheKey:
    provider: ProviderCacheKey
    ordinal: int


@dataclass(frozen=True)
class CacheStats:
    size: int
    hits: int
    misses: int
    invalidations: int


class GenerationalCache(Generic[K, V]):
    """Small thread-safe cache with explicit selective invalidation.

    It deliberately does not hide invalidation semantics behind an LRU.  TMAM
    provider results are proof data: stale semantic contexts are more dangerous
    than memory pressure.  The planner's public invalidation API is therefore
    explicit and the registry generation is part of every key.
    """

    def __init__(self) -> None:
        self._values: dict[K, V] = {}
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    def get(self, key: K) -> V | None:
        with self._lock:
            if key in self._values:
                self._hits += 1
                return self._values[key]
            self._misses += 1
            return None

    def peek(self, key: K) -> V | None:
        with self._lock:
            return self._values.get(key)

    def put(self, key: K, value: V) -> V:
        with self._lock:
            self._values[key] = value
        return value

    def get_or_create(self, key: K, factory: Callable[[], V]) -> tuple[V, bool]:
        with self._lock:
            if key in self._values:
                self._hits += 1
                return self._values[key], True
            self._misses += 1
            value = factory()
            self._values[key] = value
            return value, False

    def invalidate(self, predicate: Callable[[K, V], bool] | None = None) -> int:
        with self._lock:
            if predicate is None:
                count = len(self._values)
                self._values.clear()
            else:
                doomed = [key for key, value in self._values.items() if predicate(key, value)]
                for key in doomed:
                    del self._values[key]
                count = len(doomed)
            if count:
                self._invalidations += count
            return count

    def items(self) -> tuple[tuple[K, V], ...]:
        with self._lock:
            return tuple(self._values.items())

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(len(self._values), self._hits, self._misses, self._invalidations)
