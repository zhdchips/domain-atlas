"""Shared retry and safe observability primitives for external HTTP providers."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx


RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RetryPolicy:
    """Request-level policy; ``max_retries`` excludes the initial attempt."""

    timeout_seconds: float
    max_retries: int = 2
    base_delay_seconds: float = 1.0
    jitter_seconds: float = 0.2

    @property
    def max_attempts(self) -> int:
        return max(1, self.max_retries + 1)


@dataclass(frozen=True)
class ProviderFailure:
    provider: str
    operation: str
    category: str
    attempts: int
    max_attempts: int
    retryable: bool
    status_code: int | None = None

    @property
    def recovery_message(self) -> str:
        return {
            "timeout": "请求超时，可稍后重试。",
            "network": "网络连接暂时不可用，可稍后重试。",
            "rate_limited": "服务当前限流，请稍后重试。",
            "server_error": "服务暂时不可用，请稍后重试。",
            "configuration": "请检查 Provider 配置或访问权限。",
            "client_error": "请求未被服务接受，请检查配置后重试。",
            "invalid_response": "服务返回内容格式无效，请稍后重试。",
        }.get(self.category, "外部服务暂时不可用，可稍后重试。")

    @property
    def safe_message(self) -> str:
        status = f"（HTTP {self.status_code}）" if self.status_code is not None else ""
        return (
            f"{self.provider}{self.operation}{_category_label(self.category)}{status}，"
            f"已尝试 {self.attempts}/{self.max_attempts} 次。{self.recovery_message}"
        )

    def to_output(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "category": self.category,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "recovery_message": self.recovery_message,
        }


@dataclass(frozen=True)
class RetryEvent:
    phase: str
    failure: ProviderFailure
    next_delay_seconds: float = 0.0

    def to_output(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            **self.failure.to_output(),
            "next_delay_seconds": round(self.next_delay_seconds, 2),
        }


class ProviderRequestError(RuntimeError):
    """A terminal, safe-to-display external request failure."""

    def __init__(self, failure: ProviderFailure) -> None:
        self.failure = failure
        super().__init__(failure.safe_message)


RetryObserver = Callable[[RetryEvent], None]
RequestSender = Callable[[float], httpx.Response]


def execute_http_request(
    *,
    provider: str,
    operation: str,
    policy: RetryPolicy,
    send: RequestSender,
    observer: RetryObserver | None = None,
    sleep: Callable[[float], None] = time.sleep,
    random_uniform: Callable[[float, float], float] = random.uniform,
) -> httpx.Response:
    """Execute one idempotent HTTP read/request with bounded retries.

    Callers must use this only for operations safe to repeat. It deliberately
    does not retry any database, vector, or workflow persistence operation.
    """

    previous_failure: ProviderFailure | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = send(policy.timeout_seconds)
        except httpx.TimeoutException as exc:
            failure = _failure(
                provider=provider,
                operation=operation,
                category="timeout",
                attempt=attempt,
                policy=policy,
            )
            _retry_or_raise(
                failure=failure,
                policy=policy,
                observer=observer,
                sleep=sleep,
                random_uniform=random_uniform,
                cause=exc,
            )
            previous_failure = failure
            continue
        except httpx.RequestError as exc:
            failure = _failure(
                provider=provider,
                operation=operation,
                category="network",
                attempt=attempt,
                policy=policy,
            )
            _retry_or_raise(
                failure=failure,
                policy=policy,
                observer=observer,
                sleep=sleep,
                random_uniform=random_uniform,
                cause=exc,
            )
            previous_failure = failure
            continue

        if response.status_code < 400:
            if previous_failure is not None:
                _notify(observer, RetryEvent(phase="recovered", failure=previous_failure))
            return response

        failure = _http_failure(
            provider=provider,
            operation=operation,
            status_code=response.status_code,
            attempt=attempt,
            policy=policy,
        )
        if not failure.retryable:
            _notify(observer, RetryEvent(phase="failed", failure=failure))
            raise ProviderRequestError(failure)
        previous_failure = failure
        _retry_or_raise(
            failure=failure,
            policy=policy,
            observer=observer,
            sleep=sleep,
            random_uniform=random_uniform,
            cause=None,
        )
        continue

    raise AssertionError("retry loop must return or raise")


def invalid_response_failure(
    *,
    provider: str,
    operation: str,
    attempts: int = 1,
    max_attempts: int = 1,
    observer: RetryObserver | None = None,
) -> ProviderRequestError:
    error = ProviderRequestError(
        ProviderFailure(
            provider=provider,
            operation=operation,
            category="invalid_response",
            attempts=attempts,
            max_attempts=max_attempts,
            retryable=False,
        )
    )
    _notify(observer, RetryEvent(phase="failed", failure=error.failure))
    return error


def _retry_or_raise(
    *,
    failure: ProviderFailure,
    policy: RetryPolicy,
    observer: RetryObserver | None,
    sleep: Callable[[float], None],
    random_uniform: Callable[[float, float], float],
    cause: Exception | None,
) -> None:
    if failure.attempts >= failure.max_attempts:
        _notify(observer, RetryEvent(phase="failed", failure=failure))
        error = ProviderRequestError(failure)
        if cause is not None:
            raise error from cause
        raise error
    delay = _retry_delay(policy, failure.attempts, random_uniform)
    _notify(observer, RetryEvent(phase="retrying", failure=failure, next_delay_seconds=delay))
    sleep(delay)


def _failure(
    *,
    provider: str,
    operation: str,
    category: str,
    attempt: int,
    policy: RetryPolicy,
) -> ProviderFailure:
    return ProviderFailure(
        provider=provider,
        operation=operation,
        category=category,
        attempts=attempt,
        max_attempts=policy.max_attempts,
        retryable=True,
    )


def _http_failure(
    *,
    provider: str,
    operation: str,
    status_code: int,
    attempt: int,
    policy: RetryPolicy,
) -> ProviderFailure:
    if status_code == 429:
        category, retryable = "rate_limited", True
    elif status_code in {500, 502, 503, 504}:
        category, retryable = "server_error", True
    elif status_code in {401, 403}:
        category, retryable = "configuration", False
    else:
        category, retryable = "client_error", False
    return ProviderFailure(
        provider=provider,
        operation=operation,
        category=category,
        attempts=attempt,
        max_attempts=policy.max_attempts,
        retryable=retryable,
        status_code=status_code,
    )


def _retry_delay(
    policy: RetryPolicy,
    failed_attempt: int,
    random_uniform: Callable[[float, float], float],
) -> float:
    base_delay = max(0.0, policy.base_delay_seconds) * (2 ** (failed_attempt - 1))
    jitter = random_uniform(0.0, max(0.0, policy.jitter_seconds))
    return base_delay + jitter


def _notify(observer: RetryObserver | None, event: RetryEvent) -> None:
    if observer is None:
        return
    try:
        observer(event)
    except Exception:
        # Observability must not turn an otherwise successful provider call into a failure.
        return


def _category_label(category: str) -> str:
    return {
        "timeout": "请求超时",
        "network": "网络连接失败",
        "rate_limited": "服务限流",
        "server_error": "服务暂时不可用",
        "configuration": "配置或访问受限",
        "client_error": "请求失败",
        "invalid_response": "返回格式无效",
    }.get(category, "请求失败")
