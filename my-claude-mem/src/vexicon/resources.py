import asyncio
import json
from collections.abc import Sequence

from chromadb.api import ClientAPI
from fastmcp.resources import FunctionResource, Resource
from fastmcp.server.providers import Provider

from vexicon.idle_proxy import IdleUnloadingProxy


def space_uri(name: str) -> str:
    return f"vexicon://space/{name}"


def list_space_names(client: ClientAPI) -> list[str]:
    return [c.name for c in client.list_collections()]


def read_space_info(client: ClientAPI, name: str) -> str:
    col = client.get_collection(name=name)
    payload = {
        "name": col.name,
        "id": str(col.id),
        "metadata": col.metadata,
        "count": col.count(),
    }
    return json.dumps(payload)


class SpacesProvider(Provider):
    """Publishes every live space as a readable resource.

    Overrides dynamic listing so `resources/list` always reflects the current
    set of spaces without upfront registration. Clients cache that list,
    so tools that change the set must call `ctx.session.send_resource_list_changed`.
    Reading a space resource returns its name, id, metadata, and count.
    """

    def __init__(self, chroma: IdleUnloadingProxy[ClientAPI]) -> None:
        super().__init__()
        self.chroma = chroma

    async def _list_resources(self) -> Sequence[Resource]:
        async with self.chroma.lease() as client:
            names = await asyncio.to_thread(list_space_names, client)
        return [self.make_resource(name) for name in names]

    def make_resource(self, name: str) -> Resource:
        async def read() -> str:
            async with self.chroma.lease() as client:
                return await asyncio.to_thread(read_space_info, client, name)

        return FunctionResource.from_function(
            read,
            uri=space_uri(name),
            name=name,
            title=f"Space: {name}",
            description=f"Metadata and entry count of the '{name}' space.",
            mime_type="application/json",
        )
