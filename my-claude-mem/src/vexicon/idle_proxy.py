import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager


class IdleUnloadingProxy[T]:
    """Load a resource on first lease; unload it after idle_seconds without leases.

    Access the resource only through `lease()`. The resource is not unloaded
    while a lease is held; the idle clock starts when the last lease is released.
    Loading and unloading run in a worker thread, serialized by a lock, so
    concurrent first callers trigger exactly one load and a reload cannot
    overlap an in-progress unload.

    `unload` receives the resource so it can release handles the object owns
    (database connections, file locks). `reclaim` runs after the proxy has
    dropped its reference and is for release work that only helps once no
    reference remains (gc.collect for cycles, torch.cuda.empty_cache for
    allocator caches).
    """

    def __init__(
        self,
        load: Callable[[], T],
        idle_seconds: float,
        unload: Callable[[T], None] | None = None,
        reclaim: Callable[[], None] | None = None,
    ) -> None:
        self.load = load
        self.unload = unload
        self.reclaim = reclaim
        self.idle_seconds = idle_seconds
        self.lock = asyncio.Lock()
        self.resource: T | None = None
        self.active_leases = 0
        self.idle_deadline = 0.0
        self.reaper: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lease(self) -> AsyncGenerator[T]:
        loop = asyncio.get_running_loop()
        async with self.lock:
            if self.resource is None:
                self.resource = await asyncio.to_thread(self.load)
                self.reaper = asyncio.create_task(self.unload_when_idle())
            self.active_leases += 1
            self.idle_deadline = loop.time() + self.idle_seconds
            resource = self.resource
        try:
            yield resource
        finally:
            async with self.lock:
                self.active_leases -= 1
                self.idle_deadline = loop.time() + self.idle_seconds

    async def unload_when_idle(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            async with self.lock:
                now = loop.time()
                if self.active_leases == 0 and now >= self.idle_deadline:
                    await self.release_resource_locked()
                    self.reaper = None
                    return
                if self.active_leases == 0:
                    delay = self.idle_deadline - now
                else:
                    delay = self.idle_seconds
            await asyncio.sleep(delay)

    async def aclose(self) -> None:
        async with self.lock:
            if self.reaper is not None:
                self.reaper.cancel()
                self.reaper = None
            await self.release_resource_locked()

    async def release_resource_locked(self) -> None:
        """Unload and drop the resource, then reclaim its memory; caller must hold the lock."""
        if self.resource is None:
            return
        resource = self.resource
        self.resource = None
        if self.unload is not None:
            await asyncio.to_thread(self.unload, resource)
        if self.reclaim is not None:
            await asyncio.to_thread(self.reclaim)
