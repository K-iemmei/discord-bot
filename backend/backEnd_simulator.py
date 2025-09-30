from fastapi import FastAPI, HTTPException #type: ignore
from pydantic import BaseModel #type: ignore
import sqlite3 

app = FastAPI(title = "Management Library API")

DB_NAME = "library.db" 

class Book(BaseModel):
    title: str
    author: str
    year: int | None = None
    genre: str | None = None


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn

@app.post("/books", response_model=Book)
async def add_book(book: Book):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO books (title, author, year, genre) VALUES (?, ?, ?, ?)",
        (book.title, book.author, book.year, book.genre)
    )
    conn.commit()
    conn.close()
    return book

@app.get("/books/{book_id}", response_model=Book)
async def get_book(book_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, author, year, genre FROM books WHERE id = ?", (book_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Book(title=row[0], author=row[1], year=row[2], genre=row[3])
    else:
        raise HTTPException(status_code=404, detail="Book not found")
    
@app.put("/books/{book_id}", response_model=Book)
async def update_book(book_id: int, book: Book):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE books SET title = ?, author = ?, year = ?, genre = ? WHERE id = ?",
        (book.title, book.author, book.year, book.genre, book_id)
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return book
@app.delete("/books/{book_id}")
async def delete_book(book_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"detail": "Book deleted"}

@app.get("/books")
async def list_books():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, author, year, genre FROM books")
    rows = cursor.fetchall()
    conn.close()
    books = [{"id": row[0], "title": row[1], "author": row[2], "year": row[3], "genre": row[4]} for row in rows]
    return books
