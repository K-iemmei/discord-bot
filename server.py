import asyncio
import httpx # type: ignore
from mcp.server.fastmcp import FastMCP  # type: ignore

server = FastMCP("book-crud-server")

API_BASE = "http://localhost:8000"  

# ------------------------
# CRUD TOOLS
# ------------------------

@server.tool()
async def create_book(title: str, author: str, year: int = None, genre: str = None) -> dict:
    """
    Dùng khi cần tạo (thêm) một cuốn sách mới vào database.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE}/books/", json={
            "title": title,
            "author": author,
            "year": year,
            "genre": genre
        })
        
        # Debug log
        print("STATUS:", response.status_code)
        print("RESPONSE TEXT:", response.text)

        # Chỉ parse JSON khi status code ok
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"{response.status_code} {response.text}"}


@server.tool()
async def read_book(book_id: int) -> dict:
    """
    Dùng khi cần đọc thông tin chi tiết của một cuốn sách dựa theo ID.
    
    Args:
        book_id (int): ID của cuốn sách.
    
    Returns:
        dict: Thông tin cuốn sách (title, author, year, genre).
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/books/{book_id}")
        return response.json()

@server.tool()
async def update_book(book_id: int, title: str = None, author: str = None, year: int = None, genre: str = None) -> dict:
    """
    Dùng khi cần cập nhật thông tin một cuốn sách.
    
    Args:
        book_id (int): ID của cuốn sách cần update.
        title (str, optional): Tên sách mới.
        author (str, optional): Tác giả mới.
        year (int, optional): Năm xuất bản mới.
        genre (str, optional): Thể loại mới.
    
    Returns:
        dict: Thông tin cuốn sách sau khi được cập nhật.
    """
    async with httpx.AsyncClient() as client:
        response = await client.put(f"{API_BASE}/books/{book_id}", json={
            "title": title,
            "author": author,
            "year": year,
            "genre": genre
        })
        return response.json()

@server.tool()
async def delete_book(book_id: int) -> dict:
    """
    Dùng khi cần xóa một cuốn sách khỏi database.
    
    Args:
        book_id (int): ID của cuốn sách cần xóa.
    
    Returns:
        dict: Kết quả xóa (success message).
    """
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{API_BASE}/books/{book_id}")
        return response.json()

@server.tool()
async def list_books() -> list:
    """
    Dùng khi cần lấy danh sách tất cả sách trong database.
    
    Returns:
        list: Danh sách các cuốn sách (mỗi sách là dict chứa id, title, author, year, genre).
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/books/")
        return response.json()
# ----------------------
# TOOL: Chào thành viên mới
# ----------------------
@server.tool()
async def hello(user_id: str) -> str:
    """Chào một user dựa theo user_id khi có người mới tham gia server Discord."""
    return f"```Xin chào, {user_id}!```"

# ----------------------
# Run MCP server
# ----------------------
if __name__ == "__main__":
    server.run(transport="stdio")



