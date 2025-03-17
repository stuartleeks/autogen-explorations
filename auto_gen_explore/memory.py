from typing import Any
from autogen_core import CancellationToken
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType, MemoryQueryResult


class ListMemory2(ListMemory):
    """ListMemory2 is a simple implementation of ListMemory that stores memory contents in a list.

    This class is used to demonstrate the basic functionality of ListMemory and how to
    implement the required methods. It is not intended for production use.

    Args:
        name: Optional identifier for this memory instance

    """

    def __call__(self, *args, **kwds):
        return super().__call__(*args, **kwds)

    def _filter_on_memory_content(self, values: list[MemoryContent], query: MemoryContent):
        """Filter the memory contents based on a query.

        Args:
            values: List of MemoryContent to filter
            query: MemoryContent to filter by

        Returns:
            List of MemoryContent that match the query
        """

        def metadata_matches(
            content: MemoryContent,
            query: MemoryContent,
        ) -> bool:
            """Check if the metadata of the content matches the query."""
            for key, value in query.metadata.items():
                if key not in content.metadata or content.metadata.get(key) != value:
                    return False
            return True

        result = []
        for content in values:
            if query.metadata and not metadata_matches(content, query):
                continue
            if query.mime_type and content.mime_type != query.mime_type:
                continue
            if query.content and query.content not in content.content:
                continue
            result.append(content)

        return result

    async def query(
        self,
        query: str | MemoryContent = "",
        cancellation_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> MemoryQueryResult:
        """Return all memories without any filtering.

        Args:
            query: Ignored in this implementation
            cancellation_token: Optional token to cancel operation
            **kwargs: Additional parameters (ignored)

        Returns:
            MemoryQueryResult containing all stored memories
        """
        _ = cancellation_token, kwargs

        results = self._contents
        if query:
            if isinstance(query, str):
                results = [
                    content for content in self._contents if query in str(content.content)]
            elif isinstance(query, MemoryContent):
                results = self._filter_on_memory_content(self._contents, query)
            else:
                raise ValueError("Query must be a string or MemoryContent")

        return MemoryQueryResult(results=results)
