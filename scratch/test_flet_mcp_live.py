import asyncio
import os
import sys

sys.path.insert(0, r"C:\Users\Admin\Desktop\Code\NU-Front")

from fastmcp import Client
from flet_mcp import mcp

async def test_flet_mcp():
    async with Client(mcp) as client:
        print("=== 1. Testing get_api for PopupMenuItem ===")
        res_popup = await client.call_tool("get_api", {"name": "PopupMenuItem"})
        for line in str(res_popup.data).splitlines():
            if any(k in line for k in ["content:", "text:", "bases:", "PopupMenuItem"]):
                print(" ", line)

        print("\n=== 2. Testing get_api for FilePicker ===")
        res_fp = await client.call_tool("get_api", {"name": "FilePicker"})
        for line in str(res_fp.data).splitlines()[:6]:
            print(" ", line)

        print("\n=== 3. Testing enum_has_member for BoxFit ===")
        res_enum1 = await client.call_tool("enum_has_member", {"name": "BoxFit", "member": "COVER"})
        res_enum2 = await client.call_tool("enum_has_member", {"name": "BoxFit", "member": "CONTAIN"})
        res_enum3 = await client.call_tool("enum_has_member", {"name": "ImageFit", "member": "COVER"})
        print("  BoxFit.COVER exists:", res_enum1.data)
        print("  BoxFit.CONTAIN exists:", res_enum2.data)
        print("  ImageFit exists:", res_enum3.data)

        print("\n=== 4. Testing find_icon for 'browser' and 'terminal' ===")
        res_icon1 = await client.call_tool("find_icon", {"query": "browser", "limit": 3})
        res_icon2 = await client.call_tool("find_icon", {"query": "terminal", "limit": 3})
        print("  'browser' icons found:\n", res_icon1.data)
        print("  'terminal' icons found:\n", res_icon2.data)

        print("\n=== 5. Testing search_enum_members for Icons with 'PLAY' ===")
        res_search = await client.call_tool("search_enum_members", {"name": "Icons", "query": "PLAY", "limit": 5})
        print("  Icons with PLAY:\n", res_search.data)

if __name__ == "__main__":
    asyncio.run(test_flet_mcp())
