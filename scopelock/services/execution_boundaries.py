"""Explicit timeout and retry policies for model, persistence, and I/O calls."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from time import sleep
from typing import Awaitable, TypeVar


ResultT = TypeVar("ResultT")


class BoundaryError(RuntimeError):
    pass


class BoundaryTimeoutError(BoundaryError):
    pass


class RetryExhaustedError(BoundaryError):
    pass


@dataclass(frozen=True)
class BoundaryPolicy:
    name: str
    timeout_seconds: float
    max_attempts: int
    backoff_seconds: float = 0.1

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.max_attempts < 1:
            raise ValueError("Boundary timeout and attempts must be positive")


def run_with_boundary(
    operation: Callable[[], ResultT],
    *,
    policy: BoundaryPolicy,
    retry_on: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError),
    sleeper: Callable[[float], None] = sleep,
) -> ResultT:
    last_error: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(operation)
        try:
            return future.result(timeout=policy.timeout_seconds)
        except FutureTimeoutError as error:
            future.cancel()
            last_error = BoundaryTimeoutError(
                f"{policy.name} timed out after {policy.timeout_seconds} seconds"
            )
            if attempt == policy.max_attempts:
                raise last_error from error
        except retry_on as error:
            last_error = error
            if attempt == policy.max_attempts:
                raise RetryExhaustedError(
                    f"{policy.name} failed after {attempt} attempts"
                ) from error
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        sleeper(policy.backoff_seconds * attempt)
    raise RetryExhaustedError(f"{policy.name} failed") from last_error


async def run_async_with_boundary(
    operation: Callable[[], Awaitable[ResultT]],
    *,
    policy: BoundaryPolicy,
    retry_on: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError),
) -> ResultT:
    last_error: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await asyncio.wait_for(operation(), timeout=policy.timeout_seconds)
        except asyncio.TimeoutError as error:
            last_error = BoundaryTimeoutError(
                f"{policy.name} timed out after {policy.timeout_seconds} seconds"
            )
            if attempt == policy.max_attempts:
                raise last_error from error
        except retry_on as error:
            last_error = error
            if attempt == policy.max_attempts:
                raise RetryExhaustedError(
                    f"{policy.name} failed after {attempt} attempts"
                ) from error
        await asyncio.sleep(policy.backoff_seconds * attempt)
    raise RetryExhaustedError(f"{policy.name} failed") from last_error


class WorkflowExecutionBoundaries:
    """Named P0 policies; sends deliberately have no blind retry."""

    model_policy = BoundaryPolicy("model", timeout_seconds=45, max_attempts=3)
    persistence_policy = BoundaryPolicy(
        "persistence", timeout_seconds=10, max_attempts=4
    )
    external_read_policy = BoundaryPolicy(
        "external_read", timeout_seconds=20, max_attempts=3
    )
    external_send_policy = BoundaryPolicy(
        "external_send", timeout_seconds=20, max_attempts=1
    )

    @classmethod
    def model(cls, operation: Callable[[], ResultT]) -> ResultT:
        return run_with_boundary(operation, policy=cls.model_policy)

    @classmethod
    async def model_async(
        cls,
        operation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        return await run_async_with_boundary(operation, policy=cls.model_policy)

    @classmethod
    def persistence(cls, operation: Callable[[], ResultT]) -> ResultT:
        return run_with_boundary(operation, policy=cls.persistence_policy)

    @classmethod
    def external_read(cls, operation: Callable[[], ResultT]) -> ResultT:
        return run_with_boundary(operation, policy=cls.external_read_policy)

    @classmethod
    def external_send(cls, operation: Callable[[], ResultT]) -> ResultT:
        return run_with_boundary(operation, policy=cls.external_send_policy)
