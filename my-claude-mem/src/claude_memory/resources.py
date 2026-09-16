import asyncio
import json
from collections.abc import Sequence

from chromadb.api import ClientAPI
from fastmcp.resources import FunctionResource, Resource
from fastmcp.server.providers import Provider


def memory_space_uri(name: str) -> str:
    return f"memory://space/{name}"


def list_memory_space_names(client: ClientAPI) -> list[str]:
    return [c.name for c in client.list_collections()]


def read_memory_space_info(client: ClientAPI, name: str) -> str:
    col = client.get_collection(name=name)
    payload = {
        "name": col.name,
        "id": str(col.id),
        "metadata": col.metadata,
        "count": col.count(),
    }
    return json.dumps(payload)


class MemorySpacesProvider(Provider):
    """Publishes every live memory space as a readable resource.

    Overrides dynamic listing so `resources/list` always reflects the current
    set of memory spaces without upfront registration. Clients cache that list,
    so tools that change the set must call `ctx.session.send_resource_list_changed`.
    Reading a memory space resource returns its name, id, metadata, and count.
    """

    def __init__(self, client: ClientAPI) -> None:
        super().__init__()
        self.client = client

    async def _list_resources(self) -> Sequence[Resource]:
        names = await asyncio.to_thread(list_memory_space_names, self.client)
        return [self.make_resource(name) for name in names]

    def make_resource(self, name: str) -> Resource:
        async def read() -> str:
            return await asyncio.to_thread(read_memory_space_info, self.client, name)

        return FunctionResource.from_function(
            read,
            uri=memory_space_uri(name),
            name=name,
            title=f"Memory space: {name}",
            description=f"Name, id, metadata, and memory count for the '{name}' memory space.",
            mime_type="application/json",
        )
