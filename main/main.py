from typing import Optional
from fastapi import FastAPI, Response, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx
import asyncio
from postgres import Postgres
import os


templates = Jinja2Templates(directory="templates")
db = Postgres(os.environ["POSTGRES_DB"])
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


async def get_item(id: int, client: httpx.AsyncClient):
    item = await client.get(
        f"https://hacker-news.firebaseio.com/v0/item/{id}.json?print=pretty"
    )
    return {k: v for k, v in item.json().items() if type(v) != list}


async def top_items(page: int):
    async with httpx.AsyncClient() as client:
        r = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        items = list(
            map(
                lambda id: get_item(id, client),
                r.json()[30 * (page - 1) : 30 * page],
            )
        )

        return await asyncio.gather(*items)


@app.get("/top", response_class=HTMLResponse)
@app.get("/top/{page}", response_class=HTMLResponse)
async def top(request: Request, page: Optional[int] = 1):
    stories = list(await top_items(page))
    return templates.TemplateResponse(
        "top.html.jinja", {"request": request, "stories": stories, "page": page}
    )
